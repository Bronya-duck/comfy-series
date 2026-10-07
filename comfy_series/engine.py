from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from pathlib import Path
from filelock import FileLock
from PIL import Image
from .assets import find_asset
from .client import ComfyClient
from .common import SeriesError, digest, identifier, now, write_json, read_json
from .ingest import ingest
from .workflow import build_graph, normalize_request, to_canvas, validate_graph


def bind_assets(store, style, persist=True):
    locked = style.get("locked_generation_settings", {})
    dependencies = [("checkpoints", locked["checkpoint"])]
    for x in locked.get("loras", []):
        dependencies.append(("loras", x["name"]))
    if locked.get("upscaling", {}).get("model"):
        dependencies.append(("upscale_models", locked["upscaling"]["model"]))
    for x in locked.get("reference_conditioning", []):
        dependencies.extend([("ipadapter", x["model"]), ("clip_vision", x["clip_vision"])])
    assets = []
    existing = {x["id"]: x for x in style.get("model_manifest", [])}
    for category, name in dependencies:
        asset = find_asset(store, category, name)
        path = Path(asset["path"])
        stamp = [path.stat().st_size, path.stat().st_mtime_ns]
        if not asset.get("sha256") or asset.get("file_stamp") != stamp:
            checksum = digest(path)
            if asset.get("sha256") and checksum != asset["sha256"]:
                raise SeriesError("model_file_changed", "登记的模型文件发生变化，请重新核查来源或建立版本", {"asset_id": asset["id"]})
            asset.update(sha256=checksum, file_stamp=stamp)
            store.put("assets", asset["id"], asset)
        if asset["id"] in existing and existing[asset["id"]]["sha256"] != asset["sha256"]:
            raise SeriesError("style_model_changed", "模型不再符合固定风格版本")
        assets.append(asset)
    style.update(asset_ids=[x["id"] for x in assets], model_manifest=assets)
    if persist:
        store.put("styles", style["style_key"], style)
        write_json(store.config.data / "styles" / (style["style_key"] + ".json"), style)
    return assets


