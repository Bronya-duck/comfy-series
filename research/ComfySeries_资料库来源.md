# ComfySeries 资料库来源

核查日期：2026-10-07。范围是第一方网站、作者源码、官方模型卡和只读接口资料。本次没有安装节点或依赖、下载模型权重、修改 ComfyUI、重启服务或提交生图。

已收录 **40 条去重来源：5 个来源项目、10 个工作流、6 个模型、19 个文档条目**。机器可读索引在 [library_seed.json](D:/_SCP生图逻辑/data/library_seed.json)，所有条目的 `validation_status` 都是 `unverified`；`checked_at` 表示查阅日期，不代表本机执行通过。

## 可复用资料与当前机器的边界

- 官方模板库采用 MIT；作者示例库的 LICENSE 明确允许使用、复制、修改和分发工作流，但 GitHub 未将其识别为标准 SPDX 许可。cubiq 节点仓库与其中示例采用 GPL-3.0。模板许可不能替代所需模型的许可。[官方模板 LICENSE](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/LICENSE)、[作者示例 LICENSE](https://github.com/comfyanonymous/ComfyUI_examples/blob/f9431bb000ce792094ff345446e22cac1ea6cef3/LICENSE)、[cubiq LICENSE](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/LICENSE)
- 官方 SDXL 基础图可作为文生图结构起点；img2img、LoRA、ControlNet 和两种采样放大的归档图原本使用 SD1.5。它们可以说明接法，但不能据此把 SD1.5 权重套到现有 SDXL 模型。[SDXL 图](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/templates/image_sdxl_simple.json)、[img2img 图](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/image2image.json)
- 当前用户需求优先选择 SDXL 的风格参考分支。cubiq 的精准权重比较图展示 `style transfer` 和 `style transfer precise`；图像从噪声重新生成时可以重新组织内容。图生图的输入则先进入 VAE 编码，会保留更多原始内容与构图。风格迁移也不能保证完全去除参考图内容影响。[SDXL 风格比较图](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/examples/ipadapter_precise_weight_type.json)、[节点说明](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/NODES.md)、[作者 img2img 说明](https://comfyanonymous.github.io/ComfyUI_examples/img2img/)
- SDXL Plus 最小权重候选是一份 848MB 的 adapter 加一份 2.53GB 的 ViT-H 图像编码器，额外磁盘空间约 3.38GB。这里的文件大小不是显存峰值；没有测得 ComfyUI 0.3.64、torch 2.8 与 8GB 显卡的运行结果。cubiq 于 2025-04-14 声明仅维护，并要求最新 ComfyUI，因此兼容性仍须后续验证。[adapter 文件](https://huggingface.co/h94/IP-Adapter/blob/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors)、[encoder 文件](https://huggingface.co/h94/IP-Adapter/blob/main/models/image_encoder/model.safetensors)、[作者维护声明](https://github.com/cubiq/ComfyUI_IPAdapter_plus)
- 本机只读 `/object_info` 对比发现，SDXL、img2img、LoRA、ControlNet、ESRGAN 和 latent upscale 缓存图中的运行节点名称均有对应项；模型选择、参数、权重完整性、输出效果和显存未验证。IPAdapter 自定义节点尚未加载；插值比较模板中的 `ImageCompare` 也未在当前清单中。
- ControlNet 缓存图中有 Canny 节点，却声明 SD1.5 scribble 权重，执行前应核对控制图语义。不要因为它来自官方库就省略检查。[原始 ControlNet 图](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/controlnet_example.json)、[作者对控制图格式的说明](https://comfyanonymous.github.io/ComfyUI_examples/controlnet/)

## 已缓存的小型工作流

保留原始画布 JSON 的文本内容，不修改节点、权重名或提示词；缓存可能补齐文件末尾换行，因而分别记录来源 Git blob SHA 和本地 SHA-256。缓存文件不是直接可提交的 API JSON。画布注释与 PrimitiveNode 等前端节点要在编译时单独处理。[Workflow JSON 规范](https://docs.comfy.org/specs/workflow_json)

| ID | 架构 | 缓存文件 | 当前缺少的运行节点 |
|---|---|---|---|
| `official-sdxl-simple` | SDXL | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-sdxl-simple.json) | 仅名称检查未发现缺项 |
| `official-interpolation-upscale` | agnostic | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-interpolation-upscale.json) | `ImageCompare` |
| `official-lora` | SD1.5 | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-lora.json) | 仅名称检查未发现缺项 |
| `official-controlnet` | SD1.5 | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-controlnet.json) | 仅名称检查未发现缺项 |
| `ipadapter-advanced` | SD1.5 | [JSON](D:/_SCP生图逻辑/data/library/workflows/ipadapter-advanced.json) | `IPAdapterAdvanced`、`IPAdapterModelLoader`、`PrepImageForClipVision` |
| `ipadapter-style-composition` | SDXL | [JSON](D:/_SCP生图逻辑/data/library/workflows/ipadapter-style-composition.json) | `IPAdapterStyleComposition`、`IPAdapterUnifiedLoader` |
| `ipadapter-precise-weight-type` | SDXL | [JSON](D:/_SCP生图逻辑/data/library/workflows/ipadapter-precise-weight-type.json) | `IPAdapterAdvanced`、`IPAdapterUnifiedLoader` |
| `official-img2img` | SD1.5 | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-img2img.json) | 仅名称检查未发现缺项 |
| `official-esrgan-upscale` | SD1.5 + ESRGAN | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-esrgan-upscale.json) | 仅名称检查未发现缺项 |
| `official-latent-upscale` | SD1.5 | [JSON](D:/_SCP生图逻辑/data/library/workflows/official-latent-upscale.json) | 仅名称检查未发现缺项 |

