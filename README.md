# Comfy Series

在当前 Codex 中提供制作要求和参考资料，由 `$comfy-series` 选择本地模型、构建 ComfyUI 工作流、逐张运行、实际看图并保存系列档案。项目已经连接本机 `127.0.0.1:8190`，没有另外一个聊天大模型服务。

每次调用会先展示输出格式、宽高、比例、数量与风格，标明你提供的值和默认值，再进入制作流程。只发“测试”或“开始”时，会先给出带说明与例子的填写模板，等待你补充制作内容；需求已齐时，复述规格后继续执行。用自然语言说清想画什么即可，风格可填“你来选”，参考素材可填“无”，不需要知道模型名称或专业提示词。

## 直接使用

本机跨项目入口为 **Config Start**，调用名 `$config-start`。它只有提示语和显示信息两份文件，源码位于 `skill_package/config-start`；运行时把已有 Comfy Series 配置成用户级目录联接，共用本机模型、资料库与风格档案。完成一次配置后，在其他项目直接使用 `$comfy-series`。这份入口针对当前 Windows 电脑的固定路径，换电脑时需要调整路径并安装运行环境。

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

[打开本地资料库与图库](http://127.0.0.1:8191/)：查看图片、风格基准、全部失败与成功记录、模型占用、素材以及原始网站。每张图可打开画布工作流、API 工作流和复现记录。资料库有40个原始来源、10份精选上游工作流缓存，以及本机实际运行的派生工作流。验证状态分别记录，原始模板不会因为派生流程成功而被标记通过。

使用说明与验收证据见 [验收报告](docs/验收报告.md)。每次运行保存在 `data/runs/J-编号`，包含请求、风格快照、模型大小/哈希、每轮种子、工作流、ComfyUI 历史和实际输出。PNG 同时保留 ComfyUI 元数据。相同环境和参数可再次执行；其他硬件或软件版本的逐像素一致性未验证。

## 服务启动与安装

### 从 GitHub 安装到其他电脑

仓库提供代码、两个 Skill、模板、资料索引和第三方许可记录。模型权重、参考原图、生成图片、Python 虚拟环境、SQLite 档案与运行缓存需要在新电脑上准备；文中的验收结果来自原开发电脑。

1. 安装 Python 3.12、Git 和 ComfyUI，然后克隆项目：`git clone https://github.com/Bronya-duck/comfy-series.git`。
2. 修改 `comfy_series.json` 中的 ComfyUI 地址、安装目录、输入和输出目录；修改 `start_comfy_series.ps1` 的 ComfyUI 便携版路径，并检查 `comfy_series.extra_models.yaml` 的项目模型目录。后端需采用与本机节点兼容的版本。
3. 在项目目录运行 `./setup_comfy_series.ps1 -Python "你的 Python 3.12 路径"`，安装独立环境和项目级 comfy-series。运行 `./.venv/Scripts/python.exe -m comfy_series doctor` 检查环境与模型。
4. 准备兼容的 SDXL 模型；需要风格参考时，读取 `scripts/install_reference_assets.py` 的固定下载来源和节点版本，准备相应权重与节点。模型受各自访问条件和许可证约束。
5. 在 Codex 中打开克隆目录，调用 `$comfy-series`。Config Start 的两个路径针对原开发电脑；其他使用者先改为自己的项目 Skill 路径和用户级入口，再将 `skill_package/config-start` 放入自己的用户级 Skill 目录。

`S001-v1` 的文字规则和工作流快照随仓库提供，其基准原图与本机既有权重不随仓库分发。其他电脑重新建档时应提供自己的基准图和模型，实际看图后确认风格。参考流程只在报告中的8GB Windows 环境实测。

服务当前已经启动。重启电脑后，在项目目录运行：

```powershell
.\start_comfy_series.ps1
# 在另一个终端中启动资料库
.\start_series_library.ps1
```

8190 已有服务时先查看其状态，避免重复启动。原启动脚本 `comfy_workflow/start_comfyui.ps1` 保留，可恢复不启用参考节点的配置。项目脚本保持现有 ComfyUI 0.3.64，仅白名单加载固定版本的 IPAdapter；没有修改 ComfyUI 的 Python 环境。

技能安装在 `.agents/skills/comfy-series`，工具使用独立 Python 3.12 `.venv`。重新安装可运行 `setup_comfy_series.ps1`；可通过 `-Python <Python3.12绝对路径>`指定运行时。安装脚本使用锁定的依赖文件，并把 `skill_package/comfy-series` 同步到项目技能目录。技能源包与已安装入口都有真实脚本验证。

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
