from __future__ import annotations

import hashlib
import json
import struct
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse
import httpx
from huggingface_hub import HfApi
from filelock import FileLock
from .common import SeriesError, digest, identifier, now, within, write_json, external_http


def inspect_weights(path):
    """Cheap structural check; only the real Comfy execution proves compatibility."""
    path = Path(path)
    if path.suffix.lower() != ".safetensors":
        return {"status": "not_checked", "reason": "format_requires_runtime"}
    try:
        with path.open("rb") as stream:
            size = struct.unpack("<Q", stream.read(8))[0]
            if not 1 <= size <= min(100_000_000, path.stat().st_size - 8):
                raise ValueError("invalid_header_length")
            header = json.loads(stream.read(size))
        tensors = [v for k, v in header.items() if k != "__metadata__"]
        if not tensors or any(not isinstance(v, dict) or "data_offsets" not in v for v in tensors):
            raise ValueError("invalid_tensor_metadata")
        payload = path.stat().st_size - 8 - size
        if any(not 0 <= v["data_offsets"][0] <= v["data_offsets"][1] <= payload for v in tensors):
            raise ValueError("invalid_tensor_offsets")
        return {"status": "header_valid", "tensors": len(tensors)}
    except (ValueError, KeyError, TypeError, struct.error, OSError) as exc:
        return {"status": "invalid", "reason": type(exc).__name__}


def asset_id(category, path):
    return "A-" + hashlib.sha256((category + str(Path(path).resolve()).lower()).encode()).hexdigest()[:16]


def inventory(store, verify_hash=False):
    result = []
    for category in ("checkpoints", "loras", "clip_vision", "ipadapter", "upscale_models", "controlnet", "vae"):
        for folder in store.config.model_dirs(category):
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}:
                    continue
                key = asset_id(category, path)
                entry = store.get("assets", key, {})
                entry.update(id=key, category=category, name=path.relative_to(folder).as_posix(), path=str(path.resolve()),
                             bytes=path.stat().st_size, available=True, managed=within(path, store.config.model_root))
                if verify_hash and not entry.get("sha256"):
                    entry["sha256"] = digest(path)
                entry.setdefault("origin", "preexisting")
                entry["file_validation"] = inspect_weights(path)
                store.put("assets", key, entry)
                result.append(entry)
    # Preserve historical records, but accurately mark absent files.
    for item in store.all("assets"):
        if not Path(item["path"]).is_file() and item.get("available"):
            store.put("assets", item["id"], dict(item, available=False))
    return result


def find_asset(store, category, name):
    for folder in store.config.model_dirs(category):
        path = folder / name
        if within(path, folder) and path.is_file():
            validation = inspect_weights(path)
            if validation["status"] == "invalid":
                raise SeriesError("model_invalid", "模型文件结构无效，保留文件并选择替代", {"name": name, "validation": validation})
            entry = store.get("assets", asset_id(category, path))
            if entry:
                return entry
            entry = {"id": asset_id(category, path), "category": category, "name": name,
                     "path": str(path.resolve()), "bytes": path.stat().st_size,
                     "available": True, "managed": within(path, store.config.model_root), "origin": "preexisting"}
            return store.put("assets", entry["id"], entry)
    raise SeriesError("model_missing", "本机缺少模型", {"category": category, "name": name})


def hf_file_spec(repo, filename, category, name=None, revision="main"):
    api = HfApi(token=False)
    try:
        info = api.model_info(repo, revision=revision, files_metadata=True)
    except Exception as exc:
        raise SeriesError("model_source_unavailable", "无法读取公开模型资料，可选择替代模型", {"repo": repo}) from exc
    if info.gated:
        raise SeriesError("model_gated", "模型需要访问授权；本地免费路线选择公开替代", {"repo": repo})
    sibling = next((x for x in info.siblings if x.rfilename == filename), None)
    if not sibling:
        raise SeriesError("model_file_missing", "模型仓库中未找到权重文件", {"repo": repo, "file": filename})
    lfs = sibling.lfs
    checksum = getattr(lfs, "sha256", None) if lfs else None
    if isinstance(lfs, dict):
        checksum = lfs.get("sha256")
    return {"repo_id": repo, "revision": info.sha, "filename": filename,
            "url": f"https://huggingface.co/{repo}/resolve/{info.sha}/{filename}",
            "source_url": f"https://huggingface.co/{repo}/blob/{info.sha}/{filename}",
            "category": category, "name": name or Path(filename).name,
            "expected_bytes": sibling.size, "sha256": checksum,
            "license": getattr(info.card_data, "license", None) if info.card_data else None}