官方模板固定提交为 `b4119d0fcecf78a376e087305ec4f485c66a03f5`，cubiq 固定提交为 `a0f451a5113cf9becb0847b92884cb10cbdec0ef`。许可证副本保存在 [licenses](D:/_SCP生图逻辑/data/library/licenses)。数据索引中每个缓存条目包含 `cached_path`、`revision`、`source_blob_sha`、`cached_sha256`、`required_models`、`required_nodes` 和 `missing_current_nodes`。

## 检索与下载接口

| 来源 | 可以借助什么 | 本次证据与访问限制 |
|---|---|---|
| Hugging Face | `HfApi.list_models` 检索；模型卡核对架构和许可；`hf_hub_download` 固定完整提交下载指定文件。 | 文档与 H94 文件页可读。浏览工具不能打开本次模型详情 API URL，Shell 的公网 HTTPS 请求发生 SSL 错误；没有下载大型权重或验证本机下载器。根据官方文档区分 API、resolve 和网页限流，处理 429。 |
| CivitAI | 使用当前官方开发者站的模型、版本及下载文档入口。 | 官方 GitHub Wiki 已标注迁移；新站与此次只读模型查询在工具环境无法打开。保留入口和限制，不把旧 Wiki 参数或匿名下载能力当作当前保证。 |
| Comfy Registry | 节点包发现、版本查询、固定版本；官方索引也列出按 ComfyUI 节点类名查询所属包。 | API 总览与 llms 索引可读；若干详细路由页面无法打开，未调用安装或写入接口。它是节点包来源目录，不是模型权重仓库。 |
| GitHub | 按完整提交读取工作流 JSON 和 LICENSE，小型资料可以本地缓存。 | GitHub connector 实际取回本文 10 份 JSON。模板目录 contents 返回最多 1000 项，因此改用完整递归 Git tree，其响应 `truncated=false`；避免把目录截断当作完整列表。 |

