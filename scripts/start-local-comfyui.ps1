param(
    [int]$Port = 8188,
    [switch]$Cpu
)

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$localRoot = Join-Path $projectRoot '.local'
$candidates = @(
    (Join-Path $localRoot 'ComfyUIPortable\ComfyUI\main.py'),
    (Join-Path $localRoot 'ComfyUI\main.py')
)
$main = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $main) {
    throw "未找到 ComfyUI。请先将官方便携版解压到 $localRoot\ComfyUIPortable，或将源码放到 $localRoot\ComfyUI。"
}

$root = Split-Path -Parent $main
$python = Join-Path $root 'python_embeded\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $python) { throw '找不到 Python。请使用官方便携版，或安装 Python 3.10+。'}

$args = @('main.py', '--listen', '127.0.0.1', '--port', $Port)
if ($Cpu) { $args += '--cpu' }
$log = Join-Path $localRoot 'comfyui.log'
$err = Join-Path $localRoot 'comfyui-error.log'
Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err
Write-Host "ComfyUI 已在后台启动： http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "日志：$log"
