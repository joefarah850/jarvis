@echo off
cd /d "%~dp0"

REM Check if .venv exists
if not exist ".venv\Scripts\python.exe" (
    echo Setting up Jarvis for the first time...
    python setup.py
)

REM Start Jarvis Python backend (hidden window)
start /B "" .venv\Scripts\python.exe main.py

REM Wait for WebSocket bridge to start
timeout /t 3 /nobreak > nul

REM Start Electron UI
cd ui
call npm start