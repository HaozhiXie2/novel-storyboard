param(
    [string]$Slug,
    [string]$TextFile,
    [ValidateSet(10,30,60,90)][int]$Duration = 30,
    [switch]$Automatic
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $TextFile) {
    if (-not $Slug -or $Slug -match '[/\\]|\.\.') { throw 'Provide -TextFile or a simple -Slug matching source/<slug>.md.' }
    $TextFile = Join-Path $projectRoot "source\$Slug.md"
}
if (-not (Test-Path -LiteralPath $TextFile)) { throw "Source file not found: $TextFile" }
$TextFile = (Resolve-Path -LiteralPath $TextFile).Path
& "$PSScriptRoot\start-studio.ps1" -NoBrowser
$cliArgs = @((Join-Path $projectRoot 'app\cli.py'), $TextFile, '--duration', "$Duration")
if ($Automatic) { $cliArgs += '--automatic' }
& (Join-Path $projectRoot '.local\venv\Scripts\python.exe') @cliArgs
if ($LASTEXITCODE -ne 0) { throw 'Submission failed. See output above.' }
