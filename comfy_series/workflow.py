from __future__ import annotations

import math
import re
import secrets
from collections import defaultdict
from copy import deepcopy
from .common import SeriesError


def normalize_request(raw, style=None):
    if not isinstance(raw, dict):
        raise SeriesError("invalid_request", "请求应为JSON对象")
    result = deepcopy(raw)
    brief = result.get("brief") or result.get("prompt")
    if not isinstance(brief, str) or not brief.strip():
        raise SeriesError("brief_required", "需要制作要求 brief 或 prompt")
    result["brief"] = brief
    result.setdefault("prompt", brief)
    result.setdefault("negative", "")
    if any(not isinstance(result[x], str) for x in ("prompt", "negative")):
        raise SeriesError("invalid_prompt", "提示词应为文本")
    out = result.setdefault("output", {})
    if not isinstance(out, dict):
        raise SeriesError("invalid_output", "output应为JSON对象")
    explicit_size = "width" in out or "height" in out
    if explicit_size and not {"width", "height"}.issubset(out):
        raise SeriesError("incomplete_dimensions", "精确尺寸需同时提供 width 和 height")
    default_width, default_height = 1824, 1248
    ratio = out.get("aspect_ratio")
    if ratio:
        if not isinstance(ratio, str) or not re.fullmatch(r"[1-9]\d*:[1-9]\d*", ratio):
            raise SeriesError("invalid_aspect_ratio", "比例使用 3:2 等格式")
        rw, rh = map(int, ratio.split(":"))
        if explicit_size and out["width"] * rh != out["height"] * rw:
            raise SeriesError("dimensions_conflict", "宽高与画面比例矛盾，请澄清")
        if not explicit_size:
            unit = max(1, round(math.sqrt(default_width * default_height / (rw * rh))))
            out.update(width=rw * unit, height=rh * unit)
    out.setdefault("width", default_width)
    out.setdefault("height", default_height)
    out.setdefault("count", 1)
    out.setdefault("format", "PNG")
    for key in ("width", "height", "count"):
        if type(out[key]) is not int or out[key] <= 0:
            raise SeriesError("invalid_output", f"{key} 必须是正整数")
    if out["width"] > 16384 or out["height"] > 16384 or out["width"] * out["height"] > 64_000_000:
        raise SeriesError("output_capacity", "第一版最终尺寸上限为单边16384、总像素6400万；需要更大尺寸时另行设计分块输出")
    if out["count"] > 100:
        raise SeriesError("output_capacity", "单次请求最多100张，逐张执行")
    if not isinstance(out["format"], str) or out["format"].upper() != "PNG":
        raise SeriesError("unsupported_format", "第一版输出PNG")
    out["format"] = "PNG"
    seed = result.get("seed", secrets.randbits(63))
    if type(seed) is not int or not 0 <= seed < 2 ** 64:
        raise SeriesError("invalid_seed", "seed 超出支持范围")
    result["seed"] = seed
    refs = result.setdefault("references", [])
    if not isinstance(refs, list) or any(not isinstance(x, dict) for x in refs):
        raise SeriesError("invalid_references", "references应为素材对象列表")
    for ref in refs:
        ref.setdefault("role", "style")
        if ref["role"] not in ("style", "subject", "composition", "structure", "context"):
            raise SeriesError("reference_role", "参考用途无效")
    constraints = result.setdefault("constraints", {})
    if not isinstance(constraints, dict):
        raise SeriesError("invalid_constraints", "constraints应为JSON对象")
    for key in ("must", "avoid"):
        values = constraints.setdefault(key, [])
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
            raise SeriesError("invalid_constraints", "必须与排除内容应为文本列表")
    if not isinstance(result.get("materials", []), list) or any(not isinstance(x, str) for x in result.get("materials", [])):
        raise SeriesError("invalid_materials", "materials应为素材编号列表")
    return result


