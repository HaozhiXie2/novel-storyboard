param([Parameter(Mandatory=$true)][string]$TextPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$python = Join-Path (Split-Path -Parent $PSScriptRoot) '.local\venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'narrate.py') $TextPath $OutputPath
if ($LASTEXITCODE) { throw "中文旁白合成失败，退出码 $LASTEXITCODE" }
