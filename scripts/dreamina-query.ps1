param(
    [Parameter(Mandatory = $true)]
    [string]$SubmitId,
    [string]$DownloadDir
)

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$cli = Join-Path $projectRoot '.tools\dreamina.exe'
if (-not (Test-Path -LiteralPath $cli)) {
    throw "找不到 Dreamina CLI：$cli。请先安装官方 CLI。"
}

if ([string]::IsNullOrWhiteSpace($DownloadDir)) {
    & $cli query_result --submit_id=$SubmitId
} else {
    New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
    & $cli query_result --submit_id=$SubmitId --download_dir=$DownloadDir
}
if ($LASTEXITCODE -ne 0) {
    throw "Dreamina 任务查询失败：$SubmitId"
}