def generation_size(width, height, area=1_011_712):
    # Match target ratio while making only the latent dimensions divisible by 8.
    scale = math.sqrt(area / (width * height))
    gw, gh = max(64, round(width * scale / 8) * 8), max(64, round(height * scale / 8) * 8)
    factor = min(1, 2048 / max(gw, gh))
    return max(64, round(gw * factor / 8) * 8), max(64, round(gh * factor / 8) * 8)


def build_graph(request, style, uploaded, image_index=0, area_scale=1):
    locked = style.get("locked_generation_settings", {})
    first = locked.get("first_pass", {})
    second = locked.get("second_pass")
    blocks = style.get("prompt_blocks", {})
    checkpoint = locked.get("checkpoint")
    if not checkpoint:
        raise SeriesError("style_checkpoint_required", "风格档案必须绑定 checkpoint")
    workflow_options = request.get("workflow", {})
    if workflow_options.get("checkpoint", checkpoint) != checkpoint:
        raise SeriesError("style_revision_required", "更换模型需建立新风格版本")
    width, height = request["output"]["width"], request["output"]["height"]
    base = request.get("generation", {})
    if base:
        gw, gh = base["width"], base["height"]
        if any(type(v) is not int or v < 64 or v % 8 for v in (gw, gh)):
            raise SeriesError("invalid_generation_size", "生成尺寸必须为至少64的8倍数")
        if abs(gw / gh - width / height) / (width / height) > 0.02:
            raise SeriesError("generation_ratio", "生成画幅应与目标画幅相符，避免大幅裁剪")
        gw, gh = generation_size(width, height, gw * gh * area_scale)
    else:
        default_base = style.get("defaults", {}).get("base_resolution", [1216, 832])
        gw, gh = generation_size(width, height, default_base[0] * default_base[1] * area_scale)
    seed = (request["seed"] + image_index) % (2 ** 64)
    positive = ", ".join(x for x in (request["prompt"], ", ".join(request["constraints"].get("must", [])),
                                    blocks.get("fixed_positive_style", "")) if x)
    negative = ", ".join(x for x in (request.get("negative", ""), blocks.get("fixed_negative_style", ""),
                                    ", ".join(request["constraints"].get("avoid", []))) if x)
    graph = {}

    def add(cls, inputs, title=None):
        nid = str(len(graph) + 1)
        graph[nid] = {"class_type": cls, "inputs": inputs, "_meta": {"title": title or cls}}
        return nid

    model_id = add("CheckpointLoaderSimple", {"ckpt_name": checkpoint}, "主模型 / Model")
    model, clip, vae = [model_id, 0], [model_id, 1], [model_id, 2]
    for lora in locked.get("loras", []):
        lid = add("LoraLoader", {"model": model, "clip": clip, "lora_name": lora["name"],
                              "strength_model": lora.get("strength_model", 1), "strength_clip": lora.get("strength_clip", 1)})
        model, clip = [lid, 0], [lid, 1]
    reference_conditions = locked.get("reference_conditioning", [])
    style_refs = [x for x in request["references"] if x["role"] == "style"]
    if style_refs and not reference_conditions and workflow_options.get("reference_method") != "description":
        raise SeriesError("style_revision_required", "添加风格参考条件需新建风格版本；描述参考须显式标记 description")
    reference_log = []
    for condition in reference_conditions:
        if condition.get("method") != "ipadapter":
            raise SeriesError("unsupported_reference_method", "该参考条件未实现")
        identity = condition.get("material_id") or condition.get("reference_path")
        if identity not in uploaded:
            raise SeriesError("style_reference_missing", "绑定的风格参考图未上传", {"reference": identity})
        loader = add("IPAdapterModelLoader", {"ipadapter_file": condition["model"]})
        vision = add("CLIPVisionLoader", {"clip_name": condition["clip_vision"]})
        image = add("LoadImage", {"image": uploaded[identity]})
        adapter = add("IPAdapterAdvanced", {"model": model, "ipadapter": [loader, 0], "image": [image, 0],
                      "clip_vision": [vision, 0], "weight": condition.get("weight", 0.6),
                      "weight_type": condition.get("weight_type", "style transfer"), "combine_embeds": "concat",
                      "start_at": condition.get("start_at", 0), "end_at": condition.get("end_at", 1), "embeds_scaling": "V only"})
        model = [adapter, 0]
        reference_log.append({"method": "ipadapter", "reference": identity,
                              "weight": condition.get("weight", 0.6), "encoder_preprocessing": "CLIP-ViT-H center crop"})
    pos = add("CLIPTextEncode", {"text": positive, "clip": clip}, "主体与固定风格")
    neg = add("CLIPTextEncode", {"text": negative, "clip": clip}, "排除内容与质量约束")
    mode = style.get("mode", "txt2img")
    if workflow_options.get("mode", mode) != mode:
        raise SeriesError("style_revision_required", "更改生成模式需创建风格版本")
    if mode == "img2img":
        content_refs = [x for x in request["references"] if x["role"] in ("subject", "structure", "composition")]
        if not content_refs:
            raise SeriesError("content_reference_required", "图生图需要内容/结构参考图")
        ref = content_refs[0]
        identity = ref.get("material_id") or ref.get("path")
        load = add("LoadImage", {"image": uploaded[identity]})
        scaled = add("ImageScale", {"image": [load, 0], "width": gw, "height": gh, "upscale_method": "lanczos", "crop": "center"})
        encoded = add("VAEEncodeTiled", {"pixels": [scaled, 0], "vae": vae, "tile_size": 512, "overlap": 64,
                                        "temporal_size": 64, "temporal_overlap": 8})
        latent = [encoded, 0]
        reference_log.append({"method": "img2img", "reference": identity, "source_crop": "center to target aspect"})
    elif mode == "txt2img":
        empty = add("EmptyLatentImage", {"width": gw, "height": gh, "batch_size": 1})
        latent = [empty, 0]
    else:
        raise SeriesError("unsupported_mode", "第一版支持txt2img和img2img")
    sampled = add("KSampler", {"model": model, "positive": [pos, 0], "negative": [neg, 0], "latent_image": latent,
                              "seed": seed, "steps": first.get("steps", 30), "cfg": first.get("cfg", 5),
                              "sampler_name": first.get("sampler_name", "dpmpp_2m"),
                              "scheduler": first.get("scheduler", "karras"), "denoise": first.get("denoise", 1 if mode == "txt2img" else .55)})
    tiled = locked.get("vae_tiling", {})

    def decode(samples):
        return add("VAEDecodeTiled", {"samples": samples, "vae": vae, "tile_size": tiled.get("tile_size", 512),
                                     "overlap": tiled.get("overlap", 64), "temporal_size": 64, "temporal_overlap": 8})

    decoded = decode([sampled, 0])
    image = [decoded, 0]
    upscale = locked.get("upscaling")
    if upscale and upscale.get("model"):
        upmodel = add("UpscaleModelLoader", {"model_name": upscale["model"]})
        upimage = add("ImageUpscaleWithModel", {"upscale_model": [upmodel, 0], "image": image})
        scale = add("ImageScaleBy", {"image": [upimage, 0], "upscale_method": upscale.get("resize_method", "lanczos"),
                                    "scale_by": upscale.get("resize_scale", .75)})
        image = [scale, 0]
    if second:
        encoded = add("VAEEncodeTiled", {"pixels": image, "vae": vae, "tile_size": tiled.get("tile_size", 512),
                                        "overlap": tiled.get("overlap", 64), "temporal_size": 64, "temporal_overlap": 8})
        refined = add("KSampler", {"model": model, "positive": [pos, 0], "negative": [neg, 0], "latent_image": [encoded, 0],
                                  "seed": seed, "steps": second.get("steps", 18), "cfg": second.get("cfg", 5),
                                  "sampler_name": second.get("sampler_name", "dpmpp_2m"),
                                  "scheduler": second.get("scheduler", "karras"), "denoise": second.get("denoise", .2)})
        image = [decode([refined, 0]), 0]
    final = add("ImageScale", {"image": image, "width": width, "height": height, "upscale_method": "lanczos", "crop": "center"}, "最终精确像素尺寸")
    save = add("SaveImage", {"images": [final, 0], "filename_prefix": request.get("filename_prefix", "ComfySeries/result")})
    return graph, {"generation_size": [gw, gh], "output_size": [width, height], "seed": seed,
                   "save_node": save, "positive": positive, "negative": negative, "references": reference_log,
                   "style_key": style["style_key"], "checkpoint": checkpoint,
                   "reference_method": "ipadapter" if reference_conditions else "description" if style_refs else "none"}