依据：[HF 检索](https://huggingface.co/docs/huggingface_hub/guides/search)、[HF 固定版本下载](https://huggingface.co/docs/huggingface_hub/guides/download)、[HF 限流](https://huggingface.co/docs/hub/rate-limits)、[CivitAI 官方迁移说明](https://github.com/civitai/civitai/wiki/REST-API-Reference)、[Registry API 总览](https://docs.comfy.org/registry/api-reference/overview)、[Comfy 官方文档索引](https://docs.comfy.org/llms.txt)。工具无法打开某个 URL 是本次访问结果，不代表网站对所有用户停用。

## 值得借鉴的控制层

comfy-agent 的 CLI 与本地档案适合参考：角色档案含 style、prompt_template、references、LoRA 和画廊；`brief` 先读取适用性，`reference_image` 与 `init_image` 分开。它并未替我们验证当前工作流。VibeComfy 更偏工作流编写和来源记录，导入后保存 Python bundle 与来源信息，再静态检查、编译成 API JSON；索引其代理指南并不授权执行其中安装或运行指令。[comfy-agent CLI](https://github.com/shinshin86/comfy-agent/blob/3015580bd86b5f2cb8e0f38bd8efb5379c089055/docs/cli-reference.md)、[VibeComfy](https://github.com/peteromallet/VibeComfy)、[VibeComfy 代理指南](https://github.com/peteromallet/VibeComfy/blob/b1429c634e6c8ab44222c5e9901c318181f709f7/docs/agent-skill/SKILL.md)

## 完整来源索引

表中摘要均为资料用途说明，统一执行状态是 `unverified`。模型和节点列表以 JSON 索引为准；`docs` 的空列表表示文档本身无需运行依赖，不能推断文档覆盖的所有工作流都无依赖。

| ID | 第一方来源 | 类型 / 架构 | 用途与限制 |
|---|---|---|---|
| `comfy-official-templates` | [Comfy 官方工作流模板库](https://github.com/Comfy-Org/workflow_templates) | source / multi | 官方模板和子图库；新模板持续加入，不能据来源身份推断与 ComfyUI 0.3.64 兼容。 |
| `comfy-author-examples` | [ComfyUI 作者示例库](https://github.com/comfyanonymous/ComfyUI_examples) | source / multi | 作者发布的示例图片内嵌工作流元数据，可导入画布；资料库仅缓存链接，未下载示例图片。 |
| `example-sdxl` | [作者示例：SDXL 与 ReVision](https://comfyanonymous.github.io/ComfyUI_examples/sdxl/) | docs / SDXL | SDXL base 可单独运行；另展示 refiner、双提示词和 ReVision。ReVision 提取图像概念，不能视为纯风格分离的等价实现。 |
| `example-img2img` | [作者示例：Img2Img](https://comfyanonymous.github.io/ComfyUI_examples/img2img/) | docs / SD1.5/SDXL | 通过 VAE 编码输入图作为采样初始潜空间，denoise 控制改动程度；会保留输入内容和布局，与仅参考风格有所不同。 |
| `example-lora` | [作者示例：LoRA](https://comfyanonymous.github.io/ComfyUI_examples/lora/) | docs / SD1.5/SDXL | LoRA 加载器同时修改 MODEL 和 CLIP，多个 LoRA 可串联；示例中的具体模型须单独核对架构。 |
| `example-controlnet` | [作者示例：ControlNet 与 T2I-Adapter](https://comfyanonymous.github.io/ComfyUI_examples/controlnet/) | docs / SD1.5/SDXL | 控制图必须匹配权重所需语义，加载节点不会自动计算深度、姿态或边缘；SDXL Control-LoRA 按 ControlNet 路线使用。 |
| `example-upscale-models` | [作者示例：模型放大](https://comfyanonymous.github.io/ComfyUI_examples/upscale_models/) | docs / agnostic | 说明 ESRGAN 等放大模型的原生加载与应用节点，以及 upscale_models 目录。 |
| `example-hires-fix` | [作者示例：两次采样 / Hires fix](https://comfyanonymous.github.io/ComfyUI_examples/2_pass_txt2img/) | docs / SD1.5/SDXL | 展示潜空间放大后再次采样、像素放大再编码，以及两阶段切换模型/提示词的做法。 |
| `example-inpaint` | [作者示例：局部重绘](https://comfyanonymous.github.io/ComfyUI_examples/inpaint/) | docs / SD1.5/SDXL | 展示掩码局部重绘；普通模型与专用重绘模型的接法和表现需要分别验证。 |
| `official-sdxl-simple` | [官方模板：SDXL 基础文生图](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/templates/image_sdxl_simple.json) | workflow / SDXL | 最小 SDXL 文生图主体；原始权重为 sd_xl_base_1.0，运行前需换成已核对的本机 SDXL 文件。MarkdownNote 是画布说明。 |
| `official-interpolation-upscale` | [官方模板：插值缩放与对比](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/templates/utility_interpolation_image_upscale.json) | workflow / agnostic | 不用神经网络权重的插值缩放；图中 ImageCompare 不在当前 0.3.64 节点清单，需适配后才能执行。 |
| `official-lora` | [官方归档模板：串联 LoRA](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/lora.json) | workflow / SD1.5 | 原 JSON 串联 blindbox 与 MoXin，基础为 DreamShaper 8；具体模型许可独立于模板 MIT，不将这些 SD1.5 LoRA 推荐给 SDXL。 |
| `official-controlnet` | [官方归档模板：ControlNet 控制图](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/controlnet_example.json) | workflow / SD1.5 | 图中使用 Canny 预处理，但模型名为 SD1.5 scribble；控制图与模型语义应人工复核。只作节点结构参考，不作为可直接运行的 SDXL 图。 |
| `ipadapter-advanced` | [cubiq 示例：Advanced 显式模型加载](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/examples/ipadapter_advanced.json) | workflow / SD1.5 | 展示显式 adapter + 原生 CLIPVisionLoader + Advanced 接法；原图是 SD1.5 与线性权重，不能标成现成 SDXL 纯风格模板。 |
| `ipadapter-style-composition` | [cubiq 示例：SDXL 风格与构图双参考](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/examples/ipadapter_style_composition.json) | workflow / SDXL | 两张图分别参考风格与构图，原图为 AlbedoBaseXL；用户仅要风格时应另构图并保留必要分支。 |
| `ipadapter-precise-weight-type` | [cubiq 示例：SDXL 普通/精准风格迁移比较](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/examples/ipadapter_precise_weight_type.json) | workflow / SDXL | 原图用 ProteusV0.3，比对 style transfer 与 style transfer precise；两条生成分支不是 8GB 最小图，PrimitiveNode 需在编译时处理。 |
| `official-img2img` | [官方归档模板：基础图生图](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/image2image.json) | workflow / SD1.5 | 输入图缩放、VAE 编码再采样；原示例使用 SD1.5，作为流程结构参考，不能原样替换成 SDXL 后即认定可运行。 |
| `official-esrgan-upscale` | [官方归档模板：ESRGAN 图片放大](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/esrgan_example.json) | workflow / SD1.5 + ESRGAN | 先以 DreamShaper 8 生图再用 RealESRGAN 放大；可借鉴独立放大分支，原始 checkpoint 非 SDXL。 |
| `official-latent-upscale` | [官方归档模板：潜空间二次采样放大](https://github.com/Comfy-Org/workflow_templates/blob/b4119d0fcecf78a376e087305ec4f485c66a03f5/archived/hiresfix_latent_workflow.json) | workflow / SD1.5 | 两次采样中间放大 latent；原始 DreamShaper 8 为 SD1.5。增加采样与显存需求，当前机器未运行。 |
| `cubiq-ipadapter-pack` | [cubiq ComfyUI IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) | source / SD1.5/SDXL | 作者自 2025-04-14 进入仅维护状态，README 要求最新 ComfyUI；本机 0.3.64/torch2.8/8GB 未实测。纯风格候选可只白名单这一个节点包。 |
| `ipadapter-node-reference` | [IPAdapter 节点与权重模式说明](https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/a0f451a5113cf9becb0847b92884cb10cbdec0ef/NODES.md) | docs / SD1.5/SDXL | 解释显式/统一加载器、weight_type 和起止时间；非正方形参考会中心裁切。文档的仅迁移风格描述是设计目标，并非零内容泄漏保证。 |
| `model-ipadapter-plus-sdxl` | [H94 SDXL Plus ViT-H adapter](https://huggingface.co/h94/IP-Adapter/blob/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors) | model / SDXL | SDXL Plus 风格参考候选，848MB；需 ViT-H 图像编码器与 cubiq 节点包，不能单独生成。未下载权重。 |
| `model-ipadapter-vit-h-encoder` | [H94 配套 ViT-H 图像编码器](https://huggingface.co/h94/IP-Adapter/blob/main/models/image_encoder/model.safetensors) | model / CLIP ViT-H/14 | 匹配 SDXL Plus ViT-H 的图像编码器，2.53GB；按 cubiq 约定重命名后放入 clip_vision，未下载权重。 |
| `model-laion-vit-h` | [LAION ViT-H 原始模型卡](https://huggingface.co/laion/CLIP-ViT-H-14-laion2B-s32B-b79K) | model / CLIP ViT-H/14 | 图像编码器来源与许可证依据；ComfyUI 使用的重打包文件应保留原始模型信息。 |
| `model-sdxl-base` | [Stability AI SDXL Base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) | model / SDXL | 官方 SDXL base 可独立运行；refiner 是可选第二阶段。模型卡明确存在文本、脸部和复杂组合表达的局限，当前项目已有 SDXL 模型未因此要求下载它。 |
| `model-sdxl-control-lora` | [Stability AI SDXL Control-LoRA](https://huggingface.co/stabilityai/control-lora) | model / SDXL | 为深度、Canny、recolor、sketch 等条件提供紧凑 ControlNet 类权重；用于结构控制，不能替代纯风格参考。 |
| `model-real-esrgan` | [Comfy-Org Real-ESRGAN Safetensors 重打包](https://huggingface.co/Comfy-Org/Real-ESRGAN_repackaged) | model / Real-ESRGAN | 官方重打包 RealESRGAN_x4plus，放入 upscale_models；是否满足输出质量与显存仍需本机测试。 |
| `hf-search-api` | [Hugging Face：模型检索接口](https://huggingface.co/docs/huggingface_hub/guides/search) | docs / agnostic | HfApi.list_models 支持 search、author、filter、limit 等检索条件；检索结果的许可证、文件和架构必须逐项核对。本文未运行 SDK。 |
| `hf-download-api` | [Hugging Face：固定版本下载](https://huggingface.co/docs/huggingface_hub/guides/download) | docs / agnostic | hf_hub_download 支持文件名和完整 revision；可用 allow_patterns 限制 snapshot 下载。应固定提交并核对哈希，当前仅下载小型 GitHub JSON。 |
| `hf-model-card-metadata` | [Hugging Face：模型卡与许可字段](https://huggingface.co/docs/hub/model-cards) | docs / agnostic | 模型卡元数据可给出 license、base_model 和相关标签；字段缺失不能推断许可或兼容性。 |
| `hf-rate-limits` | [Hugging Face：API 与文件下载限流](https://huggingface.co/docs/hub/rate-limits) | docs / agnostic | API、resolve 下载、网页请求有独立限流；429 与 RateLimit 响应头应触发等待/重试，免费匿名额度可能调整。 |
| `civitai-model-api` | [CivitAI：当前模型 API 文档入口](https://developer.civitai.com/site/reference) | docs / agnostic | 官方 GitHub Wiki 已于 2026-04-30 指向此新站；本次浏览新站和模型查询接口受限。只索引官方入口，不保证旧 Wiki 参数与匿名下载仍适用。 |
| `comfy-registry-overview` | [Comfy Registry：节点发现与版本](https://docs.comfy.org/registry/overview) | docs / agnostic | 官方 Registry 是自定义节点包目录，可发现节点、固定包版本；节点审核标记不能证明特定工作流在当前机器运行。 |
| `comfy-registry-api` | [Comfy Registry：API 总览与入口](https://docs.comfy.org/registry/api-reference/overview) | docs / agnostic | 总览列出节点列表和安装版本接口；llms 索引另列按 ComfyUI 类名寻找包、版本查询。具体路由页面本次受限，未调用安装接口。 |
| `comfy-agent-project` | [shinshin86 comfy-agent CLI](https://github.com/shinshin86/comfy-agent) | source / agnostic | 可连接 ComfyUI、导入图、运行与保存本地记录，并提供 Codex skill。核心复用已有/导入工作流，README 的云端验证不等于本机 8GB 验证。 |
| `comfy-agent-character-memory` | [comfy-agent：角色/风格/参考档案接口](https://github.com/shinshin86/comfy-agent/blob/3015580bd86b5f2cb8e0f38bd8efb5379c089055/docs/cli-reference.md) | docs / agnostic | character 元数据有 style、prompt_template、references 和 LoRA，brief 加载适用性；reference_image 不自动填入 init_image，可借鉴风格参考与图生图角色分离。 |
| `vibecomfy-project` | [VibeComfy：Python 工作流编写层](https://github.com/peteromallet/VibeComfy) | source / multi | 将来源 JSON 导入可编辑 Python bundle，保存来源、静态检查并编译 API JSON；可借鉴来源记录和工作流选择流程，不因索引此项目而安装其 ComfyUI extra。 |
| `vibecomfy-agent-guide` | [VibeComfy：代理工作流规则来源](https://github.com/peteromallet/VibeComfy/blob/b1429c634e6c8ab44222c5e9901c318181f709f7/docs/agent-skill/SKILL.md) | docs / multi | 介绍模板检索、导入、检查、编译和运行边界；作为设计资料索引，不自动应用其安装或运行指令。 |
| `comfy-workflow-json-spec` | [ComfyUI：画布工作流 JSON 规范](https://docs.comfy.org/specs/workflow_json) | docs / agnostic | 画布 JSON 包含节点、连线与界面数据；不应直接当成 /prompt API 执行字典，导入/编译须处理前端节点与 widgets。 |
| `comfy-server-routes` | [ComfyUI：HTTP / WebSocket 路由](https://docs.comfy.org/development/comfyui-server/comms_routes) | docs / agnostic | 描述 object_info、prompt、history、queue、upload/image、view 和 WebSocket 等接口；当前 0.3.64 以本机实际返回为准，新增路由不能直接假定存在。 |

## 后续采用资料的顺序

1. 从当前 SDXL 基础图和目标宽高开始，检查本机模型名与节点接口。
2. 风格参考优先借鉴 SDXL IPAdapter 精准权重示例，去掉对比输出等非必要分支，并保留固定参考文件与参数记录。
3. img2img、ControlNet、LoRA 和放大作为按任务启用的分支，分别核对模型家族和许可；不要一次导入全部依赖。
4. 来源查阅、JSON 可解析、节点名称存在、模型成功加载、生成完成、视觉自检是不同证据。只有完成相应运行检查，才应更新本机验证状态。

