"""Byte-preserving local image delivery. Comfy records are read-only inputs."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import time

from PIL import Image

MANIFEST = "image-manifest.json"
LOCK = ".image-delivery.lock"


class DeliveryError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def error(exc):
    return {"code": getattr(exc, "code", "io_error"), "message": str(exc)}


def now():
    return datetime.now(timezone.utc).isoformat()


def absolute(value):
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise DeliveryError("absolute_path_required", f"需要完整绝对路径：{value!r}")
    return Path(value).resolve()


def linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    with path.open(encoding="utf-8-sig") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise DeliveryError("invalid_json", f"JSON 须为对象：{path}")
    return data


def same_path(value, path):
    return isinstance(value, str) and value != "" and absolute(value) == path


def accepted(review):
    return isinstance(review, dict) and review.get("accepted") is True


def verify_review(review, index, number, source):
    checks = review.get("checks", {}) if isinstance(review, dict) else {}
    if not (accepted(review) and review.get("index") == index and review.get("round") == number
            and same_path(review.get("viewed_path"), source)
            and isinstance(checks, dict) and {"subject", "composition", "style", "defects"} <= checks.keys()
            and all(v == "pass" for v in checks.values())):
        raise DeliveryError("comfy_review_mismatch", "所选图片的评审、轮次或实际查看路径不一致")


def comfy_sources(job_path):
    job = read_json(job_path)
    if not isinstance(job.get("images"), list) or not job.get("id"):
        raise DeliveryError("invalid_comfy_job", "任务记录缺少编号或图片列表")
    sources, skipped = [], []
    images = sorted(job["images"], key=lambda x: x["index"])
    if len({x["index"] for x in images}) != len(images):
        raise DeliveryError("invalid_comfy_job", "任务记录存在重复图片索引")
    for image in images:
        index = image["index"]
        if not accepted(image.get("review")):
            skipped.append({"image_index": index, "reason": "not_accepted"})
            continue
        descriptor = {"source_path": image.get("best_path"), "provenance": {
            "type": "comfy_series", "job_id": job["id"], "series_id": job.get("series_id"),
            "style_key": job.get("style_key"), "image_index": index, "job_path": str(job_path)}}
        try:
            source = absolute(image.get("best_path"))
            matches = [a for a in image.get("attempts", []) if same_path(a.get("path"), source)]
            if len(matches) != 1:
                raise DeliveryError("comfy_attempt_missing", "无法唯一匹配 best_path 的轮次")
            attempt = matches[0]
            number = attempt["number"]
            folder = absolute(attempt["folder"])
            if source.parent != folder or attempt.get("status") != "rendered":
                raise DeliveryError("comfy_attempt_mismatch", "轮次目录或执行状态与图片不一致")
            manifest = read_json(folder / "manifest.json")
            recorded = manifest.get("attempt", {})
            if not (manifest.get("job_id") == job["id"] and manifest.get("series_id") == job.get("series_id")
                    and manifest.get("style_key") == job.get("style_key") and recorded.get("number") == number
                    and recorded.get("status") == "rendered" and same_path(recorded.get("path"), source)):
                raise DeliveryError("comfy_manifest_mismatch", "轮次清单与任务来源不一致")
            for review in (image["review"], attempt.get("visual_review"), manifest.get("visual_review")):
                verify_review(review, index, number, source)
            for record in (attempt, recorded):
                technical = record.get("technical_checks", {})
                if any(technical.get(k) != "passed" for k in ("execution", "dimensions", "png")):
                    raise DeliveryError("comfy_technical_checks", "记录中的技术检查未通过")
                if not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
                    raise DeliveryError("comfy_checksum_missing", "任务记录缺少有效 SHA-256")
            if attempt["sha256"] != recorded["sha256"] or attempt.get("output_size") != recorded.get("output_size"):
                raise DeliveryError("comfy_manifest_mismatch", "两份轮次记录的哈希或尺寸不同")
            descriptor.update(source_path=str(source), expected_sha256=attempt["sha256"],
                              expected_size=attempt["output_size"], expected_format="PNG")
            descriptor["provenance"]["round"] = number
        except (DeliveryError, OSError, ValueError, KeyError, TypeError) as exc:
            descriptor["error"] = error(exc)
        sources.append(descriptor)
    return sources, skipped


def select_sources(request):
    if ("sources" in request) == ("comfy_job" in request):
        raise DeliveryError("source_selection", "sources 与 comfy_job 须且只能提供一种")
    if "comfy_job" in request:
        return comfy_sources(absolute(request["comfy_job"]))
    values = request["sources"]
    if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
        raise DeliveryError("invalid_sources", "sources 须为非空图片路径数组")
    return [{"source_path": v, "provenance": {"type": "local"}} for v in values], []


def describe(descriptor):
    if "error" in descriptor:
        raise DeliveryError(descriptor["error"]["code"], descriptor["error"]["message"])
    source = absolute(descriptor["source_path"])
    if not source.is_file():
        raise DeliveryError("source_missing", f"找不到源图片：{source}")
    before = source.stat()
    with Image.open(source) as image:
        width, height, fmt = *image.size, image.format
        image.verify()
    checksum = sha256(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DeliveryError("source_changed", "读取期间源文件发生变化，请重试")
    if descriptor.get("expected_sha256", checksum) != checksum:
        raise DeliveryError("comfy_checksum_mismatch", "源图片与任务记录的 SHA-256 不一致")
    if descriptor.get("expected_size", [width, height]) != [width, height] or descriptor.get("expected_format", fmt) != fmt:
        raise DeliveryError("comfy_dimensions_mismatch", "源图片的格式或尺寸与任务记录不同")
    return {"source_path": str(source), "sha256": checksum, "bytes": after.st_size,
            "width": width, "height": height, "format": fmt, "provenance": descriptor["provenance"]}


def inspect(request):
    descriptors, skipped = select_sources(request)
    items, errors = [], []
    for position, descriptor in enumerate(descriptors):
        try:
            items.append(dict(describe(descriptor), status="ready", position=position))
        except (DeliveryError, OSError, ValueError) as exc:
            detail = dict(error(exc), position=position, source_path=descriptor.get("source_path"))
            errors.append(detail)
            items.append({"status": "failed", "position": position, "source_path": descriptor.get("source_path"), "error": detail})
    return {"ok": not errors, "items": items, "skipped": skipped, "errors": errors}


def validate_name(name):
    if (not isinstance(name, str) or not name or name in (".", "..") or name[-1] in " ."
            or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
            or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]", name.split(".")[0], re.IGNORECASE)
            or len(name.encode("utf-16-le")) // 2 > 255):
        raise DeliveryError("invalid_filename", f"非法 Windows 文件名：{name!r}")
    return name


def filename(name, item):
    validate_name(name)
    Image.init()
    extensions = {ext for ext, fmt in Image.registered_extensions().items() if fmt == item["format"]}
    suffix = Path(name).suffix.lower()
    if suffix:
        if suffix not in extensions:
            raise DeliveryError("extension_mismatch", f"文件名 {name} 的扩展名不匹配实际格式 {item['format']}")
        return name
    source_suffix = Path(item["source_path"]).suffix.lower()
    preferred = {"JPEG": ".jpg", "PNG": ".png", "TIFF": ".tiff"}.get(item["format"])
    extension = source_suffix if source_suffix in extensions else preferred or next(iter(sorted(extensions)), None)
    if not extension:
        raise DeliveryError("extension_unknown", f"无法确定 {item['format']} 的扩展名")
    return validate_name(name + extension)


def request_names(request, count):
    if ("names" in request) == ("name_prefix" in request):
        raise DeliveryError("name_selection", "names 与 name_prefix 须且只能提供一种")
    if "names" in request:
        values = request["names"]
        if not isinstance(values, list) or len(values) != count or not all(isinstance(n, str) for n in values):
            raise DeliveryError("name_count", "names 数量须与选定的源图片数量相等")
        return values
    prefix = validate_name(request["name_prefix"])
    if Path(prefix).suffix:
        raise DeliveryError("invalid_prefix", "统一前缀不含扩展名，请使用 names 指定完整名称")
    return [prefix if count == 1 else f"{prefix}_{i + 1:03d}" for i in range(count)]


@contextmanager
def manifest_lock(folder, timeout=10):
    lock_path = folder / LOCK
    if linked(lock_path):
        raise DeliveryError("unsafe_lock", "锁文件是链接，无法安全使用")
    with lock_path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        acquired = False
        deadline = time.monotonic() + timeout
        try:
            while not acquired:
                try:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if time.monotonic() >= deadline:
                        raise DeliveryError("manifest_busy", "等待清单写入锁超时，可稍后重试")
                    time.sleep(0.05)
            yield
        finally:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def load_manifest(path):
    if linked(path):
        raise DeliveryError("unsafe_manifest", "清单文件是链接")
    data = read_json(path) if path.exists() else {"schema_version": 1, "items": []}
    if data.get("schema_version") != 1 or not isinstance(data.get("items"), list):
        raise DeliveryError("invalid_manifest", "无法读取现有清单版本或条目")
    for entry in data["items"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("delivery_id"), str) or not isinstance(entry.get("target_path"), str):
            raise DeliveryError("invalid_manifest", "清单条目结构不完整")
    return data


def atomic_manifest(path, data):
    handle, temporary = tempfile.mkstemp(prefix=".image-manifest-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if linked(path):
            raise DeliveryError("unsafe_manifest", "清单文件已变为链接")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def remove_owned(path):
    """Remove only a caller-owned staging/rollback file, including read-only copies."""
    if path.exists():
        path.chmod(stat.S_IREAD | stat.S_IWRITE)
        path.unlink()


def copy_image(item, folder, requested):
    source = Path(item["source_path"])
    base = Path(requested)
    staged = None
    try:
        for number in range(100000):
            name = requested if number == 0 else f"{base.stem}_{number:03d}{base.suffix}"
            validate_name(name)
            target = folder / name
            if linked(target):
                raise DeliveryError("unsafe_target", f"目标文件是链接：{target}")
            if target.exists():
                if target.is_file() and sha256(target) == item["sha256"]:
                    return target, "reused"
                continue
            if staged is None:
                handle, temp_name = tempfile.mkstemp(prefix=".image-delivery-", suffix=".tmp", dir=folder)
                staged = Path(temp_name)
                with os.fdopen(handle, "wb") as output, source.open("rb") as original:
                    shutil.copyfileobj(original, output)
                    output.flush()
                    os.fsync(output.fileno())
                if sha256(staged) != item["sha256"] or sha256(source) != item["sha256"]:
                    raise DeliveryError("source_changed", "复制期间源图片改变，未交付")
                shutil.copystat(source, staged)
            try:
                if os.name == "nt":
                    # Windows rename refuses an existing destination, including a competing writer.
                    os.rename(staged, target)
                else:
                    os.link(staged, target)
                    staged.unlink()
                staged = None
                return target, "copied"
            except FileExistsError:
                continue
        raise DeliveryError("too_many_collisions", "同名文件过多，请换一个名称")
    finally:
        if staged is not None:
            remove_owned(staged)


def deliver(request):
    if request.get("delivery_confirmed") is not True:
        raise DeliveryError("confirmation_required", "请先展示交付模板，收到本次答复后设置 delivery_confirmed: true")
    inspected = inspect(request)
    if not inspected["items"]:
        raise DeliveryError("no_accepted_images", "没有验收通过的图片可正式交付")
    names = request_names(request, len(inspected["items"]))
    folder = absolute(request.get("destination_dir"))
    usage = request.get("usage", "")
    if not isinstance(usage, str):
        raise DeliveryError("invalid_usage", "usage 须为文字")
    prepared = []
    for item, name in zip(inspected["items"], names):
        if item["status"] == "ready":
            try:
                item["requested_name"] = filename(name, item)
                prepared.append(item)
            except (DeliveryError, ValueError) as exc:
                item.update(status="failed", error=dict(error(exc), position=item["position"]))
    if prepared:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            for item in prepared:
                item.update(status="failed", error=dict(error(exc), position=item["position"]))
            return {"ok": False, "items": inspected["items"], "skipped": inspected["skipped"],
                    "errors": [i["error"] for i in inspected["items"]], "manifest_path": None}
        with manifest_lock(folder):
            manifest_path = folder / MANIFEST
            manifest = load_manifest(manifest_path)
            for item in prepared:
                target, status = None, None
                try:
                    target, status = copy_image(item, folder, item["requested_name"])
                    # Verify the published file before registering it.
                    if sha256(target) != item["sha256"]:
                        raise DeliveryError("target_changed", "登记前目标图片改变")
                    identity = json.dumps([item["source_path"], target.name, item["sha256"], item["provenance"]], sort_keys=True)
                    delivery_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
                    previous = next((e for e in manifest["items"] if e["delivery_id"] == delivery_id), None)
                    entry = {k: item[k] for k in ("source_path", "sha256", "bytes", "width", "height", "format", "provenance")}
                    entry.update(delivery_id=delivery_id, target_path=target.name,
                                 usage=usage if "usage" in request else previous.get("usage", "") if previous else "",
                                 created_at=previous["created_at"] if previous else now(), updated_at=now())
                    updated = dict(manifest, items=[e for e in manifest["items"] if e["delivery_id"] != delivery_id] + [entry], updated_at=now())
                    atomic_manifest(manifest_path, updated)
                    manifest = updated
                    item.update(status=status, target_path=str(target), delivery_id=delivery_id)
                except (DeliveryError, OSError, ValueError, KeyError) as exc:
                    detail = error(exc)
                    if target is not None and status == "copied":
                        try:
                            if not linked(target) and sha256(target) == item["sha256"]:
                                remove_owned(target)
                            else:
                                detail["unregistered_path"] = str(target)
                        except OSError:
                            detail["unregistered_path"] = str(target)
                    item.update(status="failed", error=dict(detail, position=item["position"]))
    items = inspected["items"]
    errors = [item["error"] for item in items if item["status"] == "failed"]
    return {"ok": not errors, "items": items, "skipped": inspected["skipped"], "errors": errors,
            "manifest_path": str(folder / MANIFEST) if any(i["status"] in ("copied", "reused") for i in items) else None}


def find(root, query=""):
    root = absolute(root)
    if not root.is_dir():
        raise DeliveryError("project_missing", "指定项目目录不存在")
    items, errors = [], []
    def walk_error(exc):
        errors.append(error(exc))
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        folder = Path(directory)
        dirs[:] = sorted(d for d in dirs if d not in (".git", ".venv", "node_modules") and not linked(folder / d))
        if MANIFEST not in files:
            continue
        try:
            manifest = load_manifest(folder / MANIFEST)
            for entry in manifest["items"]:
                searchable = json.dumps({k: entry.get(k) for k in ("target_path", "source_path", "usage", "provenance")}, ensure_ascii=False).casefold()
                if query.casefold() not in searchable and query.casefold() not in str(folder).casefold():
                    continue
                relative = Path(entry["target_path"])
                target = folder / relative
                unsafe = relative.is_absolute() or len(relative.parts) != 1 or relative.name in (".", "..") or linked(target)
                if not unsafe:
                    unsafe = not target.resolve().is_relative_to(root)
                result = dict(entry, manifest_path=str(folder / MANIFEST), target_absolute_path=str(target), exists=False)
                if unsafe:
                    result["integrity"] = "unsafe"
                else:
                    result["exists"] = target.is_file()
                    try:
                        result["integrity"] = "missing" if not result["exists"] else "valid" if sha256(target) == entry.get("sha256") else "changed"
                    except OSError:
                        result["integrity"] = "unreadable"
                items.append(result)
        except (DeliveryError, OSError, ValueError) as exc:
            errors.append(dict(error(exc), manifest_path=str(folder / MANIFEST)))
    return {"ok": not errors, "items": items, "errors": errors}


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        raise DeliveryError("invalid_arguments", message)


def main(argv=None):
    try:
        parser = JsonParser(description="Local image delivery: inspect, deliver, find")
        commands = parser.add_subparsers(dest="command", required=True)
        for command in ("inspect", "deliver"):
            commands.add_parser(command).add_argument("--file", required=True)
        search = commands.add_parser("find")
        search.add_argument("--root", required=True)
        search.add_argument("--query", default="")
        args = parser.parse_args(argv)
        if args.command == "find":
            result = find(args.root, args.query)
        else:
            request = read_json(absolute(args.file))
            result = inspect(request) if args.command == "inspect" else deliver(request)
    except Exception as exc:
        result = {"ok": False, "items": [], "errors": [error(exc)]}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
