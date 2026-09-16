param(
    [Parameter(Mandatory = $true)]
    [string]$Prompt,
    [ValidateSet('21:9','16:9','3:2','4:3','1:1','3:4','2:3','9:16')]
    [string]$Ratio = '16:9',
    [ValidateSet('1k','1.5k','2k','4k')]
    [string]$Resolution = '2k',
    [int]$Poll = 30,
    [int]$Session = 0
)

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$cli = Join-Path $projectRoot '.tools\dreamina.exe'
if (-not (Test-Path -LiteralPath $cli)) {
    throw "找不到 Dreamina CLI：$cli。请先安装官方 CLI。"
}

& $cli text2image --prompt=$Prompt --ratio=$Ratio --resolution_type=$Resolution --poll=$Poll --session=$Session
if ($LASTEXITCODE -ne 0) {
    throw "Dreamina 图片任务提交失败。请检查登录状态、会员权限和账户额度。"
}
