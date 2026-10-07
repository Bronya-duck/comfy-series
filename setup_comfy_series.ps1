param(
    [string]$Python,
    [ValidateSet('Project', 'User', 'Both')][string]$SkillScope = 'Both'
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot '.venv\Scripts\python.exe'))) {
    if ($Python) {
        & $Python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 required' }
        & $Python -m venv (Join-Path $taskRoot '.venv')
    } else {
        $taskLauncher = Get-Command py -ErrorAction SilentlyContinue
        if (-not $taskLauncher) { throw 'Install Python 3.12, or pass -Python with its executable path.' }
        & $taskLauncher.Source -3.12 -m venv (Join-Path $taskRoot '.venv')
    }
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'
if ($LASTEXITCODE -ne 0) { throw 'The existing .venv must use Python 3.12.' }
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -m pip install -r (Join-Path $taskRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -m pip install --no-deps -e $taskRoot
if ($LASTEXITCODE -ne 0) { throw 'project installation failed' }
& (Join-Path $taskRoot 'install_codex_skills.ps1') -Scope $SkillScope -ProjectRoot $taskRoot
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -m comfy_series init
exit $LASTEXITCODE
