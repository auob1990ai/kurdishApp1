@echo off
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r backend\requirements.txt
start "KurdText API" cmd /k "cd /d %~dp0backend && ..\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000"
cd frontend
if not exist node_modules npm install
set VITE_API_URL=http://localhost:8000
npm run dev -- --host 127.0.0.1
