# Comfy Series

在当前 Codex 中提供制作要求和参考资料，由 `$comfy-series` 选择本地模型、构建 ComfyUI 工作流、逐张运行、实际看图并保存系列档案。默认 ComfyUI 地址为 `127.0.0.1:8190`，使用前需在自己的电脑安装并启动后端；创作判断由当前 Codex 完成。

每次调用会先展示输出格式、宽高、比例、数量与风格，标明你提供的值和默认值，再进入制作流程。只发“测试”或“开始”时，会先给出带说明与例子的填写模板，等待你补充制作内容；需求已齐时，复述规格后继续执行。用自然语言说清想画什么即可，风格可填“你来选”，参考素材可填“无”，不需要知道模型名称或专业提示词。

## 直接使用

生图 Skill 的显示名称是 **Comfy Series**，调用名 `$comfy-series`；配置 Skill 的显示名称是 **Config Start**，调用名 `$config-start`。Config Start 只有提示语和显示信息两份文件，用于检查或补齐跨项目入口。

新增 **图片交付助手**，调用名 `$image-delivery`：保留原图，按确认的名称和目标目录复制交付，处理重名并建立供 AI 查询的来源清单。Comfy Series 完成评审后会通过技能指引衔接，每次等待你填写交付模板；也可独立整理其他本地图片。安装、使用和 MIT 许可范围见 [图片交付助手说明](docs/image-delivery.md)。

安装器默认同时安装三个 Skill 到项目目录，并在当前用户的 `.agents/skills` 建立目录联接。在这台电脑的其他项目中，可以直接调用 `$comfy-series` 和 `$image-delivery`，共用原项目的环境和系列档案。项目级安装只在克隆项目内可见；仅把 Config Start 放进用户目录，仍需调用它完成 Comfy Series 的启用。

在这个项目的新会话里输入：

```text
$comfy-series
沿用【同风格:S001-v1】，做一个大型地下档案室。
钢制书架上放满密封档案箱，冷色工业摄影。
尺寸：1536×1024
数量：2
避免：人物、文字、水印
```

可以附带图片、网址、TXT、Markdown、PDF、DOCX。说明每份参考用于风格、主体、构图或背景资料；未说明图片用途时默认参考风格并重画内容。扫描 PDF 会生成页面预览，由 Codex 实际查看。最终输出第一版为 PNG；未提供尺寸时为 **1824×1248**，单张。宽高和比例矛盾时会澄清。

`【同风格:S001】`沿用已有系列绑定的版本，`【同风格:S001-v1】`指定精确版本，`【同风格:上一张】`取最近正式交付的风格。`【新风格】`新建档案，`【调风格:S001】`建立新版本。更换模型、固定画风、LoRA 或参考条件会产生新版本；改变主体继续使用原版本。同一版本默认复用已有正式系列，也可以明确给出系列编号。

已实测的档案包括 `S001-v1` 冷色工业摄影、`S002-v2` 暖色科幻插画、`S003-v1` IPAdapter 冷色参考、`S004-v1` 基础图生图。`S003-v2` 是不带参考条件的 A/B 实验对照。验收系列与正式系列分开保存；切换正式风格时会询问旧模型保留或删除，并列出文件与关联档案。

## 浏览和复现

