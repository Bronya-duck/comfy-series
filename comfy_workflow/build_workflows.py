"""Create matching ComfyUI canvas and API workflows using installed core nodes."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
MODEL = "juggernautXL_XI.safetensors"
SEED = 2026100701
POSITIVE = (
    "A cinematic wide photograph of an underground containment laboratory, "
    "a single large sealed observation chamber at the end of a concrete corridor, "
    "reinforced steel doors, thick glass observation windows, exposed pipes and cables, "
    "cold overhead fluorescent lighting with a subtle red emergency light, "
    "realistic industrial materials, restrained atmosphere of mystery and unease, "
    "empty facility, symmetrical composition, eye level camera, 24mm lens, "
    "physically plausible architecture, crisp details, subtle film grain"
)
NEGATIVE = (
    "anime, cartoon, illustration, people, person, monster, gore, blood, "
    "watermark, logo, text, oversaturated, blurry, low quality, distorted perspective"
)

def api_graph(hires=True):
    g = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": MODEL}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": POSITIVE, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1216, "height": 832, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            "seed": SEED, "steps": 30, "cfg": 5.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
        "6": {"class_type": "VAEDecodeTiled", "inputs": {
            "samples": ["5", 0], "vae": ["1", 2], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "SCP_Juggernaut_XI/base"}},
    }
    if hires:
        g.update({
            "8": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "RealESRGAN_x2plus.pth"}},
            "9": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["8", 0], "image": ["6", 0]}},
            "10": {"class_type": "ImageScaleBy", "inputs": {"image": ["9", 0], "upscale_method": "lanczos", "scale_by": 0.75}},
            "11": {"class_type": "VAEEncodeTiled", "inputs": {
                "pixels": ["10", 0], "vae": ["1", 2], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
            "12": {"class_type": "KSampler", "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["11", 0],
                "seed": SEED, "steps": 18, "cfg": 5.0, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.20}},
            "13": {"class_type": "VAEDecodeTiled", "inputs": {
                "samples": ["12", 0], "vae": ["1", 2], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
            "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "SCP_Juggernaut_XI/final"}},
        })
    return g

NODE_SPECS = {
    1: ("01 · 主模型（内含 CLIP / VAE）", [40, 150], [320, 140], [MODEL], [], [("MODEL", "MODEL"), ("CLIP", "CLIP"), ("VAE", "VAE")]),
    2: ("02 · 正向提示词（修改画面内容）", [420, 60], [450, 275], [POSITIVE], [("clip", "CLIP")], [("CONDITIONING", "CONDITIONING")]),
    3: ("02 · 负向提示词（避免的内容）", [420, 375], [450, 180], [NEGATIVE], [("clip", "CLIP")], [("CONDITIONING", "CONDITIONING")]),
    4: ("03 · 画幅与批量（8GB 先用 batch=1）", [40, 365], [320, 140], [1216, 832, 1], [], [("LATENT", "LATENT")]),
    5: ("04 · 第一遍生成（完整去噪）", [940, 130], [320, 280], [SEED, "fixed", 30, 5.0, "dpmpp_2m", "karras", 1.0], [("model", "MODEL"), ("positive", "CONDITIONING"), ("negative", "CONDITIONING"), ("latent_image", "LATENT")], [("LATENT", "LATENT")]),
    6: ("05 · 原图分块解码（节省显存）", [1320, 45], [315, 215], [512, 64, 64, 8], [("samples", "LATENT"), ("vae", "VAE")], [("IMAGE", "IMAGE")]),
    7: ("06 · 保存原图 1216×832", [1700, 45], [350, 345], ["SCP_Juggernaut_XI/base"], [("images", "IMAGE")], []),
    8: ("07 · 加载官方 Real-ESRGAN 放大模型", [40, 965], [320, 100], ["RealESRGAN_x2plus.pth"], [], [("UPSCALE_MODEL", "UPSCALE_MODEL")]),
    9: ("08 · 图像超分辨率 2 倍", [420, 820], [320, 100], [], [("upscale_model", "UPSCALE_MODEL"), ("image", "IMAGE")], [("IMAGE", "IMAGE")]),
    10: ("09 · 缩至 1.5 倍（照顾 8GB 显存）", [800, 820], [310, 120], ["lanczos", 0.75], [("image", "IMAGE")], [("IMAGE", "IMAGE")]),
    11: ("10 · 分块编码高清图", [1160, 820], [310, 200], [512, 64, 64, 8], [("pixels", "IMAGE"), ("vae", "VAE")], [("LATENT", "LATENT")]),
    12: ("11 · 第二遍细化（轻度重绘）", [1520, 820], [320, 280], [SEED, "fixed", 18, 5.0, "dpmpp_2m", "karras", 0.20], [("model", "MODEL"), ("positive", "CONDITIONING"), ("negative", "CONDITIONING"), ("latent_image", "LATENT")], [("LATENT", "LATENT")]),
    13: ("12 · 高清图分块解码", [1900, 820], [310, 215], [512, 64, 64, 8], [("samples", "LATENT"), ("vae", "VAE")], [("IMAGE", "IMAGE")]),
    14: ("13 · 保存细化图 1824×1248", [2260, 820], [350, 345], ["SCP_Juggernaut_XI/final"], [("images", "IMAGE")], []),
}

def canvas_graph(api, hires):
    nodes = []
    for sid, data in api.items():
        nid = int(sid)
        title, pos, size, widgets, inputs, outputs = NODE_SPECS[nid]
        nodes.append({
            "id": nid, "type": data["class_type"], "title": title, "pos": pos, "size": size,
            "flags": {}, "order": nid - 1, "mode": 0,
            "inputs": [{"name": name, "type": typ, "link": None} for name, typ in inputs],
            "outputs": [{"name": name, "type": typ, "links": []} for name, typ in outputs],
            "properties": {"Node name for S&R": data["class_type"]}, "widgets_values": widgets,
        })
    byid = {n["id"]: n for n in nodes}
    links = []
    for sid, data in api.items():
        target = byid[int(sid)]
        for slot, inp in enumerate(target["inputs"]):
            source_id, source_slot = data["inputs"][inp["name"]]
            source = byid[int(source_id)]
            assert source["outputs"][source_slot]["type"] == inp["type"]
            lid = len(links) + 1
            links.append([lid, int(source_id), source_slot, int(sid), slot, inp["type"]])
            inp["link"] = lid
            source["outputs"][source_slot]["links"].append(lid)
    note = (
        "模型：本机 juggernautXL_XI.safetensors，使用内置 CLIP 与 VAE。\n"
        "修改正向提示词即可更换主题；本例是虚构收容设施的环境照片。\n"
        "固定 seed 方便比较参数；需要新构图时更换 seed。\n"
        "batch=1；第一遍 30 步、CFG 5、dpmpp_2m + karras。\n"
        + ("Real-ESRGAN 2 倍放大后缩到 1.5 倍；第二遍 denoise=0.20，可能改变细节。\n" if hires else "此版本只保存原图，适合快速试提示词。\n")
        + "所有生成节点均为 ComfyUI 内置节点，无需安装插件。"
    )
    nodes.append({"id": 15, "type": "Note", "title": "使用说明", "pos": [40, 585], "size": [650, 230], "flags": {}, "order": len(nodes), "mode": 0, "inputs": [], "outputs": [], "properties": {}, "widgets_values": [note], "color": "#432", "bgcolor": "#653"})
    return {"last_node_id": 15, "last_link_id": len(links), "nodes": nodes, "links": links, "groups": [], "config": {}, "extra": {"ds": {"scale": 0.5 if hires else 0.75, "offset": [25, 25]}}, "version": 0.4}

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, hires in [("01_juggernaut_xi_base", False), ("02_juggernaut_xi_complete", True)]:
        api = api_graph(hires)
        canvas = canvas_graph(api, hires)
        write_json(ROOT / f"{name}.json", canvas)
        write_json(ROOT / f"{name}.api.json", api)
        print(f"{name}: {len(api)} executable nodes, {len(canvas['links'])} typed links")
    write_json(ROOT / "environment.json", {
        "comfyui": "0.3.64", "gpu": "NVIDIA GeForce RTX 5070 Laptop GPU", "vram_mib": 8151,
        "torch": "2.8.0+cu129", "cuda": "12.9", "cuda_tensor_test": "passed",
        "model": MODEL, "checkpoint_dir": "D:/comfyui/ComfyUI_windows_portable/ComfyUI/models/checkpoints",
        "base_resolution": [1216, 832], "hires_resolution": [1824, 1248], "seed": SEED,
        "upscaler": "RealESRGAN_x2plus.pth", "upscaler_bytes": 67061725,
        "upscaler_source": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "upscaler_sha256": "49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb",
    })
