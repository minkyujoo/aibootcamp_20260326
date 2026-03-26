# GitHub 원격(minkyujoo/aibootcamp_20260326)에 최초 업로드·이후 동기화
# 사용: PowerShell에서 이 저장소 루트가 아니라도, 이 파일만 -File 로 실행 가능
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-to-github.ps1
$ErrorActionPreference = "Stop"

function Find-Git {
    $candidates = @(
        (Get-Command git -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        "$env:LocalAppData\Programs\Git\cmd\git.exe",
        "$env:ProgramFiles\Git\cmd\git.exe",
        "${env:ProgramFiles(x86)}\Git\cmd\git.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    if ($candidates) { return $candidates[0] }
    return $null
}

$GitExe = Find-Git
if (-not $GitExe) {
    Write-Error "Git을 찾을 수 없습니다. https://git-scm.com/download/win 설치 후 PATH에 cmd 를 넣고 다시 실행하세요."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

$RemoteUrl = "https://github.com/minkyujoo/aibootcamp_20260326.git"

Write-Host "Project: $ProjectRoot"
Write-Host "Git:     $GitExe"

& $GitExe -C $ProjectRoot init
if (Test-Path -LiteralPath (Join-Path $ProjectRoot ".git\HEAD")) {
    & $GitExe -C $ProjectRoot branch -M main
}

$remotes = @(& $GitExe -C $ProjectRoot remote 2>$null)
if ($remotes -contains "origin") {
    & $GitExe -C $ProjectRoot remote set-url origin $RemoteUrl
} else {
    & $GitExe -C $ProjectRoot remote add origin $RemoteUrl
}

& $GitExe -C $ProjectRoot add -A
& $GitExe -C $ProjectRoot status

$st = @(& $GitExe -C $ProjectRoot status --porcelain)
if ($st.Count -eq 0) {
    Write-Host "커밋할 변경 없음 — push 만 시도합니다."
} else {
    & $GitExe -C $ProjectRoot commit -m "Initial commit: AI 영업관리 포탈 (RAG·CRM·오케스트레이터)"
}

& $GitExe -C $ProjectRoot push -u origin main
Write-Host "완료: $RemoteUrl"
