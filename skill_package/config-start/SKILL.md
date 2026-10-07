---
name: config-start
description: 在这台 Windows 电脑上跨 Codex 项目启用已有 Comfy Series，共用本地工具、模型和系列风格档案。
---

# Config Start

将下面的配置要求作为当前任务执行：

请将已有的 comfy-series 安装为本机用户级 Skill，让所有 Codex 项目都能直接调用它。

现有 Skill：`D:\_SCP生图逻辑\.agents\skills\comfy-series`。
用户级入口：`C:\Users\bronya\.agents\skills\comfy-series`。

让用户级入口指向现有 Skill 目录，复用原项目的 Python 工具、ComfyUI、模型、资料库和风格档案。优先使用 Windows 目录联接；已有同名入口时先检查并复用正确配置。若入口指向其他内容，保留原内容并说明冲突。

保持现有技能规则：每次调用先展示输出格式、尺寸、数量，以及带说明和例子的风格、制作内容、参考素材填写模板，再进入制作流程。

完成后，从其他目录验证工具入口和 `S001-v1` 风格档案能够读取。在当前项目读取已有 comfy-series 的 `SKILL.md` 并展示其填写模板；只收到启用请求时，等待制作内容后再生成。告诉用户后续使用 `$comfy-series`；若当前会话尚未发现用户级入口，提供该入口的完整文件路径供直接调用。
