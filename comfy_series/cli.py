from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from . import __version__
from . import assets, engine, library
from .client import ComfyClient
from .common import Config, SeriesError, Store, identifier, now, read_json, write_json
from .ingest import ingest
from .web import render, serve
from .workflow import from_canvas, to_canvas, validate_graph


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise SeriesError("invalid_arguments", message)


def parser():
    p = JsonArgumentParser(description="Comfy Series: JSON-output tools for Codex")
    p.add_argument("--project", help="项目根目录，默认使用本工具所在项目")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("doctor")
    i = sub.add_parser("ingest")
    i.add_argument("--source", required=True)
    i.add_argument("--role", default="context")
    i.add_argument("--text-file")
    i.add_argument("--pages", help="PDF预览页码，逗号分隔")
    s = sub.add_parser("styles")
    s.add_argument("action", choices=["list", "show", "create", "baseline"])
    s.add_argument("--style")
    s.add_argument("--file")
    s.add_argument("--job")
    s.add_argument("--material", help="用户选定的外部基准图素材编号")
    s.add_argument("--viewed-path", help="已实际查看的素材图路径")
    s.add_argument("--index", type=int, default=0)
    s = sub.add_parser("series")
    s.add_argument("action", choices=["list", "create", "budget"])
    s.add_argument("--style")
    s.add_argument("--id")
    s.add_argument("--name", default="")
    s.add_argument("--budget-gb", type=float, default=30)
    s.add_argument("--isolated", action="store_true")
    a = sub.add_parser("assets")
    a.add_argument("action", choices=["inventory", "hf-search", "hf-spec", "download", "resolve"])
    a.add_argument("--query", default="")
    a.add_argument("--repo")
    a.add_argument("--filename")
    a.add_argument("--category")
    a.add_argument("--name")
    a.add_argument("--revision", default="main")
    a.add_argument("--file")
    a.add_argument("--series")
    a.add_argument("--hash", action="store_true")
    a.add_argument("--save")
    l = sub.add_parser("library")
    l.add_argument("action", choices=["import", "search", "validate"])
    l.add_argument("--file")
    l.add_argument("--query", default="")
    l.add_argument("--status")
    l.add_argument("--id")
    w = sub.add_parser("workflow")
    w.add_argument("action", choices=["validate", "convert"])
    w.add_argument("--file", required=True)
    w.add_argument("--save")
    q = sub.add_parser("prepare")
    q.add_argument("--request", required=True)
    q.add_argument("--switch-keep", action="store_true")
    q.add_argument("--switch-delete-plan", help="已经用户确认并执行的清理计划编号")
    q.add_argument("--confirmation-file")
    r = sub.add_parser("run")
    r.add_argument("--job", required=True)
    r.add_argument("--indices")
    r.add_argument("--patch")
    r = sub.add_parser("review")
    r.add_argument("--job", required=True)
    r.add_argument("--file", required=True)
    s = sub.add_parser("status")
    s.add_argument("--job")
    a = sub.add_parser("abandon")
    a.add_argument("--job", required=True)
    a.add_argument("--index", type=int, required=True)
    a.add_argument("--reason", required=True)
    c = sub.add_parser("cleanup")
    c.add_argument("action", choices=["plan", "execute"])
    c.add_argument("--ids", required=True)
    c.add_argument("--plan")
    c.add_argument("--confirmation-file")
    r = sub.add_parser("report")
    r.add_argument("--save")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8191)
    return p


def confirmation(path):
    if not path:
        return ""
    return read_json(path).get("human_confirmation", "")


def require(args, *names):
    for name in names:
        if not getattr(args, name, None):
            raise SeriesError("argument_required", f"此操作需要 --{name.replace('_', '-')}")


