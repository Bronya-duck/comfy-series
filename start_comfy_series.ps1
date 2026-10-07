$ErrorActionPreference = 'Stop'
$taskProjectRoot = $PSScriptRoot
$taskComfyRoot = 'D:\comfyui\ComfyUI_windows_portable'
& (Join-Path $taskComfyRoot 'python_embeded\python.exe') -B -s (Join-Path $taskComfyRoot 'ComfyUI\main.py') `
    --listen 127.0.0.1 --port 8190 --disable-auto-launch `
    --disable-all-custom-nodes --whitelist-custom-nodes ComfyUI_IPAdapter_plus --disable-api-nodes `
    --extra-model-paths-config (Join-Path $taskProjectRoot 'comfy_series.extra_models.yaml') `
    --user-directory (Join-Path $taskProjectRoot 'comfy_workflow\user') `
    --input-directory (Join-Path $taskProjectRoot 'comfy_workflow\input') `
    --output-directory (Join-Path $taskProjectRoot 'comfy_workflow\output') `
    --temp-directory (Join-Path $taskProjectRoot 'comfy_workflow\temp') `
    --database-url 'sqlite:///:memory:'
exit $LASTEXITCODE
