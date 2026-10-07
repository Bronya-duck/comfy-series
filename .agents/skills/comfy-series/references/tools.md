# 工具操作

通过`<项目 .venv 的python> <本技能 scripts/run.py> <命令>`调用，或在项目内`python -m comfy_series <命令>`。都返回`{ok,result}`或`{ok:false,error}`，退出码0/2/3。项目运行环境、Comfy地址、素材目录由根目录comfy_series.json读取。

| 操作 | 命令 |
|---|---|
| 初始化已有档案与资料 | `init` |
| 环境、显存、节点、模型与队列 | `doctor` |
| 导入图片/文档/网址 | `ingest --source <文件或URL> --role style` |
| 网页摘要或文字 | `ingest --source <原始URL或来源名称> --text-file <UTF8文件> --role context` |
| 更多PDF页 | `ingest --source <PDF> --pages 21,22,23` |
| 风格列表/读取/创建 | `styles list` / `styles show --style S001-v1` / `styles create --file <风格JSON>` |
| 系列列表/创建/预算 | `series list` / `series create --style S001-v1 --name <名称>` / `series budget --id SC001` |
| 查找已有权重 | `assets inventory` |
| HF搜索 | `assets hf-search --query <检索词>` |
| 固定HF文件版本与校验信息 | `assets hf-spec --repo h94/IP-Adapter --filename sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors --category ipadapter --save <JSON>` |
| 下载或复用 | `assets download --file <模型规格JSON> --series SC001` |
| 尝试替代候选 | `assets resolve --file <候选JSON数组> --series SC001` |
| 资料检索/追加 | `library search --query SDXL` / `library import --file <索引JSON数组>` |
| 缓存模板校验 | `library validate --id <来源编号>`；不带id检查全部缓存 |
| 检查/转换外部模板 | `workflow validate --file <JSON>` / `workflow convert --file <JSON> --save <目标JSON>` |
| 准备请求 | `prepare --request <请求JSON>` |
| 运行/恢复同一任务 | `run --job <J编号>` |
| 只重做未满足图片 | `run --job <J编号> --indices 0,2 --patch <调整JSON>` |
| 实际图片评审 | `review --job <J编号> --file <评审数组JSON>` |
| 查看历史状态 | `status --job <J编号>` |
| 核实未知任务后结束 | `abandon --job <J编号> --index 0 --reason <核实结果>` |
| 用户选定新基准 | `styles baseline --style S001-v1 --job <J编号> --index 0` |
| 用户选定外部基准图 | 先ingest并看图，再`styles baseline --style S001-v1 --material <M编号> --viewed-path <实际素材路径>`；只更换视觉基准，参考条件另建版本 |
| 导出本地索引 | `report` |
| 浏览资料库 | `serve --port 8191`，打开返回URL |

下载规格：category（checkpoints/loras/clip_vision/ipadapter/upscale_models/controlnet/vae）、name、url、expected_bytes、sha256、source_url、revision、license。HF工具自动填写固定commit、大小与LFS哈希。直接URL必须先核实来源及大小；无上游hash时工具记录计算出的hash，不能说已比对上游。resolve候选可为完整规格或`repo_id/filename/category/name`；先复用本地，再按顺序尝试，保留跳过原因。

下载出错保留可信断点与预算预留；同一规格恢复。同名现有权重校验不符时保留原文件，用不同name或调查。额度不因删除模型而重置。

正式风格切换：用户选择保留后，确认JSON为`{"human_confirmation":"用户实际确认的内容及消息引用"}`，用`prepare --request <JSON> --switch-keep --confirmation-file <确认JSON>`。选择删除时，先`cleanup plan --ids A-xxx,A-yyy`，展示具体文件；确认后`cleanup execute --plan DEL-xxx --ids A-xxx --confirmation-file <确认JSON>`，再用`prepare --request <JSON> --switch-delete-plan DEL-xxx --confirmation-file <同一确认JSON>`继续。工具核对路径、hash与空闲队列；确认只授权清单中的选定文件。

验收使用`series create --isolated`，不会改正式活动风格；它不免除下载额度或文件删除确认。独立测试必须记录自己使用的测试系列。
