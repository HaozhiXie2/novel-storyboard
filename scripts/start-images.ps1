param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$filmRoot = Split-Path -Parent $PSScriptRoot
$filmPython = Join-Path $filmRoot '.local\venv\Scripts\python.exe'
$filmCli = Join-Path $filmRoot '.tools\dreamina.exe'
$filmAddress = 'http://127.0.0.1:7861'

if (-not (Test-Path -LiteralPath $filmPython -PathType Leaf)) {
    throw 'The local Python runtime is missing. Restore the project runtime before starting Film Studio.'
}
if (-not (Test-Path -LiteralPath $filmCli -PathType Leaf)) {
    throw 'The Dreamina CLI is missing from .tools/dreamina.exe. No generation request was submitted.'
}

function Test-FilmService {
    try {
        $filmStatus = Invoke-RestMethod ($filmAddress + '/api/status') -TimeoutSec 2
    } catch {
        return $false
    }
    if ($filmStatus.app -ne 'novel-film-studio') {
        throw 'Port 7861 is used by a different service. It was not stopped or changed.'
    }
    return $true
}

$filmRunning = Test-FilmService
if (-not $filmRunning) {
    Start-Process -FilePath $filmPython -ArgumentList 'app/image_server.py' -WorkingDirectory $filmRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $filmRoot '.local/images.log') -RedirectStandardError (Join-Path $filmRoot '.local/images-error.log')
    for ($filmAttempt = 0; $filmAttempt -lt 20; $filmAttempt++) {
        if (Test-FilmService) { $filmRunning = $true; break }
        Start-Sleep -Seconds 1
    }
}
if (-not $filmRunning) { throw 'Film Studio did not start. See .local/images-error.log.' }
Write-Host ('Film Studio: ' + $filmAddress)
if (-not $NoBrowser) { Start-Process $filmAddress }
