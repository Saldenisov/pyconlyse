@echo off
REM =====================================================
REM PYCONLYSE - Main Control with Auto Tango Startup
REM This starts main_ctrl.py which will automatically 
REM start Tango Database and Starter on Windows
REM =====================================================

setlocal enabledelayedexpansion

REM Set script directory
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

echo =====================================================
echo PYCONLYSE Control Center - Auto Tango Startup
echo =====================================================
echo.

REM Validate environment variables
if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    echo Please set PYCONLYSE to your PyConlyse project directory
    pause
    exit /b 1
)

if not defined TANGO_ROOT (
    echo ERROR: TANGO_ROOT environment variable not set!
    echo Please set TANGO_ROOT to your Tango installation directory
    pause
    exit /b 1
)

if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable not set!
    echo Please set ANACONDA to your Anaconda installation directory
    pause
    exit /b 1
)

REM Set default conda environment if not specified
if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
    echo INFO: Using default conda environment: pyconlyse39
)

echo Starting PYCONLYSE Control Center with Auto-Tango Startup...
echo.
echo Components that will auto-start:
echo   - Tango Database
echo   - Tango Starter (everest)
echo   - Astor DeviceServer Manager
echo.

REM Activate conda environment and start main_ctrl
call %ANACONDA%\Scripts\activate.bat %PYCONLYSE_ENV%

if errorlevel 1 (
    echo ERROR: Failed to activate conda environment '%PYCONLYSE_ENV%'
    echo Please check your conda installation and environment name
    pause
    exit /b 1
)

echo Environment activated: %PYCONLYSE_ENV%
echo Starting main control interface...
echo.

REM Change to bin directory and start main_ctrl.py
cd /d "%SCRIPT_DIR%"
python main_ctrl.py

echo.
echo Main Control Interface has closed.
pause