def prepare(store, raw, switch_decision=None, human_confirmation="", cleanup_plan_id=None):
    if raw.get("style_profile"):
        style = store.create_style(raw["style_profile"])
        raw = dict(raw, style=style["style_key"])
    sid = raw.get("series_id")
    existing_series = store.get("series", sid) if sid else None
    style_value = raw.get("style") or (existing_series or {}).get("style_key")
    if style_value in ("【同风格:上一张】", "上一张"):
        style_value = store.get("settings", "last_style_key")
    if existing_series and style_value and "-v" not in style_value:
        pinned = existing_series.get("style_key")
        if pinned and store.need("styles", pinned)["style_id"] in style_value:
            style_value = pinned
    style = store.resolve_style(style_value)
    if not style:
        raise SeriesError("style_required", "先定义风格档案，或指定已有风格编号")
    if not sid and not raw.get("isolated", False):
        matches = [x for x in store.all("series") if x.get("style_key") == style["style_key"] and not x.get("isolated")]
        if matches:
            existing_series = sorted(matches, key=lambda x:x.get("created_at", ""))[-1]
            sid = existing_series["id"]
    request = normalize_request(raw, style)
    assets = bind_assets(store, style)
    if existing_series and existing_series.get("style_key") is None:
        existing_series["style_key"] = style["style_key"]
        store.put("series", sid, existing_series)
    series = store.create_series(style["style_key"], raw.get("series_name", ""), sid,
                                 isolated=raw.get("isolated", False))
    old_key = store.get("settings", "active_style_key")
    if not series.get("isolated") and old_key and old_key != style["style_key"]:
        if switch_decision not in ("keep", "delete") or not human_confirmation.strip():
            old = store.need("styles", old_key)
            old_assets = [store.need("assets", x) for x in old.get("asset_ids", [])]
            raise SeriesError("switch_decision_required", "切换风格前，请用户决定旧模型保留或删除；删除使用cleanup清单确认", {
                "from": old_key, "to": style["style_key"],
                "old_models": [{"id": x["id"], "name": x["name"], "bytes": x["bytes"], "managed": x.get("managed", False),
                    "related_series": [s["id"] for s in store.all("series") if s.get("style_key") and x["id"] in store.need("styles", s["style_key"]).get("asset_ids", [])] if x.get("id") else []} for x in old_assets]})
        if switch_decision == "delete":
            plan = store.need("cleanup", cleanup_plan_id or "")
            old = store.need("styles", old_key)
            if plan.get("status") != "complete" or not set(plan.get("confirmed_ids", [])).issubset(set(old.get("asset_ids", []))) or plan.get("human_confirmation") != human_confirmation:
                raise SeriesError("switch_cleanup_unconfirmed", "删除选择须关联已完成且与旧风格对应的用户确认清单")
        store.event("style_switch", series["id"], {"from": old_key, "to": style["style_key"], "decision": switch_decision,
                                                   "human_confirmation": human_confirmation, "cleanup_plan_id": cleanup_plan_id})
    references = []
    for ref in request["references"]:
        if ref.get("material_id"):
            material = store.need("materials", identifier(ref["material_id"]))
        elif ref.get("path"):
            material = ingest(store, ref["path"], ref["role"])
        else:
            raise SeriesError("reference_path_required", "参考素材须指定material_id或path")
        if material["kind"] != "image":
            raise SeriesError("image_reference_required", "references只放图像；文字和文档用materials保存并提炼到prompt")
        references.append(dict(ref, material_id=material["id"], path=material["path"]))
    request["references"] = references
    for material_id in request.get("materials", []):
        store.need("materials", identifier(material_id))
    request.update(series_id=series["id"], style=style["style_key"])
    material_ids = set(request.get("materials", [])) | {x["material_id"] for x in references}
    material_ids |= {x["material_id"] for x in style.get("locked_generation_settings", {}).get("reference_conditioning", []) if x.get("material_id")}
    request["material_provenance"] = [{k:store.need("materials", mid).get(k) for k in ("id", "source", "path", "sha256", "role", "kind")} for mid in sorted(material_ids)]
    jid = "J-" + uuid.uuid4().hex[:16]
    folder = store.config.data / "runs" / jid
    folder.mkdir(parents=True, exist_ok=True)
    job = {"id": jid, "series_id": series["id"], "style_key": style["style_key"], "request": request,
           "style_snapshot": deepcopy(style), "model_manifest": assets, "status": "prepared", "created_at": now(),
           "images": [{"index": i, "attempts": [], "review": None} for i in range(request["output"]["count"])],
           "max_rounds": 3, "folder": str(folder)}
    store.put("jobs", jid, job)
    write_json(folder / "request.json", request)
    write_json(folder / "style.json", style)
    write_json(folder / "models.json", assets)
    write_json(folder / "job.json", job)
    if not series.get("isolated"):
        store.put("settings", "active_style_key", style["style_key"])
    return job


def upload_references(store, client, job):
    mapping, seen = {}, {}
    refs = list(job["request"]["references"])
    for condition in job["style_snapshot"].get("locked_generation_settings", {}).get("reference_conditioning", []):
        ref = dict(condition, role="style", path=condition.get("reference_path"))
        if ref.get("material_id"):
            ref["path"] = store.need("materials", ref["material_id"])["path"]
        refs.append(ref)
    for ref in refs:
        path = Path(ref["path"])
        if not path.is_file():
            raise SeriesError("reference_missing", "绑定的参考素材不存在")
        checksum = digest(path)
        if ref.get("sha256") and checksum != ref["sha256"]:
            raise SeriesError("style_reference_changed", "参考图内容变化，需新风格版本")
        if checksum not in seen:
            seen[checksum] = client.upload(path)
        for identity in (ref.get("material_id"), ref.get("path"), ref.get("reference_path")):
            if identity:
                mapping[identity] = seen[checksum]
    return mapping


def save_job(store, job):
    job["updated_at"] = now()
    store.put("jobs", job["id"], job)
    write_json(Path(job["folder"]) / "job.json", job)


