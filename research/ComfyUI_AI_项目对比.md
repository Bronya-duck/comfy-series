# 用自然语言驱动 ComfyUI 的项目对比

调研日期：2026-10-07（北京时间）。调研范围：项目官方仓库、官方文档和作者论文；没有安装这些项目，也没有在本机做运行验证。下文“支持”表示公开文档或源码有对应实现，不能等同于已经在你的 Windows 便携版环境中跑通。

目标：用户提供文字或参考素材，AI 选择适合的模型，创建或修改 ComfyUI 工作流，运行、读取结果、修复问题，并能够继续使用同一风格编号。环境参考：Windows 便携版 ComfyUI 0.3.64、RTX 5070 Laptop / 8GB 显存、本地服务 http://127.0.0.1:8190。这些是此前本机检测结果；新工具与这套环境的组合尚未实测。

本次整理了 17 个相关项目或研究方向。结合上述环境，我建议优先试 **官方 Comfy MCP + 当前 Codex + 现有风格档案**；如果希望把聊天直接放在 ComfyUI 画布旁边，**artokun 的 MCP + Agent Panel** 功能最接近，不过作者已转为有限维护。**comfy-agent** 的持久档案机制值得用于系列创作。这个排序是对公开能力和部署成本的判断，不是本机横向测试结果。

## 先理解三种不同能力

- **执行工具**：运行已有工作流、改提示词/种子/参数、上传参考图、取回图片；不一定会自主设计节点图。
- **工作流助手**：根据描述生成或改图、检查错误；不一定会自动执行及检查输出。
- **完整代理**：把查询环境、搭图、执行、读图、修复连成循环。代理的智能通常来自 Codex、Claude Code 或另付费的 LLM API；ComfyUI 本身负责生成。

“支持 OpenAI API”不代表可以使用 ChatGPT 网页订阅；“支持 Codex”也不代表当前聊天已经连接该工具。只有明确的客户端配置或订阅集成才算连接。模型权重、LLM 调用和云 GPU 是不同资源。

## 官方工具、控制层与聊天应用

