@echo off
REM First time: creates a venv, installs everything, builds the UI. After that just starts the server.
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r backend\requirements.txt
) else (
  call .venv\Scripts\activate
)
if not exist frontend\dist (
  pushd frontend
  call npm install
  call npm run build
  popd
)
cd backend
echo.
echo Matchpoint running at http://localhost:8000
python -m uvicorn app.main:app --port 8000
