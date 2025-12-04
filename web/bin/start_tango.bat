@echo off
REM Tango Services Startup Script
REM Purpose: Start Tango Database and Starter services
REM Usage: start_tango.bat

setlocal enabledelayedexpansion

echo.
echo ================================================
echo Starting Tango Services
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
echo Starting Tango services in separate windows...
echo.

REM Start Tango Database
echo [1/2] Starting Tango Database...
if exist "%TANGO_ROOT%\bin\start-db-persistent.ps1" (
    start "Tango Database" powershell -NoExit -File "%TANGO_ROOT%\bin\start-db-persistent.ps1"
) else (
    start "Tango Database" powershell -NoExit -Command "cd '%TANGO_ROOT%\bin'; .\Databaseds.exe"
)
timeout /t 3 /nobreak

REM Start Tango Starter (if exists)
if exist "%TANGO_ROOT%\bin\Starter.exe" (
    echo [2/2] Starting Tango Starter...
    if exist "%TANGO_ROOT%\bin\start-starter-persistent.ps1" (
        start "Tango Starter" powershell -NoExit -File "%TANGO_ROOT%\bin\start-starter-persistent.ps1"
    ) else (
        start "Tango Starter" powershell -NoExit -Command "cd '%TANGO_ROOT%\bin'; .\Starter.exe"
    )
) else (
    echo WARNING: Tango Starter not found
)

echo.
echo ================================================
echo Tango services startup initiated!
echo ================================================
echo.
pause