def schema_entries(info):
    inputs = info.get("input", {})
    result = {}
    for group in ("required", "optional"):
        for name, schema in inputs.get(group, {}).items():
            result[name] = schema
    return result


def is_link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int


def validate_graph(graph, info):
    errors = []
    dependencies = defaultdict(list)
    for nid, node in graph.items():
        cls = node.get("class_type")
        if cls not in info:
            errors.append({"node": nid, "code": "missing_node", "class": cls})
            continue
        meta = info[cls]
        entries = schema_entries(meta)
        values = node.get("inputs", {})
        for field in meta.get("input", {}).get("required", {}):
            if field not in values:
                errors.append({"node": nid, "field": field, "code": "missing_input"})
        for field, value in values.items():
            if field not in entries:
                errors.append({"node": nid, "field": field, "code": "unknown_input"})
                continue
            entry = entries[field]
            typ, options = entry[0], entry[1] if len(entry) > 1 and isinstance(entry[1], dict) else {}
            if is_link(value):
                source, slot = value
                dependencies[nid].append(source)
                source_meta = info.get(graph.get(source, {}).get("class_type"), {})
                outputs = source_meta.get("output", [])
                if source not in graph or not 0 <= slot < len(outputs):
                    errors.append({"node": nid, "field": field, "code": "missing_link"})
                elif typ != "*" and outputs[slot] != "*" and outputs[slot] != typ:
                    errors.append({"node": nid, "field": field, "code": "type_mismatch", "expected": typ, "actual": outputs[slot]})
            elif isinstance(typ, list):
                if value not in typ:
                    errors.append({"node": nid, "field": field, "code": "unavailable_option", "value": value})
            elif typ in ("INT", "FLOAT"):
                valid_type = type(value) is int if typ == "INT" else type(value) in (int, float)
                if not valid_type or not math.isfinite(value) or not options.get("min", value) <= value <= options.get("max", value):
                    errors.append({"node": nid, "field": field, "code": "invalid_number"})
            elif typ == "BOOLEAN" and type(value) is not bool:
                errors.append({"node": nid, "field": field, "code": "invalid_boolean"})
            elif typ == "STRING" and not isinstance(value, str):
                errors.append({"node": nid, "field": field, "code": "invalid_string"})
            elif typ not in ("STRING", "INT", "FLOAT", "BOOLEAN"):
                errors.append({"node": nid, "field": field, "code": "link_required"})
    visited, stack = set(), set()

    def visit(nid):
        if nid in stack:
            errors.append({"node": nid, "code": "cycle"})
            return
        if nid in visited:
            return
        stack.add(nid)
        for dep in dependencies[nid]:
            visit(dep)
        stack.remove(nid)
        visited.add(nid)
    for nid in graph:
        visit(nid)
    if errors:
        raise SeriesError("workflow_validation", "工作流未通过本机节点校验", errors)
    return {"status": "schema_validated", "nodes": len(graph), "links": sum(map(len, dependencies.values()))}


