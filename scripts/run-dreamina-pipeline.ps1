param(
    [Parameter(Mandatory = $true)] [string]$Slug,
    [string]$SourcePath,
    [ValidateSet('9:16','16:9','1:1','4:3','3:4','21:9')] [string]$Ratio = '9:16',
    [ValidateSet('720p','1080p','4k')] [string]$Resolution = '720p',
    [ValidateRange(4,30)] [int]$Duration = 5,
    [int]$Poll = 60,
    [switch]$ContinueOnError
)

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$cli = Join-Path $projectRoot '.tools\dreamina.exe'
$sourceDir = Join-Path $projectRoot 'source'
$outputDir = Join-Path $projectRoot "output\$Slug"
$mediaDir = Join-Path $projectRoot "media-tasks\$Slug"
$manifestPath = Join-Path $mediaDir 'manifest.json'

if (-not (Test-Path -LiteralPath $cli)) { throw "找不到 Dreamina CLI：$cli" }
if ($SourcePath) {
    $source = (Resolve-Path -LiteralPath $SourcePath -ErrorAction Stop).Path
    New-Item -ItemType Directory -Force -Path $sourceDir | Out-Null
    Copy-Item -LiteralPath $source -Destination (Join-Path $sourceDir "$Slug.md") -Force
}

$promptFile = Join-Path $outputDir '04-prompts.md'
if (-not (Test-Path -LiteralPath $promptFile -PathType Leaf)) {
    throw "找不到 $promptFile。请先让 novel-director 根据 source 文本生成 04-prompts.md。"
}
$promptText = Get-Content -LiteralPath $promptFile -Raw
$matches = [regex]::Matches($promptText, '(?ms)^##\s+镜\s+([^\r\n]+).*?^\*\*生视频：\*\*\s*([^\r\n]+)')
if ($matches.Count -eq 0) { throw "没有找到生视频提示词。" }

New-Item -ItemType Directory -Force -Path $mediaDir | Out-Null
$tasks = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $matches.Count; $i++) {
    $shotName = $matches[$i].Groups[1].Value.Trim()
    $prompt = $matches[$i].Groups[2].Value.Trim()
    $shotDir = Join-Path $mediaDir ("shot-{0:D2}" -f ($i + 1))
    New-Item -ItemType Directory -Force -Path $shotDir | Out-Null
    Write-Host ("提交镜头 {0}/{1}: {2}" -f ($i + 1), $matches.Count, $shotName) -ForegroundColor Cyan

    $raw = & $cli text2video --prompt=$prompt --model_version=seedance2.0fast --duration=$Duration --ratio=$Ratio --video_resolution=$Resolution --poll=$Poll --session=0 2>&1 | Out-String
    $result = $null
    try { $result = $raw | ConvertFrom-Json } catch { }
    if (-not $result -or $result.gen_status -eq 'fail') {
        $reason = if ($result) { $result.fail_reason } else { $raw.Trim() }
        $tasks.Add([pscustomobject]@{ shot = $i + 1; name = $shotName; status = 'fail'; reason = $reason })
        $tasks | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
        if (-not $ContinueOnError) { throw "镜头 $($i + 1) 生成失败：$reason" }
        continue
    }

    $submitId = $result.submit_id
    $download = & $cli query_result --submit_id=$submitId --download_dir=$shotDir 2>&1 | Out-String
    $downloadResult = $null
    try { $downloadResult = $download | ConvertFrom-Json } catch { }
    $status = if ($downloadResult -and $downloadResult.gen_status -eq 'success') { 'success' } else { 'querying' }
    $tasks.Add([pscustomobject]@{ shot = $i + 1; name = $shotName; status = $status; submit_id = $submitId; output_dir = $shotDir; credit_count = $result.credit_count })
    $tasks | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    if ($status -ne 'success' -and -not $ContinueOnError) { throw "镜头 $($i + 1) 尚未完成，请稍后查询 submit_id=$submitId" }
}
Write-Host "流水线完成。任务清单：$manifestPath" -ForegroundColor Green
