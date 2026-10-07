# Comfy Series 适配

入口接收绝对的 `comfy_job` 文件路径。直接只读解析 JSON，不导入 Comfy Series 模块、不调用它的 CLI，也不改动 SQLite、风格档案、图片或任务记录。

ComfyUI 原始输出在配置的 `comfy_output` 下；Comfy Series 通常把评审副本存到 `data/runs/<job>/image_<序号>/round_<轮次>/result.png`。复制来源以本次任务记录为准，而不是扫描输出目录或按修改时间选最新文件。

选择链：`images` 的索引顺序 → `review.accepted` → `best_path` → 路径匹配的 `attempts` → 对应目录 `manifest.json`。核对任务、系列、风格、轮次、源路径以及评审的图片索引和 `viewed_path`。图片评审、所选 attempt 的评审和 manifest 的评审都须验收通过且检查项为 pass。manifest 的 attempt 可能没有内嵌评审，这是原工具的存储方式；应读 manifest 顶层 `visual_review`。

读取图片本身，核对两份记录中的 SHA-256、输出尺寸、PNG 格式和技术检查。未验收项列入 `skipped`；已验收但记录不一致、文件缺失或哈希变化的项列为失败，不猜测替代版本。

清单 provenance 保存任务编号、系列编号、风格版本、图片索引、轮次和任务记录路径。这些是来源信息，实际交付路径属于新项目；不把复制结果写回 `best_path` 或设成新风格基准。

Comfy Series 调用时先完成本次生成和视觉评审，再把 `job.json` 交给本技能。辅助技能仍展示交付模板等待本次答复。任务没有通过结果时说明状态；复制或登记失败只修复交付步骤。