def to_canvas(graph, info):
    nodes, links = [], []
    link_id, levels = 0, {}
    output_links = defaultdict(list)
    def level(nid):
        if nid not in levels:
            deps = [x[0] for x in graph[nid]["inputs"].values() if is_link(x)]
            levels[nid] = max((level(x) + 1 for x in deps), default=0)
        return levels[nid]
    rows = defaultdict(int)
    for nid, value in graph.items():
        cls = value["class_type"]
        meta, inputs, widgets = info[cls], [], []
        for name, entry in schema_entries(meta).items():
            typ = entry[0]
            options = entry[1] if len(entry) > 1 and isinstance(entry[1], dict) else {}
            primitive = isinstance(typ, list) or typ in ("INT", "FLOAT", "BOOLEAN", "STRING")
            literal = value["inputs"].get(name, options.get("default"))
            wired = is_link(literal)
            if not primitive or options.get("forceInput") or wired:
                item = {"name": name, "type": "COMBO" if isinstance(typ, list) else typ, "link": None}
                if primitive:
                    item["widget"] = {"name": name}
                if wired:
                    link_id += 1
                    item["link"] = link_id
                    src, slot = literal
                    links.append([link_id, int(src), slot, int(nid), len(inputs), item["type"]])
                    output_links[(src, slot)].append(link_id)
                inputs.append(item)
            if primitive and not options.get("forceInput"):
                widgets.append(options.get("default") if wired else literal)
                if name in ("seed", "noise_seed"):
                    widgets.append("fixed")
        col = level(nid)
        row, rows[col] = rows[col], rows[col] + 1
        outputs = [{"name": name, "type": typ, "links": [], "slot_index": slot} for slot, (name, typ) in
                   enumerate(zip(meta.get("output_name", meta.get("output", [])), meta.get("output", [])))]
        nodes.append({"id": int(nid), "type": cls, "pos": [col * 380, row * 360], "size": [340, 300],
                      "flags": {}, "order": int(nid) - 1, "mode": 0, "inputs": inputs, "outputs": outputs,
                      "properties": {"Node name for S&R": cls}, "widgets_values": widgets,
                      "title": value.get("_meta", {}).get("title", cls)})
    for node in nodes:
        for slot, output in enumerate(node["outputs"]):
            output["links"] = output_links[(str(node["id"]), slot)]
    return {"last_node_id": max(map(int, graph), default=0), "last_link_id": link_id, "nodes": nodes, "links": links,
            "groups": [], "config": {}, "extra": {"ds": {"scale": .6, "offset": [0, 0]}}, "version": .4}


