param(
    [ValidateSet('Project', 'User', 'Both')][string]$Scope = 'Both',
    [string]$ProjectRoot = $PSScriptRoot,
    [string]$UserSkillsRoot,
    [ValidateSet('comfy-series', 'config-start', 'image-delivery')]
    [string[]]$Skills = @('comfy-series', 'config-start', 'image-delivery')
)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath($ProjectRoot)
$taskNames = @($Skills | Select-Object -Unique)
if (-not $taskNames) { throw 'Select at least one skill.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'comfy_series.json') -PathType Leaf)) {
    throw "Not a Comfy Series project: $taskRoot"
}
if (-not $UserSkillsRoot) {
    $taskProfile = [Environment]::GetFolderPath('UserProfile')
    if (-not $taskProfile) { throw 'Cannot find the current user profile.' }
    $UserSkillsRoot = Join-Path $taskProfile '.agents\skills'
}
$taskUserRoot = [IO.Path]::GetFullPath($UserSkillsRoot)
$taskProjectSkills = Join-Path $taskRoot '.agents\skills'
$taskInstallUser = $Scope -ne 'Project'

# Check every destination before changing files. Preserve conflicting installs.
foreach ($taskName in $taskNames) {
    $taskSource = Join-Path $taskRoot "skill_package\$taskName"
    $taskTarget = Join-Path $taskProjectSkills $taskName
    if (-not (Test-Path -LiteralPath (Join-Path $taskSource 'SKILL.md') -PathType Leaf)) {
        throw "Missing skill source: $taskSource"
    }
    $taskExisting = Get-Item -LiteralPath $taskTarget -Force -ErrorAction SilentlyContinue
    if ($taskExisting -and ((-not $taskExisting.PSIsContainer) -or
        ($taskExisting.Attributes -band [IO.FileAttributes]::ReparsePoint))) {
        throw "Project skill destination must be an ordinary directory: $taskTarget"
    }
    if ($taskInstallUser) {
        $taskUserTarget = Join-Path $taskUserRoot $taskName
        $taskExistingUser = Get-Item -LiteralPath $taskUserTarget -Force -ErrorAction SilentlyContinue
        if ($taskExistingUser) {
            $taskLinkedPath = @($taskExistingUser.Target)[0]
            if ($taskExistingUser.LinkType -ne 'Junction' -or -not $taskLinkedPath -or
                [IO.Path]::GetFullPath($taskLinkedPath).TrimEnd('\') -ne $taskTarget.TrimEnd('\')) {
                throw "Existing user skill preserved: $taskUserTarget. Move it aside before installing, or use -Scope Project."
            }
        }
    }
}

$taskResults = @()
foreach ($taskName in $taskNames) {
    $taskSource = Join-Path $taskRoot "skill_package\$taskName"
    $taskTarget = Join-Path $taskProjectSkills $taskName
    New-Item -ItemType Directory -Path $taskTarget -Force | Out-Null
    foreach ($taskFile in Get-ChildItem -LiteralPath $taskSource -Recurse -File) {
        $taskRelative = $taskFile.FullName.Substring($taskSource.Length).TrimStart('\')
        $taskDestination = Join-Path $taskTarget $taskRelative
        New-Item -ItemType Directory -Path (Split-Path -Parent $taskDestination) -Force | Out-Null
        Copy-Item -LiteralPath $taskFile.FullName -Destination $taskDestination -Force
    }
    $taskUserTarget = $null
    if ($taskInstallUser) {
        New-Item -ItemType Directory -Path $taskUserRoot -Force | Out-Null
        $taskUserTarget = Join-Path $taskUserRoot $taskName
        if (-not (Get-Item -LiteralPath $taskUserTarget -Force -ErrorAction SilentlyContinue)) {
            New-Item -ItemType Junction -Path $taskUserTarget -Target $taskTarget | Out-Null
        }
        if (-not (Test-Path -LiteralPath (Join-Path $taskUserTarget 'SKILL.md') -PathType Leaf)) {
            throw "User skill verification failed: $taskUserTarget"
        }
    }
    $taskResults += [PSCustomObject]@{ name = $taskName; project_path = $taskTarget; user_path = $taskUserTarget }
}
[PSCustomObject]@{ ok = $true; scope = $Scope; skills = $taskResults } | ConvertTo-Json -Depth 4
