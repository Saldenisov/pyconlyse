@echo off
REM =====================================================
REM TANGO STARTER - Windows Startup Service
REM This script starts Tango Starter on Windows boot
REM Requires Tango Database to be running first
REM =====================================================

setlocal enabledelayedexpansion

REM Set script directory
set SCRIPT_DIR=%~dp0
set LOG_FILE=%SCRIPT_DIR%tango_starter_startup.log

REM Log startup attempt
echo [%date% %time%] Starting Tango Starter service... >> "%LOG_FILE%"

REM Check if TANGO_ROOT is set
if not defined TANGO_ROOT (
    echo [%date% %time%] ERROR: TANGO_ROOT environment variable not set! >> "%LOG_FILE%"
    exit /b 1
)

REM Get hostname (typically 'everest' for your system)
for /f "tokens=*" %%i in ('hostname') do set HOSTNAME=%%i
set HOSTNAME=%HOSTNAME%

echo [%date% %time%] Using hostname: %HOSTNAME% >> "%LOG_FILE%"

REM Wait for Tango Database to be available (max 60 seconds)
echo [%date% %time%] Waiting for Tango Database to be available... >> "%LOG_FILE%"
set DB_WAIT_COUNT=0
:wait_for_db
netstat -an | findstr ":10000" >nul 2>&1
if %errorlevel% == 0 goto db_ready

set /a DB_WAIT_COUNT+=1
if %DB_WAIT_COUNT% GEQ 12 (
    echo [%date% %time%] ERROR: Tango Database not available after 60 seconds >> "%LOG_FILE%"
    exit /b 1
)

echo [%date% %time%] Waiting for database... (%DB_WAIT_COUNT%/12) >> "%LOG_FILE%"
timeout /t 5 /nobreak >nul
goto wait_for_db

:db_ready
echo [%date% %time%] Tango Database is available >> "%LOG_FILE%"

REM Check if Starter is already running
echo [%date% %time%] Checking if Tango Starter is already running... >> "%LOG_FILE%"
tasklist /fi "imagename eq Starter.exe" | findstr "Starter.exe" >nul 2>&1
if %errorlevel% == 0 (
    echo [%date% %time%] Tango Starter appears to be already running >> "%LOG_FILE%"
    exit /b 0
)

REM Start the Tango Starter
echo [%date% %time%] Starting Tango Starter: %TANGO_ROOT%\bin\Starter.exe %HOSTNAME% >> "%LOG_FILE%"

REM Start Starter in normal window
start "Tango-Starter-%HOSTNAME%" "%TANGO_ROOT%\bin\Starter.exe" %HOSTNAME%

REM Wait a moment and verify startup
timeout /t 10 /nobreak >nul

REM Check if Starter started successfully
tasklist /fi "imagename eq Starter.exe" | findstr "Starter.exe" >nul 2>&1
if %errorlevel% == 0 (
    echo [%date% %time%] Tango Starter started successfully >> "%LOG_FILE%"
) else (
    echo [%date% %time%] WARNING: Tango Starter may not have started properly >> "%LOG_FILE%"
)

echo [%date% %time%] Tango Starter startup script completed >> "%LOG_FILE%"