def from_canvas(canvas, info):
    links = {x[0]: x for x in canvas.get("links", [])}
    graph = {}
    for node in canvas.get("nodes", []):
        if node.get("type") in ("Note", "MarkdownNote") and not any(x.get("links") for x in node.get("outputs", [])):
            continue
        if node.get("mode", 0) != 0:
            raise SeriesError("unsupported_canvas_mode", "旁路或禁用节点需先在 ComfyUI 导出API图")
        cls = node["type"]
        if cls not in info:
            raise SeriesError("missing_node", "模板需要未安装节点", {"class": cls})
        linked = {x["name"]: links[x["link"]] for x in node.get("inputs", []) if x.get("link") in links}
        widgets = iter(node.get("widgets_values", []))
        values = {}
        for name, entry in schema_entries(info[cls]).items():
            typ = entry[0]
            options = entry[1] if len(entry) > 1 and isinstance(entry[1], dict) else {}
            primitive = isinstance(typ, list) or typ in ("INT", "FLOAT", "BOOLEAN", "STRING")
            if primitive and not options.get("forceInput"):
                value = next(widgets, options.get("default"))
                if name in ("seed", "noise_seed"):
                    next(widgets, None)
                if value is not None:
                    values[name] = value
            if name in linked:
                link = linked[name]
                values[name] = [str(link[1]), link[2]]
        graph[str(node["id"])] = {"class_type": cls, "inputs": values, "_meta": {"title": node.get("title", cls)}}
    validate_graph(graph, info)
    return graph
