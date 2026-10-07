from pathlib import Path
from .common import SeriesError, digest, now, read_json, write_json, within
from .workflow import from_canvas, validate_graph


def import_library(store, path):
    records = read_json(path)
    if not isinstance(records, list):
        records = [records]
    imported = []
    for item in records:
        if not {"id", "title", "url"}.issubset(item):
            raise SeriesError("library_fields", "资料需包含id、title、url")
        old = store.get("sources", item["id"], {})
        record = dict(old, **item)
        record.setdefault("validation_status", "unverified")
        cached = record.get("cached_path")
        if cached:
            resolved = (store.config.root / cached).resolve()
            if not within(resolved, store.config.data / "library") or not resolved.is_file():
                raise SeriesError("library_cache_path", "缓存资料应在data/library内")
            record["cache_sha256"] = digest(resolved)
        if old.get("validation_status") in ("schema_validated", "runtime_passed") and old.get("cache_sha256") == record.get("cache_sha256") and old.get("revision") == record.get("revision"):
            record["validation_status"] = old["validation_status"]
        store.put("sources", record["id"], record)
        imported.append(record["id"])
    return {"imported": imported, "count": len(imported)}


def search_library(store, query="", status=None):
    values = store.all("sources")
    if query:
        words = query.casefold().split()
        values = [x for x in values if all(w in str(x).casefold() for w in words)]
    if status:
        values = [x for x in values if x.get("validation_status") == status]
    return values


def validate_source(store, source_id, info):
    source = store.need("sources", source_id)
    if not source.get("cached_path"):
        raise SeriesError("workflow_cache_missing", "此来源没有缓存工作流")
    graph = read_json(store.config.root / source["cached_path"])
    missing = []
    if "nodes" in graph:
        missing = sorted({x["type"] for x in graph["nodes"] if x["type"] not in info and x["type"] not in ("Note", "MarkdownNote")})
    else:
        missing = sorted({x.get("class_type") for x in graph.values() if x.get("class_type") not in info})
    try:
        if missing:
            raise SeriesError("missing_node", "模板需要未安装节点", missing)
        api = from_canvas(graph, info) if "nodes" in graph else graph
        validation = validate_graph(api, info)
        source.update(validation_status="runtime_passed" if source.get("validation_status") == "runtime_passed" else "schema_validated", validation=validation)
        path = store.config.data / "library" / "validated" / (source_id + ".api.json")
        write_json(path, api)
        source["validated_api_path"] = str(path.relative_to(store.config.root))
    except SeriesError as exc:
        source.update(validation_status="unverified", validation={"code": exc.code, "message": str(exc), "details": exc.details})
    source["validated_at"] = now()
    store.put("sources", source_id, source)
    return source
