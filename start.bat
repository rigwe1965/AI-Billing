@echo off
REM Starts the AI Billing backend (port 8000) and frontend (port 5173), then opens the browser.
set ROOT=%~dp0

start "AI Billing - Backend" cmd /k "cd /d "%ROOT%backend" && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
start "AI Billing - Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

timeout /t 6 /nobreak >nul
start "" http://localhost:5173