def wait_history(store, client, job, attempt):
    deadline = time.monotonic() + store.config.timeout_seconds
    while time.monotonic() < deadline:
        history = client.history(attempt["prompt_id"])
        if history:
            return history
        time.sleep(store.config.poll_seconds)
    raise SeriesError("execution_pending", "等待超时；已记录prompt_id，不自动重复提交。使用run恢复跟踪", {"prompt_id": attempt["prompt_id"]})


def finish_attempt(store, client, job, image, attempt, history):
    folder = Path(attempt["folder"])
    write_json(folder / "history.json", history)
    status = history.get("status", {})
    if status.get("status_str") != "success":
        attempt.update(status="failed", error=status, ended_at=now())
        save_job(store, job)
        return False
    output = history.get("outputs", {}).get(attempt["generation"]["save_node"], {})
    images = output.get("images", [])
    if not images:
        attempt.update(status="failed", error={"code": "output_missing"}, ended_at=now())
        save_job(store, job)
        return False
    path = folder / "result.png"
    path.write_bytes(client.fetch_image(images[0]))
    with Image.open(path) as im:
        size, fmt = list(im.size), im.format
        im.verify()
    if size != attempt["generation"]["output_size"] or fmt != "PNG":
        attempt.update(status="failed", error={"code": "output_dimensions", "actual": size}, ended_at=now())
        save_job(store, job)
        return False
    attempt.update(status="rendered", path=str(path.resolve()), output_size=size, sha256=digest(path), ended_at=now(),
                   technical_checks={"execution": "passed", "dimensions": "passed", "png": "passed"})
    image["latest_path"] = str(path.resolve())
    image["review"] = None
    if attempt["generation"].get("reference_method") == "ipadapter":
        capability = store.get("capabilities", "ipadapter", {"runtime_jobs": []})
        capability.update(status="runtime_passed", checked_at=now(), server=store.config.server,
                          limitation="参考内容或布局可能混入；每张输出仍需视觉评审")
        capability["runtime_jobs"] = sorted(set(capability["runtime_jobs"] + [job["id"]]))
        store.put("capabilities", "ipadapter", capability)
    write_json(folder / "manifest.json", {"job_id": job["id"], "series_id": job["series_id"], "style_key": job["style_key"],
                  "attempt": attempt, "request": read_json(folder / "request.json"), "original_request": job["request"], "models": job["model_manifest"],
                  "visual_review": "pending_actual_image_inspection"})
    save_job(store, job)
    return True


