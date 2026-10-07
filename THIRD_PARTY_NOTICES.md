# 第三方来源与许可记录

Comfy Series 的创作判断在当前 Codex 完成，HTTP 执行后端为已有 [ComfyUI](https://github.com/Comfy-Org/ComfyUI)。未复制 comfy-agent、VibeComfy 或 Comfy MCP 的执行代码；借鉴其公开文档中的档案、校验和来源管理方式，完整固定版本链接保存在资料库。

| 内容 | 来源及许可 | 本地用途 |
|---|---|---|
| ComfyUI IPAdapter Plus | [cubiq 仓库](https://github.com/cubiq/ComfyUI_IPAdapter_plus/tree/a0f451a5113cf9becb0847b92884cb10cbdec0ef)，GPL-3.0 | `data/vendor`保持原源码与许可证，白名单加载 |
| SDXL Plus ViT-H 权重 | [H94 固定版本](https://huggingface.co/h94/IP-Adapter/tree/018e402774aeeddd60609b4ecdb7e298259dc729)，Apache-2.0 | 本地风格参考 |
| 配套图像编码器 | 上述 H94 重新打包；[LAION 原始模型卡](https://huggingface.co/laion/CLIP-ViT-H-14-laion2B-s32B-b79K)标注 MIT | 保留打包和原模型两份来源信息 |
| 官方工作流 JSON | [workflow_templates](https://github.com/Comfy-Org/workflow_templates)，MIT | 精选缓存，许可证在 `data/library/licenses` |
| IPAdapter 示例 JSON | 上述 cubiq GPL-3.0 仓库 | 精选缓存，仅作结构资料 |
| ComfyUI 作者示例 | [ComfyUI_examples](https://github.com/comfyanonymous/ComfyUI_examples) | 索引网址及其允许使用工作流的许可正文 |
| 既有 Juggernaut XI / WAI Pony 权重 | 本机预装，原始下载记录缺失；本地哈希已固定 | 未重新下载；精确上游文件身份与原始许可待核实 |
| 既有 RealESRGAN_x2plus | [作者 release v0.2.1](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.1)，项目 BSD-3-Clause | 原环境记录了下载网址与本地哈希 |

Juggernaut 作者当前 [模型卡](https://huggingface.co/RunDiffusion/Juggernaut-XI-v11)列出访问条件和许可；仅凭本机改名文件，不能断定其与该发布版本逐字节相同。本项目保留这个核实缺口。WAI Pony 的精确原始页面本次未能定位。所有元数据会区分已核实来源、候选来源与未核实条目。

网页资料仅保存网址和原创摘要，不复制整站文档。运行通过标签只适用于记录的实际本机工作流，不代表第三方的全部能力已验证。
