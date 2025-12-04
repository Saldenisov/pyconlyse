@echo off
REM Pyconlyse Development Servers Startup Script (Batch)
REM Purpose: Start Tango, pyconlyse backend, and frontend dev servers
REM Usage: start_dev_servers.bat

setlocal enabledelayedexpansion

echo.
echo ================================================
echo Starting Pyconlyse Development Servers
echo ================================================
echo.

REM Check if TANGO_ROOT is defined
if not defined TANGO_ROOT (
    echo ERROR: TANGO_ROOT is not defined!
    echo Please define TANGO_ROOT environment variable.
    pause
    exit /b 1
)

echo TANGO_ROOT: %TANGO_ROOT%

REM Check if TANGO_HOST is defined
if not defined TANGO_HOST (
    echo ERROR: TANGO_HOST is not defined!
    echo Please define TANGO_HOST environment variable (e.g., localhost:10000).
    pause
    exit /b 1
)

echo TANGO_HOST: %TANGO_HOST%

REM Check database executable
if not exist "%TANGO_ROOT%\bin\Databaseds.exe" (
    echo ERROR: Databaseds.exe not found in %TANGO_ROOT%\bin\
    pause
    exit /b 1
)

echo.
echo Starting services in separate windows...
echo.

REM Start Tango Database
echo [1/3] Starting Tango Database...
if exist "%TANGO_ROOT%\bin\start-db-persistent.ps1" (
    start "Tango Database" powershell -NoExit -File "%TANGO_ROOT%\bin\start-db-persistent.ps1"
) else (
    start "Tango Database" powershell -NoExit -Command "cd '%TANGO_ROOT%\bin'; .\Databaseds.exe"
)
timeout /t 3 /nobreak

REM Start Tango Starter (if exists)
if exist "%TANGO_ROOT%\bin\Starter.exe" (
    echo [2/3] Starting Tango Starter...
    if exist "%TANGO_ROOT%\bin\start-starter-persistent.ps1" (
        start "Tango Starter" powershell -NoExit -File "%TANGO_ROOT%\bin\start-starter-persistent.ps1"
    ) else (
        start "Tango Starter" powershell -NoExit -Command "cd '%TANGO_ROOT%\bin'; .\Starter.exe"
    )
    timeout /t 2 /nobreak
)

REM Start pyconlyse backend (production server)
echo [3/3] Starting Pyconlyse Backend (Production)...
if exist "C:\dev\pyconlyse\web\start_production.py" (
    start "Pyconlyse Backend (Port 5000)" powershell -NoExit -Command "conda activate pyconlyse39; cd 'C:\dev\pyconlyse\web'; python start_production.py"
    echo Backend started on port 5000
) else (
    echo WARNING: Pyconlyse production server script not found
)

REM Start pyconlyse frontend (dev server)
echo [4/4] Starting Pyconlyse Frontend (Dev)...
if exist "C:\dev\pyconlyse\web\frontend" (
    start "Pyconlyse Frontend (Port 5001)" powershell -NoExit -Command "cd 'C:\dev\pyconlyse\web\frontend'; npm run dev -- --port 5001"
    echo Frontend started on port 5001
) else (
    echo WARNING: Pyconlyse frontend not found
)

echo.
echo ================================================
echo Development servers startup initiated!
echo ================================================
echo.
echo Services:
echo  - Tango Database
echo  - Tango Starter (if available)
echo  - Pyconlyse Backend: http://localhost:5000
echo  - Pyconlyse Frontend: http://localhost:5001
echo.
echo Close this window when done.
pause
