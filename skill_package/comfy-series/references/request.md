# 请求与风格

请求示例（prompt由Codex根据素材整理，SDXL通常使用英文描述）：

```json
{
  "brief": "冷色地下档案室，无人物",
  "prompt": "A cinematic photograph of a large underground archive room, tall steel shelves, cold fluorescent lighting, empty room",
  "negative": "watermark, low quality",
  "style": "S001-v1",
  "series_id": "SC001",
  "output": {"width": 1536, "height": 1024, "count": 2, "format": "PNG"},
  "seed": 2026100701,
  "references": [],
  "materials": [],
  "constraints": {"must": ["钢制书架"], "avoid": ["people", "text"]}
}
```

`style`也可为`【同风格:S001】`或`【同风格:上一张】`。未给series_id时优先复用相同风格版本的正式系列，没有匹配项时才新建；沿用返回的series_id可明确锁定累计预算。每系列固定一个明确style_key，换版本创建新系列。精确width/height需同时给出；只提供`aspect_ratio:"3:2"`时按默认面积推导精确比例的宽高。第一版PNG、单次最多100张，逐张生成；单边最多16384、总像素最多6400万，能力不足解释差距。

`references`只放图像，字段为`material_id`或`path`，及`role`（style默认；subject/composition/structure/context）。文档或文字用ingest得到的编号放入`materials`，实际内容提炼到prompt并保留出处。图生图用subject/structure/composition参考；参考图在该模式会被按目标画幅中心裁切再编码。

可选`generation:{"width":1216,"height":832}`用于生成尺寸，每边至少64且为8倍数，与最终比例接近；通常让工具自动选。最终尺寸独立处理，较低生成分辨率放大不能保证增加真实细节。重试patch只允许prompt、negative、seed、generation，维持原任务输出与风格。

新风格档案示例：

```json
{
  "display_name": "冷色工业摄影",
  "mode": "txt2img",
  "locked_generation_settings": {
    "checkpoint": "juggernautXL_XI.safetensors",
    "loras": [],
    "reference_conditioning": [],
    "first_pass": {"steps":30,"cfg":5,"sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1},
    "upscaling": {"model":"RealESRGAN_x2plus.pth","resize_method":"lanczos","resize_scale":0.75}
  },
  "prompt_blocks": {
    "fixed_positive_style":"cinematic photograph, realistic materials, cold lighting, subtle film grain",
    "fixed_negative_style":"cartoon, oversaturated, blurry, watermark"
  },
  "defaults": {"base_resolution":[1216,832],"output_resolution":[1824,1248]}
}
```

修改已有风格时加`style_id:"S001"`，工具自动分配新revision，保留旧版本。图生图使用`mode:"img2img"`和first_pass.denoise（例如0.5）；保留结构多少应实际比较。LoRA条目为name/strength_model/strength_clip。

IPAdapter风格条件放入reference_conditioning，每张风格样本一条：

```json
{
  "method":"ipadapter",
  "material_id":"M-实际素材编号",
  "sha256":"实际参考图哈希",
  "model":"ip-adapter-plus_sdxl_vit-h.safetensors",
  "clip_vision":"CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
  "weight":0.6,
  "weight_type":"style transfer",
  "start_at":0,
  "end_at":0.85
}
```

多个样本需降低各自权重并实际看图，避免内容混入。没有图像条件时，只有看图提取提示词的参考应在请求加`workflow:{"reference_method":"description"}`。

评审为JSON数组，每个结果指定实际图片与轮次：

```json
[{"index":0,"round":1,"viewed_path":"实际输出绝对路径",
  "checks":{"subject":"pass","composition":"pass","style":"pass","defects":"pass"},
  "accepted":true,"notes":"实际看图后的具体观察"}]
```

检查状态为pass/partial/fail；有partial/fail时accepted=false。三轮后保留best_path与差距。首张全部通过的图片登记初始基准，后续可按用户选择更换。
