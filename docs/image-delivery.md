# 图片交付助手

`$image-delivery` 处理本地图片的名称、目录和来源清单。它保留源图，按字节复制到用户指定的位置，供后续 AI 查找和使用。支持 Pillow 能读取的本地图片；Comfy Series 默认选取评审通过的结果，不需要后台生图服务运行。

## 随 Comfy Series 安装

按仓库首页完成环境安装，`setup_comfy_series.ps1` 会一并安装 comfy-series、config-start 和 image-delivery 三个技能。

已有正常环境时，只更新技能：

```powershell
.\install_codex_skills.ps1 -Scope Both
```

安装器会保留冲突入口并报错。已经在其他目录独立安装 image-delivery 的用户，可保留该入口，仅更新另外两个：

```powershell
.\install_codex_skills.ps1 -Scope Both -Skills comfy-series,config-start
```

## 只安装图片交付技能

需要 Windows、Git、Python 3.12 或更新版本及 Pillow。此方式不要求安装 ComfyUI、下载模型或安装完整 Comfy Series 依赖。保留克隆目录，用户级入口联接到这里。

Windows PowerShell 若提示禁止运行脚本，可在执行安装命令的当前会话中运行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`。这项设置仅作用于本次 PowerShell 进程。

```powershell
git clone https://github.com/Bronya-duck/comfy-series.git
cd comfy-series
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install 'Pillow>=11,<13'
.\install_codex_skills.ps1 -Scope Both -Skills image-delivery
```

没有 Python Launcher 时，用自己的 Python 3.12+ 执行文件替代 `py -3.12`。技能列表未刷新时，在 Codex 中开启新会话或重新启动，然后调用 `$image-delivery`。可检查入口：

```powershell
Get-Item "$env:USERPROFILE\.agents\skills\image-delivery" |
    Select-Object FullName, LinkType, Target
```

也可以只复制 `skill_package/image-delivery` 文件夹到本机，再执行该文件夹的 `install.ps1`。这种独立入口指向复制出来的文件夹；运行时通过系统 Python 或 `-PythonPath` 选择。此后若改用仓库整体安装方式，需自行处理已有入口冲突。

## 使用

Comfy Series 完成生成和评审后，技能指引会自动衔接图片交付。其他图片可以直接请求：

```text
$image-delivery
把 D:\我的素材\背景.png 和 D:\我的素材\封面.jpg 交付到我的游戏项目。
保留原图，统一用“场景”作前缀，用途是游戏背景。
```

每次交付都会展示模板并等待本次答复，已给出的值可以预填：

```text
目标文件夹：D:\我的游戏\images
文件名：统一前缀“场景”
用途：游戏背景
```

得到 `场景_001.png`、`场景_002.jpg` 及 `image-manifest.json`。文件格式与原图一致。同名同内容复用，同名不同内容追加编号；重复执行不会不断增加副本。清单记录用途、实际格式、尺寸、哈希、源到目标的映射，Comfy 图片还记录任务、风格和轮次。

后续可以请求“在 D:\我的游戏 里找到已交付的游戏背景”。查询限制在指定项目，能识别缺失或被替换的文件；清单中的目标路径为相对路径，项目整体搬迁后仍可定位。

## 工具与验证

具体 JSON 请求、返回状态和命名规则见 [工具接口](../skill_package/image-delivery/references/tools.md)，验收图片识别见 [Comfy 适配](../skill_package/image-delivery/references/comfy-series.md)。

```powershell
& "$env:USERPROFILE\.agents\skills\image-delivery\scripts\run.ps1" inspect --file 'D:\任务\inspect.json'
& "$env:USERPROFILE\.agents\skills\image-delivery\scripts\run.ps1" find --root 'D:\我的游戏' --query '游戏背景'
# 已有其他 Python 环境时：
& "$env:USERPROFILE\.agents\skills\image-delivery\scripts\run.ps1" -PythonPath 'C:\Python312\python.exe' find --root 'D:\我的游戏'

# 只验证图片交付功能：
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_image_delivery.py' -v
```

首版提供命名、复制归档、批量交付和查询。转格式、压缩、原件移动和删除尚未提供。

## 许可证

新增的 `skill_package/image-delivery` 以及 `tests/test_image_delivery.py` 使用 [MIT 许可证](../skill_package/image-delivery/LICENSE)。这项许可仅涉及新增技能及其测试；仓库其他代码和第三方资料的许可状态保持原样。
