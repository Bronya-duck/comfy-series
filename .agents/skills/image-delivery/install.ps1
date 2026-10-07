param([string]$UserSkillsRoot)
$ErrorActionPreference = 'Stop'
if (-not $UserSkillsRoot) { $UserSkillsRoot = Join-Path $env:USERPROFILE '.agents\skills' }
$taskSource = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$taskEntry = Get-Item -LiteralPath $taskSource -Force
if ($taskEntry.LinkType -eq 'Junction') { $taskSource = [IO.Path]::GetFullPath(@($taskEntry.Target)[0]).TrimEnd('\') }
$taskDestination = Join-Path ([IO.Path]::GetFullPath($UserSkillsRoot)) 'image-delivery'
if (-not (Test-Path -LiteralPath (Join-Path $taskSource 'SKILL.md') -PathType Leaf)) { throw "Missing skill source: $taskSource" }
$taskExisting = Get-Item -LiteralPath $taskDestination -Force -ErrorAction SilentlyContinue
if ($taskExisting) {
    $taskTarget = @($taskExisting.Target)[0]
    if ($taskExisting.LinkType -ne 'Junction' -or -not $taskTarget -or [IO.Path]::GetFullPath($taskTarget).TrimEnd('\') -ne $taskSource) {
        throw "Existing skill preserved; conflicting entry: $taskDestination"
    }
} else {
    New-Item -ItemType Directory -Path ([IO.Path]::GetFullPath($UserSkillsRoot)) -Force | Out-Null
    New-Item -ItemType Junction -Path $taskDestination -Target $taskSource | Out-Null
}
if (-not (Test-Path -LiteralPath (Join-Path $taskDestination 'scripts\image_delivery.py') -PathType Leaf)) { throw 'Skill entry verification failed.' }
[ordered]@{ ok = $true; name = 'image-delivery'; source = $taskSource; user_path = $taskDestination } | ConvertTo-Json
