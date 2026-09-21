param(
    [Parameter(Mandatory = $true)] [string]$Slug,
    [string]$ComfyUrl = 'http://127.0.0.1:8188',
    [string]$WorkflowPath,
    [int]$PollSeconds = 2,
    [int]$TimeoutSeconds = 1800
)

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$outputDir = Join-Path $projectRoot "output\$Slug"
$mediaDir = Join-Path $projectRoot "media-tasks\local-$Slug"
$promptFile = Join-Path $outputDir '04-prompts.md'
if (-not (Test-Path -LiteralPath $promptFile)) { throw "找不到 $promptFile" }
if (-not $WorkflowPath) { $WorkflowPath = Join-Path $projectRoot 'workflows\animatediff-api.example.json' }
if (-not (Test-Path -LiteralPath $WorkflowPath)) { throw "找不到工作流：$WorkflowPath" }

& "$PSScriptRoot\check-local-backend.ps1" -ComfyUrl $ComfyUrl
$promptText = Get-Content -LiteralPath $promptFile -Raw
$matches = [regex]::Matches($promptText, '(?ms)^##\s+镜\s+([^\r\n]+).*?^\*\*生视频：\*\*\s*([^\r\n]+)')
if ($matches.Count -eq 0) { throw '没有找到生视频提示词。' }

New-Item -ItemType Directory -Force -Path $mediaDir | Out-Null
$manifest = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $matches.Count; $i++) {
    $shotDir = Join-Path $mediaDir ("shot-{0:D2}" -f ($i + 1))
    New-Item -ItemType Directory -Force -Path $shotDir | Out-Null
    $manifest.Add([pscustomobject]@{
        shot = $i + 1
        name = $matches[$i].Groups[1].Value.Trim()
        prompt = $matches[$i].Groups[2].Value.Trim()
        status = 'ready-for-workflow-mapping'
        output_dir = $shotDir
    })
}

$manifestPath = Join-Path $mediaDir 'manifest.json'
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "已解析 $($matches.Count) 个镜头。" -ForegroundColor Green
Write-Host "注意：请先把 ComfyUI 导出的真实 API workflow JSON 放入 $WorkflowPath，再将 prompt 节点映射到该工作流。" -ForegroundColor Yellow
Write-Host "任务清单：$manifestPath"
