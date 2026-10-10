#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
( cd backend && ../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 ) &
cd frontend
[ -d node_modules ] || npm install
export VITE_API_URL=http://localhost:8000
npm run dev -- --host 127.0.0.1
