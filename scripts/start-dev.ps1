# API(8000) + Vite(5173) — 새 PowerShell 창 2개에서 실행합니다.
# 한글 등 유니코드 경로: 자식 프로세스는 -File 로만 띄워 경로 인코딩 깨짐(怨쇱젣)을 피합니다.
# 사용 전: pip install -e .  및 frontend 에서 npm install

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunApi = Join-Path $PSScriptRoot "run-api.ps1"
$RunFe = Join-Path $PSScriptRoot "run-frontend.ps1"

foreach ($f in @($RunApi, $RunFe)) {
    if (-not (Test-Path -LiteralPath $f)) {
        Write-Error "스크립트가 없습니다: $f"
        exit 1
    }
}

Write-Host "Project: $ProjectRoot"
Write-Host "Starting API: http://0.0.0.0:8000 (로컬: http://127.0.0.1:8000)"
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $RunApi
)

Write-Host "Starting Vite: http://127.0.0.1:5173 (또는 이 PC IP:5173)"
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $RunFe
)

Write-Host "Done. 브라우저에서 http://127.0.0.1:5173 을 여세요."
