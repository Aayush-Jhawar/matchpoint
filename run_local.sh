#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv; . .venv/bin/activate; pip install -r backend/requirements.txt; }
. .venv/bin/activate
[ -d frontend/dist ] || (cd frontend && npm install && npm run build)
cd backend && echo "Matchpoint running at http://localhost:8000" && python -m uvicorn app.main:app --port 8000
