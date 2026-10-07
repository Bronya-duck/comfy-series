[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$PythonPath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ToolArguments
)
$ErrorActionPreference = 'Stop'
$taskCandidates = @()
if ($PythonPath) {
    $taskCandidates += $PythonPath
} else {
    $taskCandidates += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    # A clone or installed skill may have a local Python environment of its own.
    $taskParent = [IO.DirectoryInfo]::new($PSScriptRoot)
    while ($taskParent) {
        $taskItem = Get-Item -LiteralPath $taskParent.FullName -Force
        if ($taskItem.LinkType -eq 'Junction') {
            $taskParent = [IO.DirectoryInfo]::new(@($taskItem.Target)[0])
        }
        $taskCandidates += Join-Path $taskParent.FullName '.venv\Scripts\python.exe'
        $taskParent = $taskParent.Parent
    }
    $taskComfy = Get-Item -LiteralPath (Join-Path $env:USERPROFILE '.agents\skills\comfy-series') -ErrorAction SilentlyContinue
    if ($taskComfy) {
        $taskResolved = if ($taskComfy.LinkType -eq 'Junction') { @($taskComfy.Target)[0] } else { $taskComfy.FullName }
        $taskParent = [IO.DirectoryInfo]::new($taskResolved)
        while ($taskParent) {
            if (Test-Path -LiteralPath (Join-Path $taskParent.FullName 'comfy_series.json')) {
                $taskCandidates += Join-Path $taskParent.FullName '.venv\Scripts\python.exe'
                break
            }
            $taskParent = $taskParent.Parent
        }
    }
    $taskLauncher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
    if ($taskLauncher) {
        try {
            $taskLaunched = & $taskLauncher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $taskLaunched) { $taskCandidates += [string]$taskLaunched }
        } catch { }
    }
    $taskSystemPython = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
    if ($taskSystemPython) { $taskCandidates += $taskSystemPython.Source }
}
foreach ($taskCandidate in ($taskCandidates | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $taskCandidate -PathType Leaf) {
        try {
            & $taskCandidate -B -X utf8 -c 'import sys; assert sys.version_info >= (3, 12); from PIL import Image' >$null 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0) {
            & $taskCandidate -B -X utf8 (Join-Path $PSScriptRoot 'image_delivery.py') @ToolArguments
            exit $LASTEXITCODE
        }
    }
}
[ordered]@{ ok = $false; errors = @(@{ code = 'runtime_missing'; message = '找不到包含 Pillow 的 Python 3.12 或更新版本；请用 -PythonPath 指定已有环境。' }); items = @() } | ConvertTo-Json -Depth 4 -Compress
exit 1
