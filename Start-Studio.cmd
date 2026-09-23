@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-studio.ps1"
if errorlevel 1 (
  echo.
  echo 启动失败。上面是错误原因。
  pause
) else (
  echo.
  echo 小说影坊已打开： http://127.0.0.1:7860
  echo 这个窗口可以关掉，关掉不会停止制作。
  pause
)