def search_hf(query, limit=10):
    try:
        models = HfApi(token=False).list_models(search=query, limit=min(limit, 30), sort="downloads")
        return [{"id": x.id, "url": f"https://huggingface.co/{x.id}", "tags": x.tags or [],
                 "downloads": x.downloads, "gated": x.gated} for x in models]
    except Exception as exc:
        raise SeriesError("search_unavailable", "Hugging Face 搜索不可用，请用官网检索并记录原始页面") from exc


def download(store, spec, series_id, attempts=3):
    category, name = spec["category"], spec["name"]
    store.config.model_dirs(category)
    if Path(name).name != name or name.startswith("."):
        raise SeriesError("invalid_model_name", "下载目标使用单个模型文件名")
    folder = store.config.model_root / category
    folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(folder / (name + ".download.lock")), timeout=30):
        try:
            return _download_locked(store, spec, series_id, attempts)
        except (httpx.HTTPError, OSError) as exc:
            raise SeriesError("download_interrupted", "下载访问失败，保留已有断点并选择替代", {"type": type(exc).__name__}) from exc


def _download_locked(store, spec, series_id, attempts=3):
    category, name = spec["category"], spec["name"]
    store.config.model_dirs(category)  # category whitelist
    if Path(name).name != name or name.startswith("."):
        raise SeriesError("invalid_model_name", "下载目标使用单个模型文件名")
    target = store.config.model_root / category / name
    if target.exists():
        if spec.get("expected_bytes") and target.stat().st_size != spec["expected_bytes"]:
            raise SeriesError("existing_size_mismatch", "已有同名文件大小不符，保留文件并选择不同名称")
        if spec.get("sha256") and digest(target) != spec["sha256"]:
            raise SeriesError("existing_hash_mismatch", "已有同名文件与来源不符，保留原文件并选择不同名称")
        asset = find_asset(store, category, name)
        return {"asset": asset, "reused": True, "budget": store.budget(series_id)}
    parsed = urlparse(spec["url"])
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        raise SeriesError("invalid_download_url", "模型下载使用 HTTP(S) 地址，认证信息不得写入 URL")
    size = spec.get("expected_bytes")
    with external_http(store.config, spec["url"], follow_redirects=True, timeout=60) as http:
        if not isinstance(size, int) or size <= 0:
            head = http.head(spec["url"])
            if head.status_code in (401, 403, 404):
                raise SeriesError("model_source_unavailable", "模型不可公开下载，选择替代模型", {"http_status": head.status_code})
            if not head.headers.get("content-length"):
                raise SeriesError("unknown_model_size", "无法确定模型大小，需先核实文件信息以检查预算")
            size = int(head.headers["content-length"])
        if shutil.disk_usage(store.config.data).free < size + 2_000_000_000:
            raise SeriesError("disk_space", "磁盘剩余空间不足")
        target.parent.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256((spec["url"] + str(target)).encode()).hexdigest()[:20]
        part = target.with_name(target.name + ".part")
        meta_path = target.with_name(target.name + ".part.json")
        if part.exists() and meta_path.exists():
            from .common import read_json
            if read_json(meta_path).get("fingerprint") != fingerprint:
                raise SeriesError("partial_source_mismatch", "已有断点属于不同来源，不能拼接")
        elif part.exists():
            raise SeriesError("partial_without_provenance", "断点文件缺少来源记录，不能自动拼接")
        prior = next((x for x in store.all("downloads") if x.get("fingerprint") == fingerprint and x["status"] != "complete"), None)
        did = prior["id"] if prior else "D-" + uuid.uuid4().hex[:16]
        with store.transaction():
            budget = store.budget(series_id)
            old_reservation = prior.get("reserved_bytes", 0) if prior and prior["series_id"] == series_id else 0
            if prior and prior["series_id"] != series_id:
                raise SeriesError("download_owned_by_other_series", "已有断点下载属于其他系列，先恢复该系列")
            if size > budget["remaining"] + old_reservation:
                raise SeriesError("download_budget", "超过本系列新增下载预算，请复用已有或更小模型", {"required": size, **budget})
            entry = {"id": did, "fingerprint": fingerprint, "series_id": series_id, "reserved_bytes": size,
                     "status": "reserved", "spec": spec, "part_path": str(part), "created_at": (prior or {}).get("created_at", now())}
            store.put("downloads", did, entry, commit=False)
        write_json(meta_path, {"fingerprint": fingerprint, "expected_bytes": size, "sha256": spec.get("sha256")})
        errors = []
        for attempt in range(attempts):
            offset = part.stat().st_size if part.exists() else 0
            if offset == size:
                break
            if offset > size:
                part.unlink()
                offset = 0
            try:
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with http.stream("GET", spec["url"], headers=headers) as response:
                    if response.status_code in (401, 403, 404):
                        if not part.exists() or part.stat().st_size == 0:
                            store.put("downloads", did, dict(entry, reserved_bytes=0, status="unavailable"))
                        raise SeriesError("model_source_unavailable", "模型不可下载，选择替代模型", {"http_status": response.status_code})
                    response.raise_for_status()
                    if "text/html" in response.headers.get("content-type", ""):
                        raise SeriesError("not_model_file", "下载地址返回网页而非权重")
                    if offset and response.status_code == 206:
                        content_range = response.headers.get("content-range", "")
                        if not re.match(rf"bytes {offset}-\d+/{size}$", content_range):
                            raise SeriesError("invalid_content_range", "服务器断点范围不匹配")
                        mode = "ab"
                    elif response.status_code == 200:
                        mode, offset = "wb", 0
                    else:
                        raise SeriesError("invalid_download_response", "服务器未返回完整文件或有效断点")
                    downloaded = offset
                    with part.open(mode) as output:
                        for block in response.iter_bytes(1024 * 1024):
                            downloaded += len(block)
                            if downloaded > size:
                                raise SeriesError("model_size_exceeded", "实际下载大小超出已核验大小与预算")
                            output.write(block)
                if part.stat().st_size != size:
                    raise httpx.ReadError("incomplete download")
                break
            except SeriesError:
                raise
            except (httpx.HTTPError, OSError) as exc:
                errors.append(type(exc).__name__)
                store.put("downloads", did, dict(entry, status="interrupted", errors=errors, attempt=attempt + 1))
                if attempt + 1 == attempts:
                    raise SeriesError("download_interrupted", "下载已保留断点，可用同一来源恢复或选择替代", {"download_id": did, "errors": errors}) from exc
                time.sleep(min(2 ** attempt, 4))
        checksum = digest(part)
        if spec.get("sha256") and checksum.lower() != spec["sha256"].lower():
            # Invalid temporary bytes are not installed as a model or reused.
            part.unlink()
            meta_path.unlink(missing_ok=True)
            store.put("downloads", did, dict(entry, status="hash_failed", reserved_bytes=0))
            raise SeriesError("model_hash_mismatch", "权重校验失败，已清理无效临时文件，可换来源")
        part.replace(target)
        meta_path.unlink(missing_ok=True)
        key = asset_id(category, target)
        asset = {"id": key, "category": category, "name": name, "path": str(target.resolve()), "bytes": size,
                 "sha256": checksum, "source": spec, "charged_series": series_id, "managed": True,
                 "available": True, "downloaded_at": now()}
        with store.transaction():
            store.put("assets", key, asset, commit=False)
            store.put("downloads", did, dict(entry, status="complete", reserved_bytes=0, committed_bytes=size,
                                              asset_id=key, completed_at=now()), commit=False)
        return {"asset": asset, "reused": False, "budget": store.budget(series_id)}


