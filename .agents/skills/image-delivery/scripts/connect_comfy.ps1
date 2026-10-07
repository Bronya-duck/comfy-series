param([string]$ComfyProjectRoot)
$ErrorActionPreference = 'Stop'
if (-not $ComfyProjectRoot) {
    $taskEntry = Get-Item -LiteralPath (Join-Path $env:USERPROFILE '.agents\skills\comfy-series') -Force
    $taskPath = if ($taskEntry.LinkType -eq 'Junction') { @($taskEntry.Target)[0] } else { $taskEntry.FullName }
    $taskParent = [IO.DirectoryInfo]::new($taskPath)
    while ($taskParent -and -not (Test-Path -LiteralPath (Join-Path $taskParent.FullName 'comfy_series.json'))) { $taskParent = $taskParent.Parent }
    if (-not $taskParent) { throw 'Cannot locate Comfy Series project; pass -ComfyProjectRoot.' }
    $ComfyProjectRoot = $taskParent.FullName
}
$taskRoot = [IO.Path]::GetFullPath($ComfyProjectRoot)
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'comfy_series.json') -PathType Leaf)) { throw "Not a Comfy Series project: $taskRoot" }
$taskAddition = '8. **命名与项目文件交付**：本次生图任务完成视觉评审后，调用 `$image-delivery`，传递本任务 `data/runs/<J编号>/job.json` 的完整路径；有验收通过图片时，每次展示交付模板，等待用户本次填写目标文件夹、文件名和可选用途，再保留源图、复制交付并登记目标目录的清单。没有通过结果时说明状态，不正式交付。不在各重试轮次分别触发。辅助技能未出现在列表时，读取当前用户 `.agents/skills/image-delivery/SKILL.md`；入口缺失时说明安装问题。交付失败只修复文件交付，不重跑生图或修改视觉评审。'
$taskPaths = @('skill_package\comfy-series\SKILL.md', '.agents\skills\comfy-series\SKILL.md')
$taskChanges = @()
foreach ($taskRelative in $taskPaths) {
    $taskFile = Join-Path $taskRoot $taskRelative
    $taskContent = [IO.File]::ReadAllText($taskFile)
    if ($taskContent.Contains($taskAddition)) {
        $taskChanges += @{ path = $taskFile; changed = $false }
        continue
    }
    if ($taskContent.Contains('8. **命名与项目文件交付**')) { throw "Existing different integration preserved: $taskFile" }
    $taskMatches = [regex]::Matches($taskContent, '(?m)^7\. \*\*交付与记录\*\*[^\r\n]*')
    if ($taskMatches.Count -ne 1) { throw "Cannot uniquely locate delivery step: $taskFile" }
    $taskNewline = if ($taskContent.Contains("`r`n")) { "`r`n" } else { "`n" }
    $taskMatch = $taskMatches[0]
    $taskUpdated = $taskContent.Insert($taskMatch.Index + $taskMatch.Length, $taskNewline + $taskAddition)
    $taskChanges += @{ path = $taskFile; changed = $true; content = $taskUpdated }
}
# Validate both documents before writing either one. Preserve all surrounding text.
foreach ($taskChange in $taskChanges) {
    if ($taskChange.changed) { [IO.File]::WriteAllText($taskChange.path, $taskChange.content, [Text.UTF8Encoding]::new($false)) }
}
[ordered]@{ ok = $true; changes = @($taskChanges | ForEach-Object { @{ path = $_.path; changed = $_.changed } }) } | ConvertTo-Json -Depth 4
