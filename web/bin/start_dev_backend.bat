@echo off
REM Backend DEV Server Startup Script
REM Purpose: Start Python backend DEV server on port 5001
REM Usage: start_backend_dev.bat

setlocal enabledelayedexpansion

echo.
echo ================================================
echo Starting Pyconlyse Backend DEV Server
echo ================================================
echo.

REM Check if backend directory exists
if not exist "C:\dev\pyconlyse\web\backend" (
    echo ERROR: Backend directory not found at C:\dev\pyconlyse\web\backend
    pause
    exit /b 1
)

echo Starting Python backend DEV server on port 5001...
echo.

REM Activate conda environment and start server with dev config
cd /d "C:\dev\pyconlyse\web\backend"
call conda activate pyconlyse39
set FLASK_APP=app.py
set FLASK_ENV=development
set FLASK_DEBUG=1
call python -m flask run --port 5001

pause
