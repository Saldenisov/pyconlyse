@echo off
REM =====================================================
REM TANGO INFRASTRUCTURE - Windows Auto Startup
REM This script starts Tango Database and Starter on Windows boot
REM Place this in Windows Startup folder or Task Scheduler
REM =====================================================

setlocal enabledelayedexpansion

REM Set script directory
set SCRIPT_DIR=%~dp0
set LOG_FILE=%SCRIPT_DIR%tango_windows_startup.log

echo.
echo =====================================================
echo TANGO INFRASTRUCTURE - Windows Startup Service
echo =====================================================
echo [%date% %time%] Starting Tango Infrastructure...
echo [%date% %time%] Starting Tango Infrastructure... >> "%LOG_FILE%"

REM Validate environment
if not defined TANGO_ROOT (
    echo ERROR: TANGO_ROOT environment variable not set!
    echo [%date% %time%] ERROR: TANGO_ROOT environment variable not set! >> "%LOG_FILE%"
    pause
    exit /b 1
)

echo TANGO_ROOT: %TANGO_ROOT%
echo [%date% %time%] TANGO_ROOT: %TANGO_ROOT% >> "%LOG_FILE%"
echo.

REM Step 1: Start Tango Database in separate terminal
echo [%date% %time%] === STARTING TANGO DATABASE ===
echo [%date% %time%] === STARTING TANGO DATABASE === >> "%LOG_FILE%"
echo Starting Tango Database in separate terminal...
start "Tango-Database-Service" cmd /k "%TANGO_ROOT%\bin\start-db.bat"
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Tango Database terminal
    echo [%date% %time%] ERROR: Failed to start Tango Database >> "%LOG_FILE%"
    pause
    exit /b 1
)
echo Database terminal started successfully

REM Wait for database to initialize
echo Waiting for database to initialize (10 seconds)...
timeout /t 10 /nobreak >nul

REM Step 2: Start Tango Starter in separate terminal
echo.
echo [%date% %time%] === STARTING TANGO STARTER ===
echo [%date% %time%] === STARTING TANGO STARTER === >> "%LOG_FILE%"
echo Starting Tango Starter in separate terminal...

REM Get hostname for starter
for /f "tokens=*" %%i in ('hostname') do set HOSTNAME=%%i
echo Using hostname: %HOSTNAME%

start "Tango-Starter-%HOSTNAME%" cmd /k "%TANGO_ROOT%\bin\Starter.exe %HOSTNAME%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Tango Starter terminal
    echo [%date% %time%] ERROR: Failed to start Tango Starter >> "%LOG_FILE%"
    pause
    exit /b 1
)
echo Starter terminal started successfully

echo.
echo [%date% %time%] === TANGO INFRASTRUCTURE STARTUP COMPLETED ===
echo [%date% %time%] === TANGO INFRASTRUCTURE STARTUP COMPLETED === >> "%LOG_FILE%"

REM Show status
echo.
echo =====================================================
echo TANGO INFRASTRUCTURE STATUS:
echo =====================================================
echo - Database: Running in separate terminal (Tango-Database-Service)
echo - Starter:  Running in separate terminal (Tango-Starter-%HOSTNAME%)
echo - Log file: %LOG_FILE%
echo.
echo You should now see 2 additional terminal windows:
echo   1. Tango Database (running start-db.bat)
echo   2. Tango Starter (running Starter.exe)
echo.
echo This main window will close in 10 seconds...
echo.

REM Countdown
for /L %%i in (10,-1,1) do (
    echo Closing in %%i seconds...
    timeout /t 1 /nobreak >nul
)

exit /b 0
