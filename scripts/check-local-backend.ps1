param(
    [string]$ComfyUrl = 'http://127.0.0.1:8188'
)

try {
    $response = Invoke-WebRequest -Uri "$ComfyUrl/system_stats" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -ne 200) { throw "HTTP $($response.StatusCode)" }
    Write-Host "ComfyUI API 可用：$ComfyUrl" -ForegroundColor Green
    $response.Content
} catch {
    Write-Error "ComfyUI API 不可用：$ComfyUrl。请先启动 ComfyUI。原因：$($_.Exception.Message)"
    exit 1
}
