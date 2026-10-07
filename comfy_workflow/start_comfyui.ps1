$ErrorActionPreference = 'Stop'
$taskComfyRoot = 'D:\comfyui\ComfyUI_windows_portable'
$taskProjectRoot = $PSScriptRoot
foreach ($taskSubdir in @('output', 'input', 'temp', 'user')) {
    New-Item -ItemType Directory -Path (Join-Path $taskProjectRoot $taskSubdir) -Force | Out-Null
}
$env:PYTHONDONTWRITEBYTECODE = '1'
& (Join-Path $taskComfyRoot 'python_embeded\python.exe') -B -s (Join-Path $taskComfyRoot 'ComfyUI\main.py') `
    --listen 127.0.0.1 --port 8190 --disable-auto-launch --disable-all-custom-nodes --disable-api-nodes `
    --user-directory (Join-Path $taskProjectRoot 'user') `
    --input-directory (Join-Path $taskProjectRoot 'input') `
    --output-directory (Join-Path $taskProjectRoot 'output') `
    --temp-directory (Join-Path $taskProjectRoot 'temp') `
    --database-url 'sqlite:///:memory:'
exit $LASTEXITCODE