def dispatch(args, config, store):
    cmd = args.command
    if cmd == "init":
        imported = store.import_legacy()
        inventory = assets.inventory(store)
        if store.get("styles", "S001-v1") and not store.get("series", "SC001"):
            store.create_series("S001-v1", "冷色收容设施摄影", "SC001")
        seed = config.data / "library_seed.json"
        result = library.import_library(store, seed) if seed.exists() else {"count": 0}
        return {"version": __version__, "root": str(config.root), "imported_styles": imported, "model_count": len(inventory),
                "library": result, "database": str(config.data / "comfy_series.sqlite")}
    if cmd == "doctor":
        client = ComfyClient(config)
        stats, info = client.stats(), client.info()
        inventory = assets.inventory(store)
        return {"server": config.server, "stats": stats, "node_count": len(info), "queue": client.queue(),
                "features": {"txt2img": "EmptyLatentImage" in info, "img2img": "VAEEncodeTiled" in info,
                             "exact_size": "ImageScale" in info, "ipadapter_nodes": "IPAdapterAdvanced" in info,
                             "ipadapter_weights": any(x["category"] == "ipadapter" for x in inventory),
                             "clip_vision_weights": any(x["category"] == "clip_vision" for x in inventory)},
                "runtime_capabilities": store.all("capabilities"),
                "models": [{k:x.get(k) for k in ("id", "name", "category", "bytes", "managed")} for x in inventory]}
    if cmd == "ingest":
        pages = list(map(int, args.pages.split(","))) if args.pages else None
        text = Path(args.text_file).read_text(encoding="utf-8-sig") if args.text_file else None
        return ingest(store, args.source, args.role, pages, text)
    if cmd == "styles":
        if args.action == "list":
            return store.all("styles")
        if args.action == "show":
            require(args, "style")
            return store.resolve_style(args.style)
        if args.action == "create":
            require(args, "file")
            payload = read_json(args.file)
            if not payload.get("locked_generation_settings", {}).get("checkpoint"):
                raise SeriesError("style_checkpoint_required", "风格需绑定checkpoint")
            return store.create_style(payload)
        require(args, "style")
        style = store.resolve_style(args.style)
        if args.material:
            material = store.need("materials", args.material)
            if material["kind"] != "image" or not args.viewed_path or Path(args.viewed_path).resolve() != Path(material["path"]).resolve():
                raise SeriesError("baseline_review", "外部基准图须先导入并实际查看，记录viewed-path")
            style["visual_baseline"] = {"image_path":material["path"], "material_id":material["id"], "sha256":material["sha256"], "source":"user_selected_reference"}
            store.put("styles", style["style_key"], style)
            write_json(config.data / "styles" / (style["style_key"] + ".json"), style)
            return style
        require(args, "job")
        job = store.need("jobs", args.job)
        if job["style_key"] != style["style_key"]:
            raise SeriesError("baseline_style", "基准图片必须来自相同风格版本")
        image = job["images"][args.index]
        if not (image.get("review") or {}).get("accepted"):
            raise SeriesError("baseline_review", "先查看并评审基准图片")
        style["visual_baseline"] = {"image_path": image["best_path"], "job_id": args.job, "image_index": args.index}
        store.put("styles", style["style_key"], style)
        write_json(config.data / "styles" / (style["style_key"] + ".json"), style)
        return style
    if cmd == "series":
        if args.action == "list":
            return store.all("series")
        if args.action == "budget":
            require(args, "id")
            return store.budget(args.id)
        style = store.resolve_style(args.style) if args.style else None
        if not 0 < args.budget_gb <= 30:
            raise SeriesError("budget_limit", "本项目默认每系列最多30GB；改变上限需明确更新配置与用户约定")
        return store.create_series(style["style_key"] if style else None, args.name, args.id,
                                   round(args.budget_gb * 1e9), args.isolated)
    if cmd == "assets":
        if args.action == "inventory":
            return assets.inventory(store, args.hash)
        if args.action == "hf-search":
            return assets.search_hf(args.query)
        if args.action == "hf-spec":
            require(args, "repo", "filename", "category")
            spec = assets.hf_file_spec(args.repo, args.filename, args.category, args.name, args.revision)
            if args.save:
                write_json(args.save, spec)
            return spec
        require(args, "file", "series")
        value = read_json(args.file)
        if args.action == "download":
            return assets.download(store, value, args.series)
        return assets.resolve_candidates(store, value, args.series)
    if cmd == "library":
        if args.action == "import":
            require(args, "file")
            return library.import_library(store, args.file)
        if args.action == "search":
            return library.search_library(store, args.query, args.status)
        info = ComfyClient(config).info()
        if args.id:
            return library.validate_source(store, args.id, info)
        return [library.validate_source(store, x["id"], info) for x in store.all("sources") if x.get("cached_path")]
    if cmd == "workflow":
        value, info = read_json(args.file), ComfyClient(config).info()
        graph = from_canvas(value, info) if "nodes" in value else value
        result = validate_graph(graph, info)
        if args.action == "convert":
            require(args, "save")
            if "nodes" in value:
                write_json(args.save, graph)
            else:
                write_json(args.save, to_canvas(graph, info))
            result["saved"] = str(Path(args.save).resolve())
        return result
    if cmd == "prepare":
        if args.switch_keep and args.switch_delete_plan:
            raise SeriesError("switch_decision_conflict", "保留与删除选择不能同时使用")
        return engine.prepare(store, read_json(args.request), "delete" if args.switch_delete_plan else "keep" if args.switch_keep else None,
                              confirmation(args.confirmation_file), args.switch_delete_plan)
    if cmd == "run":
        return engine.run(store, args.job, list(map(int, args.indices.split(","))) if args.indices else None,
                          read_json(args.patch) if args.patch else None)
    if cmd == "review":
        return engine.review(store, args.job, read_json(args.file))
    if cmd == "status":
        return store.need("jobs", args.job) if args.job else store.all("jobs")
    if cmd == "abandon":
        return engine.abandon(store, args.job, args.index, args.reason)
    if cmd == "cleanup":
        ids = args.ids.split(",")
        if args.action == "plan":
            return assets.cleanup_plan(store, ids)
        require(args, "plan", "confirmation_file")
        return assets.cleanup_execute(store, args.plan, ids, confirmation(args.confirmation_file), ComfyClient(config))
    if cmd == "report":
        path = Path(args.save) if args.save else config.data / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(store), encoding="utf-8")
        return {"path": str(path.resolve()), "serve_url": "http://127.0.0.1:8191/"}
    if cmd == "serve":
        return serve(config, args.port)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    store = None
    try:
        args = parser().parse_args()
        config = Config(args.project)
        store = Store(config)
        result = dispatch(args, config, store)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    except SeriesError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc), "details": exc.details}}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "internal_error", "type": type(exc).__name__, "message": "读取记录或执行操作失败，请检查参数与项目状态"}}, ensure_ascii=False))
        return 3
    finally:
        if store is not None:
            store.db.close()
    return 0
