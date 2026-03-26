# Child launcher: 한글 경로를 -Command 문자열에 넣지 않기 위해 -File 로만 호출합니다.
$ErrorActionPreference = "Stop"
$pathRefresh = '$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User"); '
Invoke-Expression $pathRefresh
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
python -m uvicorn rag_agent.api.main:app --reload --host 0.0.0.0 --port 8000
