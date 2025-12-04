@echo off
REM Frontend Development Server Startup Script
REM Purpose: Start npm dev server on port 3001
REM Usage: start_frontend_dev.bat

setlocal enabledelayedexpansion

echo.
echo ================================================
echo Starting Pyconlyse Frontend Dev Server
echo ================================================
echo.

REM Check if frontend directory exists
if not exist "C:\dev\pyconlyse\web\frontend" (
    echo ERROR: Frontend directory not found at C:\dev\pyconlyse\web\frontend
    pause
    exit /b 1
)

REM Check if node_modules exists
if not exist "C:\dev\pyconlyse\web\frontend\node_modules" (
    echo Installing dependencies...
    cd /d "C:\dev\pyconlyse\web\frontend"
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed
        pause
        exit /b 1
    )
)

echo Starting npm dev server on port 3001...
echo.

cd /d "C:\dev\pyconlyse\web\frontend"
call npm run dev -- --port 3001

pause