def run(store, jid, indices=None, patch=None):
    job = store.need("jobs", identifier(jid))
    with FileLock(str(Path(job["folder"]) / "run.lock"), timeout=1):
        job = store.need("jobs", jid)
        if all((x.get("review") or {}).get("accepted") for x in job["images"]):
            return job
        client = ComfyClient(store.config)
        style = job["style_snapshot"]
        bind_assets(store, deepcopy(style), persist=False)
        uploaded = upload_references(store, client, job)
        # LoadImage choices change after upload; validate against the fresh schema.
        info = client.info()
        requested_indices = set(indices) if indices is not None else {x["index"] for x in job["images"] if x.get("review") is not None and not x["review"].get("accepted")}
        if indices is None:
            requested_indices |= {x["index"] for x in job["images"] if not x["attempts"] or x["attempts"][-1]["status"] in ("failed", "queued", "building", "submitting", "submission_unknown")}
        if not requested_indices.issubset({x["index"] for x in job["images"]}):
            raise SeriesError("image_index", "图片序号不在请求范围内")
        request = deepcopy(job["request"])
        if patch:
            if set(patch) - {"prompt", "negative", "seed", "generation"}:
                raise SeriesError("retry_patch", "重试只调整内容提示词、种子和生成尺寸；输出要求及风格保持固定")
            request.update(patch)
            request = normalize_request(request, style)
        job["status"] = "running"
        save_job(store, job)
        for image in job["images"]:
            if image["index"] not in requested_indices:
                continue
            if (image.get("review") or {}).get("accepted"):
                continue
            if image["attempts"] and image["attempts"][-1]["status"] in ("submitting", "submission_unknown"):
                pending = image["attempts"][-1]
                prefix = f"ComfySeries/{jid}/image_{image['index'] + 1:03d}_round_{pending['number']}"
                prompt_id = client.find_submission(jid, prefix)
                if not prompt_id:
                    job['status'] = 'waiting'
                    save_job(store, job)
                    raise SeriesError("submission_unknown", "没有找到提交回执；核查队列、历史和输出，不能自动重排", {"job_id": jid, "prefix": prefix})
                pending.update(status="queued", prompt_id=prompt_id)
                save_job(store, job)
            # Interrupted waits resume the existing ComfyUI prompt, never queue a duplicate.
            if image["attempts"] and image["attempts"][-1]["status"] == "queued":
                pending = image["attempts"][-1]
                history = client.history(pending["prompt_id"])
                if history is None:
                    queue = client.queue()
                    queue_ids = {str(x[1]) for group in ("queue_running", "queue_pending") for x in queue.get(group, [])}
                    if pending["prompt_id"] not in queue_ids:
                        raise SeriesError("execution_unknown", "服务器没有此任务的队列或历史；先核实输出，再用abandon明确结束未知任务")
                    history = wait_history(store, client, job, pending)
                if finish_attempt(store, client, job, image, pending, history):
                    continue
            # Rendered files awaiting visual review are not silently rerendered.
            if image["attempts"] and image["attempts"][-1]["status"] == "rendered" and image.get("review") is None:
                continue
            if len(image["attempts"]) >= job["max_rounds"]:
                continue
            area_scale = 1
            while len(image["attempts"]) < job["max_rounds"]:
                number = len(image["attempts"]) + 1
                folder = Path(job["folder"]) / f"image_{image['index'] + 1:03d}" / f"round_{number}"
                folder.mkdir(parents=True, exist_ok=True)
                attempt = {"number": number, "status": "building", "folder": str(folder), "started_at": now()}
                image["attempts"].append(attempt)
                save_job(store, job)
                try:
                    actual_request = dict(request, filename_prefix=f"ComfySeries/{jid}/image_{image['index'] + 1:03d}_round_{number}")
                    graph, generation = build_graph(actual_request, style, uploaded, image["index"], area_scale)
                    validation = validate_graph(graph, info)
                    canvas = to_canvas(graph, info)
                    write_json(folder / "workflow.api.json", graph)
                    write_json(folder / "workflow.json", canvas)
                    write_json(folder / "request.json", actual_request)
                    attempt.update(generation=generation, validation=validation, status="submitting")
                    save_job(store, job)
                    response = client.submit(graph, canvas, jid)
                    if response.get("node_errors"):
                        raise SeriesError("comfy_validation", "ComfyUI拒绝工作流", response["node_errors"])
                    attempt.update(status="queued", prompt_id=response["prompt_id"])
                    save_job(store, job)
                    history = wait_history(store, client, job, attempt)
                    if finish_attempt(store, client, job, image, attempt, history):
                        break
                    error_text = json.dumps(attempt.get("error", {})).lower()
                    oom = "outofmemory" in error_text or "out of memory" in error_text or "allocation" in error_text
                    if oom:
                        area_scale *= .7
                        client.free_memory()
                        continue
                    break
                except SeriesError as exc:
                    if exc.code == "submission_unknown":
                        attempt.update(status="submission_unknown", error={"code": exc.code, "message": str(exc)})
                    if exc.code in ("execution_pending", "submission_unknown") or attempt["status"] == "queued":
                        job["status"] = "waiting"
                        save_job(store, job)
                        raise
                    attempt.update(status="failed", error={"code": exc.code, "message": str(exc), "details": exc.details}, ended_at=now())
                    save_job(store, job)
                    break
                except KeyboardInterrupt:
                    job["status"] = "waiting" if attempt["status"] in ("queued", "submitting") else "interrupted"
                    save_job(store, job)
                    raise
                except Exception as exc:
                    unknown = attempt["status"] in ("queued", "submitting")
                    attempt.update(status=attempt["status"] if unknown else "failed", error={"code": type(exc).__name__})
                    job["status"] = "waiting" if unknown else "failed"
                    save_job(store, job)
                    raise SeriesError("run_error", "执行发生异常；查询记录后恢复，避免重复提交", {"job_id": jid, "type": type(exc).__name__}) from exc
        job["status"] = "accepted" if all((x.get("review") or {}).get("accepted") for x in job["images"]) else "awaiting_visual_review" if any(x.get("latest_path") for x in job["images"]) else "failed"
        save_job(store, job)
        return job