def resolve_candidates(store, candidates, series_id):
    reasons = []
    for candidate in candidates:
        try:
            spec = candidate
            try:
                local = find_asset(store, candidate["category"], candidate["name"])
                if candidate.get("sha256") and digest(local["path"]).lower() != candidate["sha256"].lower():
                    raise SeriesError("existing_hash_mismatch", "已有同名模型与固定来源哈希不符，选择其他候选")
                result = {"asset": local, "reused": True}
            except SeriesError as exc:
                if exc.code not in ("model_missing", "model_invalid"):
                    raise
                if "repo_id" in candidate and "url" not in candidate:
                    spec = hf_file_spec(candidate["repo_id"], candidate["filename"], candidate["category"], candidate["name"], candidate.get("revision", "main"))
                result = download(store, spec, series_id)
            result["alternatives_skipped"] = reasons
            store.event("model_resolution", series_id, {"selected": result["asset"]["id"], "alternatives_skipped": reasons})
            return result
        except SeriesError as exc:
            reasons.append({"name": candidate.get("name"), "code": exc.code, "message": str(exc)})
    raise SeriesError("no_usable_model", "候选模型均不可用，请继续检索或说明能力差距", reasons)


def cleanup_plan(store, asset_ids):
    items = []
    for aid in asset_ids:
        asset = store.need("assets", identifier(aid))
        path = Path(asset["path"])
        if not any(within(path, root) for root in store.config.model_dirs(asset["category"])):
            raise SeriesError("unsafe_model_path", "模型路径不在登记的模型目录")
        if not path.is_file():
            raise SeriesError("model_missing", "模型文件不存在")
        related = []
        for style in store.all("styles"):
            locked = style.get("locked_generation_settings", {})
            if aid in style.get("asset_ids", []) or asset["name"] in json_paths(locked) or str(path).replace("\\", "/") in json_paths(locked):
                related.append(style["style_key"])
        related_series = [x["id"] for x in store.all("series") if x.get("style_key") in related]
        items.append({"asset_id": aid, "path": str(path.resolve()), "bytes": path.stat().st_size,
                      "sha256": digest(path), "managed": asset.get("managed", False), "related_styles": related, "related_series": related_series})
    plan = {"id": "DEL-" + uuid.uuid4().hex[:12], "items": items, "created_at": now(), "status": "awaiting_human_confirmation"}
    store.put("cleanup", plan["id"], plan)
    return plan


