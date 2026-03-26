# 프로젝트 루트에서 실행: .\start-app.ps1
# (한글 경로에서도 scripts\start-dev.ps1 을 안전하게 호출)
$ErrorActionPreference = "Stop"
$Start = Join-Path $PSScriptRoot "scripts\start-dev.ps1"
& $Start
