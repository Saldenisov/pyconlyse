@echo off
REM =====================================================
REM PYCONLYSE - Improved Tango Startup Script
REM This script starts the Tango infrastructure and lets
REM Astor manage DeviceServers automatically
REM =====================================================

setlocal enabledelayedexpansion

REM Set script directory for relative paths
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Logging function
set LOG_FILE=%SCRIPT_DIR%\tango_startup.log
echo [%date% %time%] Starting Tango infrastructure... >> "%LOG_FILE%"

REM Color codes for console output
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do (
  set "DEL=%%a"
)

call :ColorText 0a "Starting PYCONLYSE Tango Infrastructure..."
echo.

REM Validate environment variables
call :CheckEnvVar TANGO_ROOT
call :CheckEnvVar PYCONLYSE
call :CheckEnvVar ANACONDA
call :CheckEnvVar PYCONLYSE_ENV

REM Step 1: Start Tango Database
call :ColorText 0e "Step 1: Starting Tango Database..."
echo.
echo [%date% %time%] Starting Tango Database >> "%LOG_FILE%"
start "Tango-DB" cmd /c "%TANGO_ROOT%\bin\start-db.bat"

REM Wait for DB to initialize
timeout /t 5 /nobreak >nul

REM Step 2: Start Main Control Interface
call :ColorText 0e "Step 2: Starting Main Control Interface..."
echo.
echo [%date% %time%] Starting Main Control >> "%LOG_FILE%"
start "PyConlyse-Main" cmd /c "%PYCONLYSE%\bin\start_main_ctrl.cmd"

REM Wait for main control to initialize
timeout /t 8 /nobreak >nul

REM Step 3: Start Tango Starter (this will manage DeviceServers via Astor)
call :ColorText 0e "Step 3: Starting Tango Starter for everest..."
echo.
echo [%date% %time%] Starting Tango Starter >> "%LOG_FILE%"
start "Tango-Starter" cmd /c "%TANGO_ROOT%\bin\Starter.exe everest"

REM Wait for Starter to initialize
timeout /t 3 /nobreak >nul

REM Step 4: Start Astor (Device Server Manager)
call :ColorText 0e "Step 4: Starting Astor (Device Server Manager)..."
echo.
echo [%date% %time%] Starting Astor >> "%LOG_FILE%"
start "Tango-Astor" cmd /c "%TANGO_ROOT%\bin\start-astor.bat"

REM Step 5: Start Jive (optional GUI)
call :ColorText 0e "Step 5: Starting Jive GUI..."
echo.
echo [%date% %time%] Starting Jive >> "%LOG_FILE%"
start "Tango-Jive" cmd /c "%TANGO_ROOT%\bin\start-jive.bat"

REM Final message
timeout /t 3 /nobreak >nul
call :ColorText 0a "Tango infrastructure startup complete!"
echo.
echo.
call :ColorText 0f "Next steps:"
echo - Open Astor to configure and start DeviceServers
echo - Use main_ctrl GUI to manage device clients
echo - Check %LOG_FILE% for startup logs
echo.
echo [%date% %time%] Startup sequence completed >> "%LOG_FILE%"

pause
goto :eof

REM =====================================================
REM HELPER FUNCTIONS
REM =====================================================

:CheckEnvVar
if not defined %1 (
    call :ColorText 0c "ERROR: Environment variable %1 is not defined!"
    echo.
    echo [%date% %time%] ERROR: Missing environment variable %1 >> "%LOG_FILE%"
    pause
    exit /b 1
)
exit /b 0

:ColorText
<nul set /p "=%DEL%" > "%~2"
findstr /v /a:%1 /R "^$" "%~2" nul
del "%~2" > nul 2>&1
exit /b 0