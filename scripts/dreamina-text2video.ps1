param(
    [Parameter(Mandatory = $true)]
    [string]$Prompt,
    [ValidateSet('1:1','3:4','16:9','4:3','9:16','21:9')]
    [string]$Ratio = '16:9',
    [ValidateSet('720p','1080p','4k','480p')]
    [string]$Resolution = '720p',
    [ValidateSet('seedance2.0','seedance2.0fast','seedance2.0_vip','seedance2.0fast_vip','seedance2.0mini','seedance2.5')]
    [string]$Model = 'seedance2.0fast',
    [ValidateRange(4,30)]
    [int]$Duration = 5,
    [int]$Poll = 30,
    [int]$Session = 0
)

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$cli = Join-Path $projectRoot '.tools\dreamina.exe'
if (-not (Test-Path -LiteralPath $cli)) {
    throw "找不到 Dreamina CLI：$cli。请先安装官方 CLI。"
}

& $cli text2video --prompt=$Prompt --ratio=$Ratio --video_resolution=$Resolution --model_version=$Model --duration=$Duration --poll=$Poll --session=$Session
if ($LASTEXITCODE -ne 0) {
    throw "Dreamina 视频任务提交失败。请检查模型权限、登录状态和账户额度。"
}
