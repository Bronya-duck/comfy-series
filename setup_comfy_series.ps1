param([string]$Python = 'C:\Users\bronya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = $Python
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot '.venv\Scripts\python.exe'))) {
    & $taskPython -m venv (Join-Path $taskRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -m pip install -r (Join-Path $taskRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -m pip install --no-deps -e $taskRoot
if ($LASTEXITCODE -ne 0) { throw 'project installation failed' }
$taskSkillSource = Join-Path $taskRoot 'skill_package\comfy-series'
$taskSkillTarget = Join-Path $taskRoot '.agents\skills\comfy-series'
New-Item -ItemType Directory -Path $taskSkillTarget -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $taskSkillSource 'SKILL.md') -Destination $taskSkillTarget -Force
foreach ($taskFolder in @('agents','references','scripts')) {
    $taskDestination = Join-Path $taskSkillTarget $taskFolder
    New-Item -ItemType Directory -Path $taskDestination -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $taskSkillSource $taskFolder) -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $taskDestination -Force
    }
}
& (Join-Path $taskRoot '.venv\Scripts\python.exe') -m comfy_series init
exit $LASTEXITCODE