| 项目与网站 | 功能 | 优点 | 缺点和限制 |
|---|---|---|---|
| [官方 Comfy MCP](https://github.com/Comfy-Org/comfy-mcp) / [文档](https://docs.comfy.org/agent-tools/mcp) | 给 Codex 等代理查询节点、校验和运行工作流、上传素材、取回结果、按 URL 下载模型的工具。 | 第一方维护；可连接已有本地安装；适合继续在当前 Codex 中完成规划与执行。 | 当前为 Beta，需配置 comfy-cli；模型搜索主要查本地目录，网络模型发现仍需其他工具；没有内置聊天面板或 S001 协议。 |
| [artokun / comfyui-mcp](https://github.com/artokun/comfyui-mcp) + [Agent Panel](https://github.com/artokun/comfyui-mcp-panel) | 代理搭图、运行、处理输出，搜索/下载模型、管理扩展；面板实时编辑画布。 | 功能覆盖很广；支持 Windows；ChatGPT 路线通过 Codex CLI 登录；有中文、附件、历史与回退。 | 依赖 Node.js ≥ 22、CLI 登录与桥接配置；目前仅有限维护，重点修复关键问题；不能把订阅宣传理解为无限用量。 |
| [yutianxiao6 / comfyui-mcp](https://github.com/yutianxiao6/comfyui-mcp) | 查询节点，创建/修改版本化 API 图，校验、执行、上传素材、获取输出；可选画布同步。 | 附带 Codex 等客户端适配与 skill，图编辑和版本控制清楚。 | Alpha；仅导入 API 格式，画布同步需扩展；公开工具表未确认网络模型搜索/下载。 |
| [官方 Comfy Agent](https://www.comfy.org/agent/) / [使用入口](https://cloud.comfy.org/) | 在画布旁接收描述和素材，规划、搭图、执行；保存可复用工作流和命名 skills。 | 官方成套界面；云端使用，无需本机显卡承担生成。 | 截至调研日，已开放的是 Cloud，本地/Desktop 仍为 coming soon；内置代理使用 Anthropic，聊天和生成消耗 Comfy Credits。 |
| [Open WebUI + ComfyUI](https://docs.openwebui.com/features/chat-conversations/image-generation-and-editing/comfyui/) | 在聊天中调用已上传的 API 工作流，映射提示词、尺寸、种子等输入；可另配置编辑流程。 | 适合固定风格模板和日常聊天出图；前端与图像模型分开选择。 | 官方集成需要先提供流程和节点映射；该集成本身不负责从零搭图或自动下载模型。 |
| [Selene](https://github.com/tercumantanumut/selene) / [发布下载](https://github.com/tercumantanumut/selene/releases) | 桌面 AI 应用；将 ComfyUI 工作流作为代理工具，接收参考图，导入流程后运行。 | 提供 Windows 安装/便携包；聊天、文件、记忆和多种模型服务集中在一个应用。 | 本次确认的是导入与调用工作流；从零搭图和自主选择下载模型的能力资料不足；安装包较大，功能范围很广。 |

### 官方 Comfy MCP：适合当前聊天继续使用

这是第一方公开的本地 MCP 服务，经 comfy-cli 调用现有 ComfyUI。节点发现与校验可帮助代理依据真实安装环境编写图，运行/队列/输出工具把执行接起来。Python 要求 ≥ 3.10，comfy-cli ≥ 1.14.0。模型下载接受直接 URL；README 的 search_models 是本地文件搜索，不能把它解释成自动搜索整个 Hugging Face 或 CivitAI。[仓库](https://github.com/Comfy-Org/comfy-mcp)

你的服务在本机 8190 端口，当前 README 指定本地非默认地址应配置 `COMFY_LOCAL_URL=http://127.0.0.1:8190`。同一项目中的 `COMFYUI_URL` 用于远程目标，当前只重定向部分工具；混用会造成查询与执行指向不同实例。还需让 comfy-cli 指向已有便携版工作目录，而不是再建一套模型目录。[地址配置说明](https://github.com/Comfy-Org/comfy-mcp#targeting-a-non-default-comfyui-address)

官方另外提供 Cloud MCP，让自己的 AI 客户端使用云 GPU；它和云端内置 Comfy Agent 是两条不同接入方式。若坚持用 Codex/ChatGPT 做规划且希望云端执行，应考察 Cloud MCP。[官方 MCP 文档](https://docs.comfy.org/agent-tools/mcp)

### artokun：功能最接近成套的本地自主助手

MCP 管理模型、图、执行与扩展，Panel 把它放在 ComfyUI 侧栏：修改实时画布，可撤销；上传附件，保留工作流聊天历史和图版本。ChatGPT 连接路径明确是 Codex CLI 登录及 app-server，而不是复用已打开的 ChatGPT 网页会话。需要 Node.js ≥ 22。模型搜索/下载能力比仅查本地目录的桥接器完整。[MCP 仓库](https://github.com/artokun/comfyui-mcp)、[Panel 仓库](https://github.com/artokun/comfyui-mcp-panel)

维护状态影响长期选择：作者 2026-09 曾宣布停止，2026-10-01 更新为恢复有限维护；当前仅承诺验证后的关键修复，没有广泛新功能路线，自动问题上报仍停用。不要只引用历史的“已归档”结论，也不要按全速维护的新项目推荐。[当前维护公告](https://comfyui-mcp.artokun.io/docs/blog/goodbye)

README 还有标注 July 2026 的官方工具状态比较，已经落后于当前官方发布。本文依据 Comfy 自己的最新文档判断官方 MCP 已公开、官方 Agent 已在 Cloud 开放、本地面板尚未开放。对你现有 D 盘安装和 8190 端口应明确配置路径/地址，不依赖自动发现。[当前官方可用性](https://support.comfy.org/articles/4013072355-comfy-agent)

### yutianxiao6：较精简的图编辑工具

它通过实时 object_info 获取节点类型，提供带版本号的 workflow store、逐节点修改、连线检查和运行。仓库附 Codex 插件与 skill；当前为 Alpha，Python ≥ 3.11，内置插件启动器需 uv。API 任务提交不会自动改变浏览器中的画布，可选 bridge 才负责同步。我们的 `.api.json` 可用于导入，普通 UI JSON 需转换。[仓库与集成说明](https://github.com/yutianxiao6/comfyui-mcp)

### 官方 Comfy Agent：容易开始的云端路线

官方说明已确认自然语言搭图、素材读取、执行与实时画布修改，并可按名字调用保存的 skill。当前用 Anthropic 模型；Cloud 已可使用，本地/Desktop 支持仍在等待。试用 token 用完后，聊天及图像生成都消耗 Comfy Credits。它使用云工作区可用的模型和节点，不能假设能立即装任意本地扩展。[官方 FAQ](https://support.comfy.org/articles/4013072355-comfy-agent)

### Open WebUI 与 Selene：先有图，再在聊天中运行

Open WebUI 官方 ComfyUI 集成要求先上传 API 格式的工作流，再配置节点输入映射；因此适合我们已经验证的固定 SDXL 流程。它提供聊天入口，但自动从零设计图和网络模型下载需要额外代理工具。[官方集成说明](https://docs.openwebui.com/features/chat-conversations/image-generation-and-editing/comfyui/)

Selene 官方仓库确认 ComfyUI workflows as agent tools、参考图和 Windows 发行包；发行记录提供把 workflow JSON 拖进聊天导入的功能。由此能确认已提供图的调用路线，尚不足以确认完全自主搭图/选模/下载闭环。[项目](https://github.com/tercumantanumut/selene)、[发行记录](https://github.com/tercumantanumut/selene/releases)

## ChatGPT、Codex 和 API 接入区别

Codex 支持本地 stdio 与 Streamable HTTP MCP；登录可以使用 ChatGPT 订阅或 API Key，后者按 API 使用量计费。因此，本地 ComfyUI 加本地 MCP 再接当前 Codex，是很直接的组合。[Codex MCP 文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、[身份验证](https://learn.chatgpt.com/docs/auth)

若你指定的是 ChatGPT 网页中的聊天，定制 MCP 使用 SSE 或 Streamable HTTP，需要配置可达连接，或使用官方 Secure MCP Tunnel 连接私有/本地服务；具体受账号和工作区权限影响。不能只填写 ComfyUI 的裸 API 地址就等同于安装一个 MCP 连接器。[定制 MCP](https://developers.openai.com/api/docs/guides/custom-mcp-server)、[Secure MCP Tunnels](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)

第三方项目说“支持 OpenAI”时，应分别检查：是否仅接受 API Key、是否支持 Codex 登录、是否实现远程 MCP。采用订阅登录也有使用额度，不能按“无限免费生成”理解。[Codex 用量说明](https://learn.chatgpt.com/docs/pricing)

## 社区与研究项目一览

| 项目与网站 | 功能及优势 | 缺点和限制 | 对当前目标的判断 |
|---|---|---|---|
| [dreamrec / ComfyPilot](https://github.com/dreamrec/ComfyPilot) | MCP 桥接本地 AI 客户端；有搭图、队列、状态、输出获取和显存检查；README 给出 Codex 配置方式。 | 当前文档要求 ComfyUI ≥ 0.20.0，0.3.64 不在审计范围；社区工具，需先做版本适配验证。 | 很贴近“继续在 Codex 聊天中控制本地 ComfyUI”。 |
| [ATH-MaaS / ComfyUI-Copilot](https://github.com/ATH-MaaS/ComfyUI-Copilot)（旧名 AIDC-AI） | ComfyUI 内的助手；工作流改写、调试、参数批量比较、模型推荐。 | 官方服务已有暂停公告，旧查询/推荐/工作流服务受影响；Agent 功能需自备 API Key 与 Base URL。 | 可考察中文界面助手，但不能按旧演示假设所有在线服务可用。 |
| [ConstantineB6 / comfy-pilot](https://github.com/ConstantineB6/comfy-pilot) | Claude Code 使用 MCP 编辑实时画布，运行、看输出、安装节点及下载模型。 | 主要围绕 Claude Code；Windows 源码明确禁用内嵌终端，保留 REST 接口。 | 功能接近，但对当前 Windows / Codex 需求不是优先。 |
| [AdamPerlinski / comfy-pilot](https://github.com/AdamPerlinski/comfy-pilot) | ComfyUI 聊天面板，多个 LLM 后端；读取本机模型、节点、显存，生成并校验工作流。 | Alpha；OpenAI API 和 Codex 后端被作者列为未测试；主要是生成 JSON 后应用到画布。 | 可试验，可靠性证据弱于成熟的控制工具。 |
| [shinshin86 / comfy-agent](https://github.com/shinshin86/comfy-agent) | CLI + Codex/Claude 等代理 skill；保存预设、任务、输出与历史，支持本地或云 ComfyUI。 | 核心是运行已有/导入预设；新工作流创作依赖外部 AI；Node.js ≥ 22。 | 非常适合“风格/角色档案 + 批量系列”，可作为持久管理层。 |
| [VibeComfy](https://github.com/peteromallet/VibeComfy) | 工作流变成可编辑 Python；模板搜索、导入、校验、编译与执行；适合让编码代理维护复杂图。 | 更偏开发工具；需 Python ≥ 3.11；Windows 便携版需适配安装步骤和依赖。 | 对长期可复用流程很有价值，初次搭建复杂。 |
| [ComfyMind](https://github.com/EnVision-Research/ComfyMind) | 输入描述与两份可选参考素材，使用规划与反馈完成生成/编辑；提供 Gradio 演示。 | 研究型部署；需预装模型及节点，配置多类 LLM API；没有现成风格编号系统。 | 研究方向最贴近“素材 + 任务 → 自动生成”，不宜作为省心安装首选。 |
| [ComfyAgent / ComfyBench](https://github.com/xxyQwQ/ComfyBench) | 按任务指令设计节点图，连接 ComfyUI 后自动执行；有论文和测试集。 | 需要 Conda、API、节点与模型环境；一些模型和扩展仍需手动准备。 | 适合研究、二次开发，普通创作工作台体验不足。 |
| [ComfyGPT](https://comfygpt.github.io/) / [源码](https://github.com/comfygpt/comfygpt) | 多代理研究框架，从描述生成并细化工作流。 | 当前公开 infer.py 的结束动作是保存 workflow.json，没有自动队列和出图闭环。 | 可参考规划设计；不能当作现成的“聊天直接出图”产品。 |
| [ComfySearch 论文](https://arxiv.org/abs/2601.04060) | 逐步编辑节点并做校验和原位修复，减少一次生成整图的错误。 | 本次没有找到可确认的作者官方代码仓库/安装产品；论文结果不能代表本机实用性。 | 作为研究参考，暂不列入可安装候选。 |
| [apppps / comfyui-agent](https://github.com/apppps/comfyui-agent) | 把当前 workflow.json 送给 GPT，帮助理解参数、提示词和连接。 | 早期版本，需 OpenAI API；文档流程返回 AI 回答，没有证实完整自动编辑、执行循环。 | 更像工作流讲解助手，能力范围较窄。 |

## 最接近完整流程的候选：进一步核查

### dreamrec / ComfyPilot

它是给现有代理提供工具的 MCP 服务，不需要另运行一个本地 LLM。可读取真实的模型目录和节点 schema、上传参考图片、构建及验证 API 工作流、提交队列、取回输出与错误日志；模型家族检测采用文件名规则，不能据此保证任何模型都能自动认对。[项目说明](https://github.com/dreamrec/ComfyPilot)

模型搜索覆盖 Hugging Face 和 CivitAI。下载工具实际调用 comfy-cli；源码要求明确 workspace 和确认参数，不能只有 URL 就自动放到任意安装目录。模型许可、登录令牌、目标目录和缺失文件仍需代理判断。[手册](https://github.com/dreamrec/ComfyPilot/blob/main/docs/MANUAL.md)、[下载实现](https://github.com/dreamrec/ComfyPilot/blob/main/src/comfy_mcp/tools/lifecycle.py)

“Technique”能把工作流和标签、模型引用保存为持久 JSON 并重放，快照支持差异和恢复；这些可以承载 S001 等风格档案，但没有证明它原生理解我们自定义的 `【同风格:S001】` 协议，也不自动保证画面视觉一致。其当前兼容文档列出最低 ComfyUI 0.20.0 和审计范围 0.20.0–0.31.1；若本机仍为 0.3.64，先在隔离环境检查，不能直接声称兼容。[手册](https://github.com/dreamrec/ComfyPilot/blob/main/docs/MANUAL.md)、[兼容审计](https://github.com/dreamrec/ComfyPilot/blob/main/docs/COMFYUI_COMPATIBILITY.md)

### ComfyUI-Copilot

旧 AIDC-AI 地址现在重定向 ATH-MaaS。当前 README 的服务公告比旧演示更重要：官方 API 服务已暂停，旧节点查询、任务推荐、工作流生成将停止；作者表示 Agent 相关能力仍可用，但必须填自己的 API Key 与 Base URL。不能把历史上的免费托管知识库服务视为当前保证。[当前官方 README](https://github.com/ATH-MaaS/ComfyUI-Copilot)

公开文档有工作流改写、错误调试、模型推荐/下载入口、GenLab 参数扫描和视觉比较；还明确提示新模型知识和上下文长度会导致中断。Windows 安装有便携 Python 路径示例，但文档同时存在不适用于 Windows 的 sudo 建议，部署时应按实际环境调整。没有核实独立的持久风格 ID 功能。[中文说明](https://github.com/ATH-MaaS/ComfyUI-Copilot/blob/main/README_CN.md)

### ConstantineB6 / comfy-pilot

已列出 get_workflow、edit_graph、run、view_image、download_model 及节点管理工具，适合 Claude Code 读取和修改正在打开的画布。与只生成离线 JSON 的项目相比，实时编辑和读图能力更贴近用户希望的闭环。[项目 README](https://github.com/ConstantineB6/comfy-pilot)

但 Windows 核查发现实际源码把内嵌 PTY 终端设为禁用，spawn 遇到 Windows 会失败，REST 路由仍在。下载及画布功能可以另行测试，不能据跨平台宣传推断 Windows 会获得演示中完整终端体验。未核实 ChatGPT 订阅或 Codex 的即用集成。[平台实现](https://github.com/ConstantineB6/comfy-pilot/blob/main/__init__.py)

### AdamPerlinski / comfy-pilot

作者明确标为 Alpha，测试过的后端为 Ollama、Claude Code 和 Aider，OpenAI API、Codex 等被列为未测试。项目文档的安装/价格示例有明显瑕疵，不能据此确定当前订阅费用或安装命令。[README](https://github.com/AdamPerlinski/comfy-pilot)

源码 controller.py 会把当前画布、GPU、模型和节点信息放入上下文，并用节点注册表校验生成的工作流，失败时最多修复三次。apply-workflow 端点返回校验后的 workflow，由前端应用；本次没有确认自动运行、取图评审或模型下载闭环，所以把它列为工作流编写助手。[控制器源码](https://github.com/AdamPerlinski/comfy-pilot/blob/main/controller.py)

### shinshin86 / comfy-agent

它把已有工作流作为 preset，连接 ComfyUI、改参数、上传素材、执行并保存结果；支持为 Codex 安装 skill，控制本地 GPU 或远程云实例。不是另一个聊天大模型，工作流设计和选择仍由外部代理完成。[项目 README](https://github.com/shinshin86/comfy-agent)

它有明确的持久 character 目录：appearance、style、negative、参考图、LoRA、gallery 和 notes，brief 在每次生成前检索记忆，支持全局与项目级存储。这比只保存聊天历史更适合系列创作；风格 S001 可借鉴此机制实现，需额外定义风格版本和基准图规范。[CLI 文档](https://github.com/shinshin86/comfy-agent/blob/main/docs/cli-reference.md)

包元数据要求 Node.js ≥ 22、当前版本 0.0.5。它的云 kit 清单不代表本机 8GB 显存能运行所有 kit；本机适配应从已验证的 SDXL 工作流开始。外部 CLI 接口不会自动修复 ComfyUI 或模型的硬件不兼容。[package.json](https://github.com/shinshin86/comfy-agent/blob/main/package.json)

### VibeComfy

重点是把图转成代理容易维护的 Python，保留来源和伴随元数据，修改后校验、再编译成 ComfyUI 的 API JSON。可导入已有图、选择模板、复用 recipe，run 会协调声明的模型资产；这适合将“固定风格部分”和“本次内容部分”做成可维护的生成代码。[README](https://github.com/peteromallet/VibeComfy)

当前包要求 Python ≥ 3.11，agent 面板另依赖 Arnold；可选 comfy extra 固定一个 ComfyUI 版本，并注明前端依赖冲突，因此不要随意把这个 extra 装进正在使用的便携版。现成安装说明以 Unix 路径与符号链接为主；Windows 需要适配。未确认原生 ChatGPT 订阅连接。[项目元数据](https://github.com/peteromallet/VibeComfy/blob/main/pyproject.toml)

## 研究原型：值得参考，但不等同于即用产品

### ComfyMind

官网：[项目页](https://litaoguo.github.io/ComfyMind.github.io/)；源码：[EnVision-Research/ComfyMind](https://github.com/EnVision-Research/ComfyMind)。README 提供自然语言 instruction 和 resource1/resource2 两个参考资源，既有命令行也有 Gradio，要求预先准备模型与扩展。论文方向是树状规划与反馈，是本次发现中非常贴近“用户交素材，系统自主完成任务”的研究方案。

config.yaml 要求分别配置文本、视觉、视觉推理和文本推理 API；这与使用当前 ChatGPT/Codex 订阅不是一回事。公开 main.py 按资源和任务自动判断模态、调用 pipeline 并保存输出；部署工作量、API 成本和反复试图的 GPU 时间都要评估。[配置源码](https://github.com/EnVision-Research/ComfyMind/blob/main/config.yaml)、[执行入口](https://github.com/EnVision-Research/ComfyMind/blob/main/main.py)

### ComfyAgent / ComfyBench

官网：[ComfyBench](https://xxyqwq.github.io/ComfyBench/)；源码：[xxyQwQ/ComfyBench](https://github.com/xxyQwQ/ComfyBench)。ComfyAgent 能从任务指令生成图，ComfyUI 服务正常时自动执行并保存图和日志；但模型和扩展需先准备，作者明确说部分资源仍需手动下载。适合复现实验或做自己的代理，而不是免配置的消费者应用。

默认配置使用 API 的 embedding、completion、vision 三类模型，不是 ChatGPT 网页登录。跨任务风格编号和模型网络发现/下载的完整持久协议没有在本次文档中证实。[配置](https://github.com/xxyQwQ/ComfyBench/blob/main/config.yaml)

### ComfyGPT

官网：[ComfyGPT](https://comfygpt.github.io/)；源码：[comfygpt/comfygpt](https://github.com/comfygpt/comfygpt)。现在仓库已经有代码，不能沿用早期“空仓库”的评价。README 要求 Conda Python 3.10 和模型/资源下载，是多代理工作流生成研究框架。

当前 infer.py 的流程是 FlowAgent 生成、RefineAgent 细化、ExecuteAgent 将图转换成工作流，最后写 workflow.json。公开入口没有提交 ComfyUI 任务、等待、获取图片的调用；“ExecuteAgent”名称不能作为它已完成出图的证据。未验证持久风格档案及在线模型自动下载。[入口源码](https://github.com/comfygpt/comfygpt/blob/main/infer.py)

### ComfySearch

网址：[arXiv 论文](https://arxiv.org/abs/2601.04060)。2026-01-07 提交，提出每次节点编辑后校验、诊断和修复；论文说明这种校验不是每一步都运行完整生成。适合借鉴工作流构建策略，但本次搜索未确认官方开源代码/权重/产品入口，因此不推荐用户将它视为可直接安装的工具。[论文正文](https://arxiv.org/html/2601.04060v1)

### apppps / comfyui-agent

网址：[仓库](https://github.com/apppps/comfyui-agent)。早期 ComfyUI 插件，把当前图复制为 session.json 后发送给 GPT，返回建议，默认模型为 GPT-4o-mini，需要 API。更接近“让 AI 看图解释与排错”，没有足够证据确认自动编辑、运行和输出检查；不是本次首选。[README](https://github.com/apppps/comfyui-agent/blob/master/README.md)

## 风格编号如何落在这些项目上

以上工具可以帮助保存或复用工作流，但本次没有发现哪个已原生实现我们的 `【同风格:S001】` 完整约定。最接近的基础分别是 ComfyPilot 的 technique/snapshot、comfy-agent 的 character/brief/history、VibeComfy 的 Python bundle/recipe；官方 Comfy Agent 也提供按名字保存和调用的 skills，但保存指令本身不等同于锁定所有模型与参数。[官方命名 skills](https://support.comfy.org/articles/4013072355-comfy-agent)

可以在选定控制工具上增加一个小型项目档案层：每个 S001-v1 保存模型文件名与版本/哈希、LoRA、基准图、固定提示词、采样/放大参数及工作流；每次引用编号先读取档案，再覆盖主体/构图/种子，最后保存图片与完整参数并检查风格偏差。这是基于本次工具能力提出的组合设计，不是已经在这些项目中找到的原生功能。

对于 8GB 显存环境，建议代理使用当前聊天/云 LLM 做规划，把本机显存主要留给图像模型。若同时在 GPU 上加载 Ollama 大模型与 SDXL，可能产生争用；实际是否能运行应逐个工作流实测，插件的模型支持清单不等同于硬件可用清单。

## 按你的需求选择

| 优先考虑 | 建议 | 原因 |
|---|---|---|
| 继续在当前 Codex 聊天中，由 AI 操作已有本机 ComfyUI | 官方 Comfy MCP + 当前风格档案 | 第一方工具层负责查询、校验、执行，当前代理负责网络找模型和设计流程；可保留已跑通的 SDXL 图。 |
| 在 ComfyUI 画布旁直接聊天，看到节点随要求变化 | artokun MCP + Agent Panel | 接近成套本地自主助手，模型与扩展管理丰富；接受有限维护和部署适配成本后可试。 |
| 系列图片、角色和风格持续复用 | 在控制层上采用 comfy-agent 的档案机制，或继续完善现有 registry | style / reference / LoRA / history 持久化与编号协议匹配；不是只记一段聊天。 |
| 减少本机部署，并运行超出本机显存能力的模型 | 官方 Comfy Agent；坚持自己的 Codex 则用 Cloud MCP | 云端承担生成；需接受云资源、额度和可用模型/节点范围。 |
| 固定一套流程，日后只变主体和场景 | Open WebUI + 已验证 API 工作流 | 先完成模板，再提供稳定聊天入口，部署目标更简单。 |
| 研究自动规划算法、做自己的产品 | ComfyMind / ComfyAgent / ComfyGPT / VibeComfy | 有可借鉴实现；需承担开发、环境与 API 集成工作。 |

综合建议：先用官方 MCP 验证“素材输入 → 建图 → 校验 → 执行 → 看结果 → 保存 S001 记录”一次闭环，再决定是否增加面板或档案工具。当前推荐不要求先更换已经验证的 SDXL 模型，也不需要同时安装多个相似桥接器。模型能被项目下载并不代表本机显存可运行；模型选择仍按真实节点和硬件逐一验证。

## 仍需验证的内容

- 选中工具能否连接当前 8190 端口并发现真实模型、节点和显存。
- 同一个任务能否完成创建图、运行、读图、处理错误的闭环。
- 模型下载能否正确落到便携版 models 子目录，受限模型需要哪些令牌。
- 风格编号跨聊天、进程重启与项目迁移后是否仍可恢复。
- 所选版本和本机 ComfyUI / Python / 前端的兼容性。

这些是选择后的实测工作；本次成果是有来源的项目比较，没有替你安装或升级软件。
