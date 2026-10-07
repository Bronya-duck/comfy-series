---
name: config-start
description: 在 Windows 电脑上跨 Codex 项目启用已安装的 Comfy Series，共用本地工具、模型和系列风格档案。
---

# Config Start

将已安装的 Comfy Series 启用为本机用户级 Skill，让其他 Codex 项目共用原项目的工具、模型、资料库和风格档案。

先定位包含 `comfy_series.json` 和 `install_codex_skills.ps1` 的项目。优先检查当前项目、本技能真实目录的上级目录，以及当前用户 `.agents/skills/comfy-series` 的目录联接目标。找不到时，请用户提供 Comfy Series 克隆目录；路径按本机实际配置读取。

在该项目运行 `install_codex_skills.ps1 -Scope Both`，为 comfy-series 和 config-start 建立用户级入口。安装器根据当前用户目录定位 `.agents/skills`，复用正确联接；已有同名入口指向其他内容时会保留原内容并报出冲突。处理冲突后再次运行，完成安装验证。

保持现有技能规则：每次调用先展示输出格式、尺寸、数量，以及带说明和例子的风格、制作内容、参考素材填写模板，再进入制作流程。

完成后，从其他目录通过用户级入口运行 `scripts/run.py --help` 和 `styles list`，确认工具仍定位原项目。已有 `S001-v1` 时核实能读取；新电脑可使用自己的风格档案。在当前项目读取 comfy-series 的 `SKILL.md` 并展示其填写模板；只收到启用请求时，等待制作内容后再生成。告诉用户后续使用 `$comfy-series`；若列表尚未更新，重启 Codex，并提供用户级 `SKILL.md` 的完整路径供直接调用。
