@echo off
title BlendAgent planner (FastAPI)
cd /d "%~dp0"
echo Installing Python deps (if needed)...
py -m pip install -q -r requirements.txt 2>nul
if errorlevel 1 python -m pip install -q -r requirements.txt
echo.
echo Starting planner on http://127.0.0.1:8000  (Ctrl+C to stop)
echo In Blender, set Planner to "Planner server (advanced)" and API base to that URL.
echo.
py -m uvicorn agent_server:app --host 127.0.0.1 --port 8000
if errorlevel 1 python -m uvicorn agent_server:app --host 127.0.0.1 --port 8000
pause
