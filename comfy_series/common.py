from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import urllib.request
from urllib.parse import urlparse
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SeriesError(Exception):
    def __init__(self, code: str, message: str, details=None):
        super().__init__(message)
        self.code, self.details = code, details


def now():
    try:
        zone = ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        from datetime import timezone, timedelta
        zone = timezone(timedelta(hours=8))
    return datetime.now(zone).isoformat(timespec="seconds")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identifier(value, prefix=None):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value):
        raise SeriesError("invalid_identifier", "编号含非法字符", {"value": str(value)})
    if prefix and not value.startswith(prefix):
        raise SeriesError("invalid_identifier", "编号类型不符")
    return value


def within(path, root):
    resolved, parent = Path(path).resolve(), Path(root).resolve()
    return resolved == parent or parent in resolved.parents


class Config:
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).resolve().parents[1]).resolve()
        raw = read_json(self.root / "comfy_series.json") if (self.root / "comfy_series.json").exists() else {}
        self.server = raw.get("server", "http://127.0.0.1:8190").rstrip("/")
        self.comfy_root = Path(raw.get("comfy_root", "D:/comfyui/ComfyUI_windows_portable/ComfyUI"))
        self.data = self.root / "data"
        self.model_root = self.data / "models"
        self.output = Path(raw.get("comfy_output", str(self.root / "comfy_workflow/output")))
        self.input = Path(raw.get("comfy_input", str(self.root / "comfy_workflow/input")))
        self.poll_seconds = raw.get("poll_seconds", 2)
        self.timeout_seconds = raw.get("timeout_seconds", 1200)
        self.default_budget = 30_000_000_000
        self.raw = raw

    def model_dirs(self, category):
        if category not in {"checkpoints", "loras", "clip_vision", "ipadapter", "upscale_models", "controlnet", "vae"}:
            raise SeriesError("invalid_category", "未知模型目录", {"category": category})
        return [self.model_root / category, self.comfy_root / "models" / category]


def external_http(config, url, **kwargs):
    import httpx
    # Explicit proxy avoids httpx 0.28's malformed IPv6 NO_PROXY parsing on Windows.
    proxy = None
    if urlparse(url).hostname not in ("127.0.0.1", "localhost", "::1"):
        proxies = urllib.request.getproxies()
        proxy = config.raw.get("proxy") or proxies.get("https") or proxies.get("all") or proxies.get("http")
    return httpx.Client(trust_env=False, proxy=proxy, **kwargs)


class Store:
    def __init__(self, config):
        self.config = config
        config.data.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(config.data / "comfy_series.sqlite", timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
              kind TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL,
              updated TEXT NOT NULL, PRIMARY KEY(kind,key));
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL,
              key TEXT NOT NULL, data TEXT NOT NULL);
        """)

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def get(self, kind, key, default=None):
        row = self.db.execute("SELECT data FROM records WHERE kind=? AND key=?", (kind, key)).fetchone()
        return json.loads(row[0]) if row else default

    def need(self, kind, key):
        value = self.get(kind, key)
        if value is None:
            raise SeriesError("not_found", f"未找到 {kind}: {key}")
        return value

    def put(self, kind, key, value, commit=True):
        self.db.execute("INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,key) DO UPDATE SET data=excluded.data,updated=excluded.updated",
                        (kind, key, json.dumps(value, ensure_ascii=False), now()))
        if commit:
            self.db.commit()
        return value

    def all(self, kind):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM records WHERE kind=? ORDER BY key", (kind,))]

    def event(self, kind, key, value):
        self.db.execute("INSERT INTO events(at,kind,key,data) VALUES(?,?,?,?)", (now(), kind, key, json.dumps(value, ensure_ascii=False)))
        self.db.commit()

    def allocate(self, kind, prefix, width=3):
        with self.transaction():
            key = "sequence:" + kind
            n = self.get("settings", key, 0) + 1
            while self.get(kind, f"{prefix}{n:0{width}d}") is not None:
                n += 1
            self.put("settings", key, n, commit=False)
        return f"{prefix}{n:0{width}d}"

    def create_series(self, style_key=None, name="", series_id=None, budget=None, isolated=False):
        if style_key:
            self.need("styles", style_key)
        sid = identifier(series_id) if series_id else self.allocate("series", "SC")
        if self.get("series", sid):
            existing = self.need("series", sid)
            if style_key and existing.get("style_key") != style_key:
                raise SeriesError("series_style_locked", "同一系列不能静默更换风格；请新建系列")
            return existing
        return self.put("series", sid, {"id": sid, "name": name or sid, "style_key": style_key,
                         "download_budget_bytes": budget if budget is not None else self.config.default_budget,
                         "isolated": isolated, "created_at": now()})

    def budget(self, sid):
        series = self.need("series", sid)
        used = sum(x.get("committed_bytes", 0) for x in self.all("downloads") if x.get("series_id") == sid and x.get("status") == "complete")
        reserved = sum(x["reserved_bytes"] for x in self.all("downloads") if x.get("series_id") == sid and x.get("status") != "complete")
        return {"limit": series["download_budget_bytes"], "used": used, "reserved": reserved,
                "remaining": series["download_budget_bytes"] - used - reserved}

    def resolve_style(self, key):
        if not key:
            return None
        key = key.replace("【同风格:", "").replace("】", "")
        if re.fullmatch(r"S\d+", key):
            matches = [x for x in self.all("styles") if x["style_id"] == key]
            if not matches:
                raise SeriesError("style_not_found", "风格编号不存在", {"style": key})
            return max(matches, key=lambda x: x["revision"])
        return self.need("styles", identifier(key))

    def create_style(self, payload):
        with self.transaction():
            result = self._create_style_locked(payload)
        write_json(self.config.data / "styles" / (result["style_key"] + ".json"), result)
        return result

    def _create_style_locked(self, payload):
        payload = dict(payload)
        if payload.get("style_key"):
            payload["based_on"] = payload["style_key"]
        for key in ("visual_baseline", "asset_ids", "model_manifest", "origin"):
            payload.pop(key, None)
        sid = payload.get("style_id")
        if sid:
            if not re.fullmatch(r"S\d+", sid):
                raise SeriesError("invalid_style_id", "风格编号使用 S001 等形式")
            revisions = [x["revision"] for x in self.all("styles") if x["style_id"] == sid]
            revision = max(revisions, default=0) + 1
        else:
            nums = [int(x["style_id"][1:]) for x in self.all("styles")]
            sid, revision = f"S{max(nums, default=0) + 1:03d}", 1
        result = dict(payload, style_id=sid, revision=revision, style_key=f"{sid}-v{revision}", created_at=now())
        self.put("styles", result["style_key"], result, commit=False)
        return result

    def import_legacy(self):
        folder = self.config.root / "comfy_workflow/style_registry/styles"
        imported = []
        if not folder.exists():
            return imported
        for path in folder.glob("S*-v*.json"):
            value = read_json(path)
            if "style_key" not in value or self.get("styles", value["style_key"]):
                continue
            value["origin"] = {"legacy_path": str(path), "imported_at": now()}
            self.put("styles", value["style_key"], value)
            write_json(self.config.data / "styles" / path.name, value)
            imported.append(value["style_key"])
        return imported