def json_paths(value):
    if isinstance(value, dict):
        return sum((json_paths(x) for x in value.values()), [])
    if isinstance(value, list):
        return sum((json_paths(x) for x in value), [])
    return [value.replace("\\", "/")] if isinstance(value, str) else []


def cleanup_execute(store, plan_id, confirmed_ids, human_confirmation, client=None):
    if not human_confirmation.strip():
        raise SeriesError("confirmation_required", "必须先取得用户对具体文件的删除确认")
    plan = store.need("cleanup", identifier(plan_id))
    if plan["status"] != "awaiting_human_confirmation":
        raise SeriesError("cleanup_plan_used", "删除计划已使用")
    expected = {x["asset_id"] for x in plan["items"]}
    if not confirmed_ids or not set(confirmed_ids).issubset(expected):
        raise SeriesError("confirmation_mismatch", "确认的模型不属于此删除计划")
    if client:
        queue = client.queue()
        if queue.get("queue_running") or queue.get("queue_pending"):
            raise SeriesError("queue_busy", "队列正在使用模型，完成后再清理")
        client.free_memory()
    selected = [x for x in plan["items"] if x["asset_id"] in confirmed_ids]
    for item in selected:
        asset = store.need("assets", item["asset_id"])
        path = Path(item["path"])
        if Path(asset["path"]).resolve() != path.resolve() or not any(within(path, p) for p in store.config.model_dirs(asset["category"])):
            raise SeriesError("unsafe_model_path", "模型路径发生变化")
        if not path.is_file() or digest(path) != item["sha256"]:
            raise SeriesError("model_changed", "模型文件自确认清单生成后发生变化，请重新核对")
    for item in selected:
        Path(item["path"]).unlink()
        asset = store.need("assets", item["asset_id"])
        store.put("assets", item["asset_id"], dict(asset, available=False, deleted_at=now()))
    plan.update(status="complete", confirmed_ids=confirmed_ids, human_confirmation=human_confirmation, completed_at=now())
    store.put("cleanup", plan_id, plan)
    return plan
