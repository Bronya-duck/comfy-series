# 工具接口

在 PowerShell 中使用本技能真实路径或用户级联接路径：

```powershell
& "$env:USERPROFILE\.agents\skills\image-delivery\scripts\run.ps1" inspect --file 'D:\任务\inspect.json'
& "$env:USERPROFILE\.agents\skills\image-delivery\scripts\run.ps1" deliver --file 'D:\任务\delivery.json'
& "$env:USERPROFILE\.agents\skills\image-delivery\scripts\run.ps1" find --root 'D:\目标项目' --query '封面'
```

`--file` 为 UTF-8 JSON，路径必须为完整绝对路径。`sources` 和 `comfy_job` 二选一：

```json
{"sources": ["D:/素材/参考图.png", "D:/素材/场景.jpg"]}
```

```json
{"comfy_job": "D:/Comfy项目/data/runs/J-编号/job.json"}
```

`inspect` 返回 `items`，含 `ready` 或 `failed` 状态、来源、格式、宽高、字节数和 SHA-256；Comfy 未验收项在 `skipped` 中，顺序按图片索引。`deliver` 也会重新读取和核验源文件。

收到本次交付模板答复后，增加交付字段：

```json
{
  "sources": ["D:/素材/参考图.png", "D:/素材/场景.jpg"],
  "destination_dir": "D:/目标项目/images",
  "names": ["封面", "室内场景.jpg"],
  "usage": "游戏背景",
  "delivery_confirmed": true
}
```

多张统一命名时用 `name_prefix` 替代 `names`，例如 `"name_prefix": "档案室"`。`names` 必须与已选来源数量相等；Comfy 未验收图片不占位置，通过但核验失败的图片仍保留原位置。单张也用一元素名称列表。前缀无扩展名，多张生成 `_001` 起始序号，单张直接使用前缀。`usage` 可省略；重复交付省略时保留清单中已有用途，显式提供时更新。

输出为一个 JSON 对象；退出码 0 表示成功，1 表示有错误。交付逐项返回 `copied`、`reused`、`failed`；有成功项而也有错误时 `ok: false`，成功项及清单仍保留。`manifest_path` 为清单位置。无验收通过图片时不创建目标目录。

`find` 的 `--root` 必须是现有项目的绝对目录，`--query` 可省略。查询名称、用途、来源/目标路径及任务、系列、风格编号；不跟随子目录联接，不扫描 `.git`、`.venv`、`node_modules`。返回 `target_absolute_path`、`exists` 和 `integrity`（`valid`、`changed`、`missing`、`unsafe`、`unreadable`）。项目挪动后，目标路径仍从清单所在目录解析。

名称保留中文和空格。Windows 禁用字符、设备保留名、末尾空格/点、目录分隔符及不匹配的扩展名会失败。工具不会用改扩展名冒充转格式。重复交付复用内容相同的已编号文件。

清单为 `schema_version: 1`、`items` 数组，记录每条源到目标的映射，目标路径相对于清单目录。写入由 `.image-delivery.lock` 的操作系统文件锁串行化；锁在进程结束后自动释放，锁文件可以保留。清单原子替换；登记失败时撤回本次新复制的图片，复用的已有图片保持原样。
