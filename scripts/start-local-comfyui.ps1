param([int]$Port = 8188,[switch]$Cpu)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot '.local'
$python = Join-Path $runtime 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Local Python environment is missing.' }
try { Invoke-RestMethod "http://127.0.0.1:$Port/system_stats" -TimeoutSec 2 | Out-Null; Write-Host 'ComfyUI is already running.'; return } catch {}
$arguments = @('main.py','--listen','127.0.0.1','--port',"$Port",'--disable-auto-launch')
if ($Cpu) { $arguments += '--cpu' } else { $arguments += '--lowvram' }
Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory (Join-Path $runtime 'ComfyUI') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'comfyui.log') -RedirectStandardError (Join-Path $runtime 'comfyui-error.log')
for ($i=0; $i -lt 60; $i++) {
    try { Invoke-RestMethod "http://127.0.0.1:$Port/system_stats" -TimeoutSec 2 | Out-Null; Write-Host "ComfyUI ready: http://127.0.0.1:$Port"; return } catch { Start-Sleep -Seconds 1 }
}
throw 'ComfyUI did not become ready. See .local/comfyui-error.log.'
