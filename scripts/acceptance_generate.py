"""Real GPU checks, in isolated series so tests never change the active production style."""
import argparse
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comfy_series.common import Config, Store, SeriesError, now, write_json
from comfy_series.engine import prepare, run
from comfy_series.ingest import ingest

p = argparse.ArgumentParser()
p.add_argument("case", choices=["photo", "illustration", "reference", "img2img"])
args = p.parse_args()
config, results = Config(), []
store = Store(config)
baseline = store.need("styles", "S001-v1")
material = ingest(store, baseline["visual_baseline"]["image_path"], "style")

def profile(marker, payload):
    existing = next((x for x in store.all("styles") if x.get("acceptance_profile") == marker), None)
    return existing or store.create_style(dict(payload, acceptance_profile=marker))

if args.case == "photo":
    style = baseline
    prompts = ["A wide cinematic photograph of a vast underground archive room, tall steel shelves with sealed storage boxes, industrial concrete walls, cold blue-gray fluorescent light, empty room, readable architectural scale, no corridor, no writing",
               "A cinematic photograph of an underground machinery hall, a large brass and steel cylindrical apparatus in the center, orderly pipes and service platforms, cold gray-blue lighting with a small red warning light, empty industrial room, physically plausible construction"]
elif args.case == "illustration":
    style = profile("illustration-pony", {"style_id": "S002", "display_name": "温暖手绘科幻插画", "mode": "txt2img",
         "model_selection": {"replaced": "WAI_NSFW-illustrious-SDXL_v14.safetensors", "reason": "预装权重文件头损坏；复用本机Pony SDXL，未删除原文件"},
         "locked_generation_settings": {"checkpoint": "WAI-2DPonyXL_2.0.safetensors", "loras": [], "reference_conditioning": [],
             "first_pass": {"steps": 28, "cfg": 5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1},
             "upscaling": {"model": "RealESRGAN_x2plus.pth", "resize_method": "lanczos", "resize_scale": .75}},
         "prompt_blocks": {"fixed_positive_style": "masterpiece, best quality, hand painted gouache illustration, warm amber and teal palette, visible brush strokes, elegant shapes, soft atmospheric lighting, whimsical science fiction architecture",
                           "fixed_negative_style": "photograph, photorealistic, low quality, blurry, watermark, writing, letters"},
         "defaults": {"base_resolution": [1216, 832], "output_resolution": [1536, 1024]}})
    prompts = ["An illustrated underground archive library, tall curved bookshelves, amber lamps, brass cabinets, empty room, wide composition, no text",
               "An illustrated observatory machine room, a large brass telescope mechanism, curved service platforms, warm glowing lamps and teal shadows, wide composition, empty room"]
elif args.case == "reference":
    payload = copy.deepcopy(baseline)
    for key in ("style_id", "revision", "style_key", "visual_baseline", "asset_ids", "model_manifest", "origin"):
        payload.pop(key, None)
    payload["display_name"] = "冷色设施摄影 · 图像风格参考"
    payload["locked_generation_settings"].pop("second_pass", None)
    payload["locked_generation_settings"]["first_pass"]["steps"] = 24
    payload["locked_generation_settings"]["reference_conditioning"] = [{"method": "ipadapter", "material_id": material["id"],
        "reference_path": material["path"], "sha256": material["sha256"], "model": "ip-adapter-plus_sdxl_vit-h.safetensors",
        "clip_vision": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors", "weight": .6, "weight_type": "style transfer", "start_at": 0, "end_at": .85}]
    style = profile("reference", payload)
    prompts = ["A wide photograph of a large underground archive chamber, rows of sealed steel storage cabinets, cold gray concrete walls, empty room, different layout from a corridor, cinematic industrial architecture",
               "A wide photograph of an underground turbine hall, one enormous cylindrical steel machine with orderly pipes, service platforms and cold overhead lights, empty room, industrial photography"]
else:
    payload = copy.deepcopy(baseline)
    for key in ("style_id", "revision", "style_key", "visual_baseline", "asset_ids", "model_manifest", "origin"):
        payload.pop(key, None)
    payload.update(display_name="冷色设施摄影 · 图生图", mode="img2img")
    payload["locked_generation_settings"].pop("second_pass", None)
    payload["locked_generation_settings"]["first_pass"].update(denoise=.5, steps=20)
    style = profile("img2img", payload)
    prompts = ["A cinematic photograph of the industrial containment room, warm red emergency lights added on the walls, realistic steel and concrete, empty room, preserve the large doors and architectural layout"]

sid = "SC-TEST-" + args.case.upper() + ("-PONY" if args.case == "illustration" else "")
store.create_series(style["style_key"], "验收 · " + args.case, sid, isolated=True)
for i, prompt in enumerate(prompts):
    request = {"brief": f"验收 {args.case} 主题{i+1}", "prompt": prompt, "negative": "people, watermark, text, low quality",
               "style": style["style_key"], "series_id": sid, "seed": 20261007000 + i,
               "output": {"width": 1001 if args.case in ("photo", "img2img") and i == 0 else 1536,
                          "height": 733 if args.case in ("photo", "img2img") and i == 0 else 1024},
               "constraints": {"must": ["empty room"], "avoid": ["people", "text"]}, "materials": [material["id"]]}
    if args.case == "img2img":
        request["references"] = [{"material_id": material["id"], "role": "structure"}]
    try:
        job = prepare(store, request)
        print(f"Running {args.case} {i+1}: {job['id']}", flush=True)
        job = run(store, job["id"])
        result = {"job_id": job["id"], "style": job["style_key"], "status": job["status"],
                  "images": [{"path": x.get("latest_path"), "attempts": len(x["attempts"]), "last": x["attempts"][-1]} for x in job["images"]]}
        results.append(result)
        print(f"Result {job['status']}: {[x.get('latest_path') for x in job['images']]}", flush=True)
    except SeriesError as exc:
        results.append({"status": "failed", "code": exc.code, "message": str(exc), "details": exc.details})
        print(f"Failed {exc.code}: {exc.details}", flush=True)
    write_json(config.data / "acceptance" / (args.case + ".json"), {"created_at": now(), "results": results})