[打开本地资料库与图库](http://127.0.0.1:8191/)（先启动自己的资料库服务）：查看图片、风格基准、失败与成功记录、模型占用、素材以及原始网站。每张图可打开画布工作流、API 工作流和复现记录。仓库提供40个原始来源和10份精选上游工作流缓存；图片、素材和运行记录来自本机后续生成。验证状态分别记录，原始模板不会因为派生流程成功而被标记通过。

使用说明与验收证据见 [验收报告](docs/验收报告.md)。每次运行保存在 `data/runs/J-编号`，包含请求、风格快照、模型大小/哈希、每轮种子、工作流、ComfyUI 历史和实际输出。PNG 同时保留 ComfyUI 元数据。相同环境和参数可再次执行；其他硬件或软件版本的逐像素一致性未验证。

## 服务启动与安装

### 从 GitHub 安装到其他电脑

仓库提供代码、三个 Skill、模板、资料索引和第三方许可记录。模型权重、参考原图、生成图片、Python 虚拟环境、SQLite 档案与运行缓存需要在新电脑上准备；文中的验收结果来自原开发电脑。

第一版安装脚本适用于 Windows。安装 Python 3.12、Git 和 ComfyUI 后，在 PowerShell 中克隆并进入项目：

```powershell
git clone https://github.com/Bronya-duck/comfy-series.git
cd comfy-series
```

1. 修改 `comfy_series.json` 中的 ComfyUI 地址、安装目录、输入和输出目录。若使用自带启动脚本，修改 `start_comfy_series.ps1` 的 ComfyUI 便携版路径，以及 `comfy_series.extra_models.yaml` 的 `base_path`（你的克隆目录下的 `data` 目录）。这些 ComfyUI 配置仍需按本机路径填写。
2. 运行下面的安装命令。未指定 `-Python` 时，使用系统 Python Launcher 的 `py -3.12`；没有 Launcher 时，显式传入自己的 Python 3.12 可执行文件路径。已有 `.venv` 会复用并检查版本。

```powershell
.\setup_comfy_series.ps1
# 或显式指定 Python 3.12：
.\setup_comfy_series.ps1 -Python 'C:\你的Python目录\python.exe'
```

3. 成功后，项目级 `.agents/skills` 和用户级 `%USERPROFILE%\.agents\skills` 都应包含 `comfy-series`、`config-start` 与 `image-delivery`。用户级入口联接到当前克隆目录，脚本会验证 `SKILL.md` 能读取。仅想在当前项目使用时，传 `-SkillScope Project`；以后补装跨项目入口可运行 `.\install_codex_skills.ps1 -Scope Both`，无需重装 Python 或下载模型。只需要图片整理功能时，按 [独立安装说明](docs/image-delivery.md#只安装图片交付技能) 准备 Python 与 Pillow，再使用安装器的 `-Skills image-delivery` 参数。
4. 准备兼容的 SDXL checkpoint，放入本项目 `data/models/checkpoints` 或 ComfyUI 的 `models/checkpoints`。启动已配置的 ComfyUI，再运行 `.\.venv\Scripts\python.exe -m comfy_series doctor` 检查节点与模型。需要 IPAdapter 参考时，参考权重规格在 `data/reference_assets.json`；`scripts/install_reference_assets.py` 只下载权重，不安装节点。节点须使用 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 记录的固定版本，通过额外模型路径配置和白名单启动脚本加载。新安装且对应节点目录尚不存在时，在项目目录运行：

```powershell
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git data/vendor/ComfyUI_IPAdapter_plus
git -C data/vendor/ComfyUI_IPAdapter_plus checkout a0f451a5113cf9becb0847b92884cb10cbdec0ef
.\.venv\Scripts\python.exe scripts/install_reference_assets.py
```

模型受各自访问条件和许可证约束。参考权重约3.4GB；已有节点目录时先核对版本再复用。

5. 在 Codex 中调用 `$comfy-series`。安装后若列表尚未更新，重启 Codex，再在任意项目的新会话输入 `$comfy-series`。Config Start 和图片交付助手已由安装器一并安装，不需要手动修改 Skill 中的用户名或盘符。生图通过评审后会收集交付文件名和目标目录；也可单独调用 `$image-delivery`。

目录联接依赖原克隆目录；请保留该目录。安装器遇到同名用户级 Skill 指向其他内容时会保留原内容并报错，需先处理该冲突。需要保留其他位置独立安装的 image-delivery 时，使用 `.\install_codex_skills.ps1 -Scope Both -Skills comfy-series,config-start`。核实三个入口的位置：

```powershell
Get-Item "$env:USERPROFILE\.agents\skills\comfy-series", "$env:USERPROFILE\.agents\skills\config-start", "$env:USERPROFILE\.agents\skills\image-delivery" |
    Select-Object FullName, LinkType, Target
```

本机 Skill 的项目级、用户级发现规则与刷新方式见 [OpenAI 官方文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。安装脚本已用隔离目录验证首次安装、重复安装和冲突保留；其他电脑的 ComfyUI、模型和显存兼容性仍需由 `doctor` 与实际生成验证。

`S001-v1` 的文字规则和工作流快照随仓库提供，其基准原图与本机既有权重不随仓库分发。其他电脑重新建档时应提供自己的基准图和模型，实际看图后确认风格。参考流程只在报告中的8GB Windows 环境实测。

配置完成后，在项目目录运行：

```powershell
.\start_comfy_series.ps1
# 在另一个终端中启动资料库
.\start_series_library.ps1
```

8190 已有服务时先查看其状态，避免重复启动。原启动脚本 `comfy_workflow/start_comfyui.ps1` 保留，可恢复不启用参考节点的配置。项目脚本保持现有 ComfyUI 0.3.64，仅白名单加载固定版本的 IPAdapter；没有修改 ComfyUI 的 Python 环境。

工具使用独立 Python 3.12 `.venv`。重新安装可运行 `setup_comfy_series.ps1`；可通过 `-Python <Python3.12绝对路径>`指定运行时。安装脚本使用锁定依赖，并通过 `install_codex_skills.ps1` 同步三个 Skill、建立用户级入口。技能源包与已安装入口都有真实脚本验证。

## 工具接口

命令返回 JSON，成功退出码0，领域错误2，其他错误3。使用 `--help`查看字段，或读取技能的 `references/tools.md`。例如：

```powershell
.\.venv\Scripts\python.exe -m comfy_series doctor
.\.venv\Scripts\python.exe -m comfy_series prepare --request examples\archive-request.json
.\.venv\Scripts\python.exe -m comfy_series run --job J-返回的编号
.\.venv\Scripts\python.exe -m comfy_series status --job J-返回的编号
```

`run` 的成功表示技术出图；Codex 查看图片后使用 `review` 完成视觉评审。只重做未满足图片，每张最多三轮，已接受的图会跳过。超时保留 prompt_id 并恢复跟踪，不自动重复提交未知任务。

下载通过工具核实固定来源、版本、大小和 SHA-256，支持断点恢复与候选替代。每个系列累计新增下载最多30GB，删除文件不重置额度；已有文件复用。新下载的参考权重合计 **3,375,890,960 字节**。受限、付费或不适配候选会被跳过并记录原因。具体模型文件删除需要用户确认清单，工具会再核对路径、哈希与队列。

## 当前边界

参考条件已在8GB显卡上运行，但不能保证风格与内容完全分离，部分参考验收仍有布局与主体数量偏差。Pony 插画模型也可能加入人物，必须实际看图。精确最终尺寸通过缩放保证；放大不会保证增加真实细节。角色身份一致、复杂局部修改、视频和训练留待扩展。既有模型的来源与许可缺口在来源记录中保留；项目不把文件存在当作公开可下载或许可已经核实。

开发验证：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`。第三方资料见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