def review(store, jid, reviews):
    job = store.need("jobs", identifier(jid))
    pending = []
    for result in reviews:
        index = result["index"]
        image = next((x for x in job["images"] if x["index"] == index), None)
        if not image:
            raise SeriesError("image_index", "评审图片不属于此请求")
        attempt = next((x for x in image["attempts"] if x["number"] == result["round"]), None)
        if not attempt or attempt["status"] != "rendered":
            raise SeriesError("review_output_missing", "没有可评审的实际输出")
        if str(Path(result.get("viewed_path", "")).resolve()) != str(Path(attempt["path"]).resolve()):
            raise SeriesError("review_not_viewed", "评审须记录实际查看的输出路径")
        checks = result.get("checks", {})
        if not {"subject", "composition", "style", "defects"}.issubset(checks) or any(v not in ("pass", "partial", "fail") for v in checks.values()):
            raise SeriesError("review_checks", "填写主体、构图、风格和缺陷检查，状态为pass/partial/fail")
        accepted = bool(result.get("accepted", False))
        if accepted and any(value != "pass" for value in checks.values()):
            raise SeriesError("review_contradiction", "存在失败或部分通过项的图片不能标记完全通过")
        pending.append((image, attempt, result, accepted))
    for image, attempt, result, accepted in pending:
        result = dict(result, accepted=accepted, reviewed_at=now())
        image["review"] = result
        attempt["visual_review"] = result
        def score(item):
            return sum({"pass": 2, "partial": 1, "fail": 0}[x] for x in item.get("checks", {}).values())
        prior = next((x for x in image["attempts"] if x.get("path") == image.get("best_path")), None)
        if result.get("select_best") or not prior or score(result) >= score(prior.get("visual_review", {})):
            image["best_path"] = attempt["path"]
        manifest = Path(attempt["folder"]) / "manifest.json"
        from .common import read_json
        data = read_json(manifest)
        data["visual_review"] = result
        write_json(manifest, data)
    if all(x.get("review", {}).get("accepted") if x.get("review") else False for x in job["images"]):
        job["status"] = "accepted"
    elif all(len(x["attempts"]) >= 3 or (x.get("review") or {}).get("accepted") for x in job["images"]):
        job["status"] = "completed_with_gaps"
    else:
        job["status"] = "needs_adjustment"
    save_job(store, job)
    style = store.need("styles", job["style_key"])
    accepted_images = [x for x in job["images"] if (x.get("review") or {}).get("accepted")]
    if accepted_images and not style.get("visual_baseline"):
        chosen = accepted_images[0]
        style["visual_baseline"] = {"image_id": f"{jid}-{chosen['index']}", "image_path": chosen["best_path"], "job_id": jid}
        store.put("styles", style["style_key"], style)
        write_json(store.config.data / "styles" / (style["style_key"] + ".json"), style)
    if accepted_images and not store.need("series", job["series_id"]).get("isolated"):
        store.put("settings", "last_style_key", style["style_key"])
    return job


def abandon(store, jid, index, reason):
    job = store.need("jobs", identifier(jid))
    image = job["images"][index]
    if not reason.strip() or not image["attempts"] or image["attempts"][-1]["status"] not in ("queued", "building", "submitting", "submission_unknown"):
        raise SeriesError("abandon_invalid", "只有未知/未完成任务可结束，并需记录核查原因")
    image["attempts"][-1].update(status="failed", error={"code": "explicitly_abandoned", "reason": reason}, ended_at=now())
    save_job(store, job)
    return job
