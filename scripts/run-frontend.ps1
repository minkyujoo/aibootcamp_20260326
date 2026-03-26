# Child launcher: frontend 폴더로 이동 후 Vite 실행 (경로는 $PSScriptRoot 기준으로만 계산).
$ErrorActionPreference = "Stop"
$pathRefresh = '$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User"); '
Invoke-Expression $pathRefresh
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path -LiteralPath $Frontend)) {
    Write-Error "frontend 폴더를 찾을 수 없습니다: $Frontend"
    exit 1
}
Set-Location -LiteralPath $Frontend
npm run dev
