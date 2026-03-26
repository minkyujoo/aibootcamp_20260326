# rag-orchestrator-agent 의 "한 단계 위" 폴더 이름에 과제 등 한글이 있으면 영어로 바꿉니다.
# Cursor/IDE에서 이 저장소를 연 채로는 이동이 실패할 수 있으니, 먼저 창을 닫고 실행하세요.
# 실행: powershell -ExecutionPolicy Bypass -File .\scripts\move-assignment-folder-to-english.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AssignmentRoot = Split-Path -Parent $ProjectRoot
$Parent = Split-Path -Parent $AssignmentRoot
$Leaf = Split-Path -Leaf $AssignmentRoot

if ($Leaf -notmatch "[\uAC00-\uD7A3]") {
    Write-Host "상위 폴더에 한글이 없습니다: $Leaf — 변경 없음."
    exit 0
}

$NewLeaf = $Leaf -creplace "과제", "_assignment"
if ($NewLeaf -eq $Leaf) {
    $NewLeaf = [regex]::Replace($Leaf, "[\uAC00-\uD7A3]+", "assignment")
}
$TargetFull = Join-Path $Parent $NewLeaf
if (Test-Path -LiteralPath $TargetFull) {
    Write-Error "대상 폴더가 이미 있습니다: $TargetFull"
    exit 1
}

Write-Host "이동:"
Write-Host "  $AssignmentRoot"
Write-Host "-> $TargetFull"
Move-Item -LiteralPath $AssignmentRoot -Destination $TargetFull
$repo = Join-Path $TargetFull (Split-Path -Leaf $ProjectRoot)
Write-Host "완료. Cursor에서 다음 폴더를 다시 여세요:"
Write-Host "  $repo"
