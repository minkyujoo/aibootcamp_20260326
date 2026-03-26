@echo off
REM API(8000) + Vite(5173) — Node/npm 과 Python 이 PATH 에 있어야 합니다.
set "ROOT=%~dp0.."
cd /d "%ROOT%"
start "rag-api-8000" cmd /k "python -m uvicorn rag_agent.api.main:app --reload --host 0.0.0.0 --port 8000"
cd /d "%ROOT%\frontend"
start "vite-5173" cmd /k "npm run dev"
echo 브라우저: http://127.0.0.1:5173
