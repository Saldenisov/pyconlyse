@echo off
REM =====================================================
REM TANGO DATABASE - Windows Startup Service
REM This script starts Tango Database on Windows boot
REM Place in Windows Startup folder or use Task Scheduler
REM =====================================================

setlocal enabledelayedexpansion

REM Set script directory
set SCRIPT_DIR=%~dp0
set LOG_FILE=%SCRIPT_DIR%tango_db_startup.log

REM Log startup attempt
echo [%date% %time%] Starting Tango Database service... >> "%LOG_FILE%"

REM Check if TANGO_ROOT is set
if not defined TANGO_ROOT (
    echo [%date% %time%] ERROR: TANGO_ROOT environment variable not set! >> "%LOG_FILE%"
    exit /b 1
)

REM Check if database is already running by trying to connect
echo [%date% %time%] Checking if Tango Database is already running... >> "%LOG_FILE%"

REM Try to connect to database (simple test)
netstat -an | findstr ":10000" >nul 2>&1
if %errorlevel% == 0 (
    echo [%date% %time%] Tango Database appears to be already running on port 10000 >> "%LOG_FILE%"
    exit /b 0
)

REM Start the Tango Database
echo [%date% %time%] Starting Tango Database from: %TANGO_ROOT%\bin\start-db.bat >> "%LOG_FILE%"

REM Start database in normal window (keep terminal open)
start "Tango-DB-Service" cmd /k "%TANGO_ROOT%\bin\start-db.bat"

REM Wait a moment and verify startup
timeout /t 10 /nobreak >nul

REM Check if database started successfully
netstat -an | findstr ":10000" >nul 2>&1
if %errorlevel% == 0 (
    echo [%date% %time%] Tango Database started successfully >> "%LOG_FILE%"
) else (
    echo [%date% %time%] WARNING: Tango Database may not have started properly >> "%LOG_FILE%"
)

echo [%date% %time%] Tango Database startup script completed >> "%LOG_FILE%"