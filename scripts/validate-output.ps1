param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$required = @(
    '00-rights.md',
    '01-summary.md',
    '02-bible.md',
    '03-storyboard.md',
    '04-prompts.md'
)

$resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
$missing = @()
$empty = @()

foreach ($name in $required) {
    $file = Join-Path $resolved $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        $missing += $name
        continue
    }
    if ((Get-Item -LiteralPath $file).Length -eq 0) {
        $empty += $name
    }
}

if ($missing.Count -gt 0 -or $empty.Count -gt 0) {
    if ($missing.Count -gt 0) { Write-Host "缺少文件: $($missing -join ', ')" -ForegroundColor Red }
    if ($empty.Count -gt 0) { Write-Host "空文件: $($empty -join ', ')" -ForegroundColor Red }
    exit 1
}

Write-Host "输出校验通过: $resolved" -ForegroundColor Green
