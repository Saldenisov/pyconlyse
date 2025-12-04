@echo off
REM Pyconlyse Development Servers Startup Script
REM Purpose: Start pyconlyse backend (port 5000) and frontend (port 5001)
REM Usage: start_pyconlyse.bat

setlocal enabledelayedexpansion

echo.
echo ================================================
echo Starting Pyconlyse Servers
echo ================================================
echo.

REM Start pyconlyse backend (production server)
echo [1/2] Starting Pyconlyse Backend (Port 5000)...
if exist "C:\dev\pyconlyse\web\start_production.py" (
    start "Pyconlyse Backend (Port 5000)" powershell -NoExit -Command "conda activate pyconlyse39; cd 'C:\dev\pyconlyse\web'; python start_production.py"
    echo Backend started on port 5000
) else (
    echo ERROR: Pyconlyse production server script not found at C:\dev\pyconlyse\web\start_production.py
    pause
    exit /b 1
)

timeout /t 2 /nobreak

REM Start pyconlyse frontend (dev server)
echo [2/2] Starting Pyconlyse Frontend (Port 5001)...
if exist "C:\dev\pyconlyse\web\frontend" (
    start "Pyconlyse Frontend (Port 5001)" powershell -NoExit -Command "cd 'C:\dev\pyconlyse\web\frontend'; npm run dev -- --port 5001"
    echo Frontend started on port 5001
) else (
    echo ERROR: Pyconlyse frontend not found at C:\dev\pyconlyse\web\frontend
    pause
    exit /b 1
)

echo.
echo ================================================
echo Pyconlyse servers startup initiated!
echo ================================================
echo.
echo Services:
echo  - Backend: http://localhost:5000
echo  - Frontend: http://localhost:5001
echo.
pause
