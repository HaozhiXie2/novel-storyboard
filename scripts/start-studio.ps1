param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.local\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Local Python environment is missing.' }
$runtime = Join-Path $projectRoot '.local'
function Test-Service($url) {
    try { Invoke-RestMethod -Uri $url -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
if (-not (Test-Service 'http://127.0.0.1:8188/system_stats')) {
    Start-Process -FilePath $python -ArgumentList @('main.py','--listen','127.0.0.1','--port','8188','--lowvram','--disable-auto-launch') -WorkingDirectory (Join-Path $runtime 'ComfyUI') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'comfyui.log') -RedirectStandardError (Join-Path $runtime 'comfyui-error.log')
}
if (-not (Test-Service 'http://127.0.0.1:7860/api/jobs')) {
    Start-Process -FilePath $python -ArgumentList @('app/server.py') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'studio.log') -RedirectStandardError (Join-Path $runtime 'studio-error.log')
}
for ($i=0; $i -lt 30; $i++) {
    if (Test-Service 'http://127.0.0.1:7860/api/jobs') { break }
    Start-Sleep -Seconds 1
}
if (-not (Test-Service 'http://127.0.0.1:7860/api/jobs')) { throw 'Studio failed to start. See .local/studio-error.log.' }
Write-Host 'Novel Studio: http://127.0.0.1:7860'
if (-not $NoBrowser) {
    $chrome = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
    if (Test-Path -LiteralPath $chrome) {
        Start-Process -FilePath $chrome -ArgumentList @('--new-window', 'http://127.0.0.1:7860/')
    } else {
        Start-Process 'http://127.0.0.1:7860/'
    }
}
