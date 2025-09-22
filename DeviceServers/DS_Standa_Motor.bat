@echo off
REM =====================================================
REM DS_Standa_Motor Wrapper for Astor
REM Launches the Python device server in a visible terminal
REM =====================================================

setlocal enabledelayedexpansion

if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable not set!
    exit /b 1
)
if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    exit /b 1
)
if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
)

set INSTANCE_NAME=%1
if "%INSTANCE_NAME%"=="" (
    echo ERROR: No instance name provided!
    echo Usage: DS_Standa_Motor.bat [instance_name]
    echo Example: DS_Standa_Motor.bat 1_MotorX_V0
    exit /b 1
)

echo =====================================================
echo Starting DS_Standa_Motor Device Server
echo Instance: %INSTANCE_NAME%
echo Environment: %PYCONLYSE_ENV%
echo =====================================================

echo To stop, press Ctrl+C in the tab or close the tab/window.

set DISABLE_ARCHIVE=1

set "DS_TITLE=DS_Standa_Motor [%INSTANCE_NAME%]"
where wt >nul 2>&1
if %errorlevel%==0 (
    wt -w 0 nt --title "%DS_TITLE%" -d "%PYCONLYSE%\DeviceServers\motion\standa" cmd /k "call "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && echo Starting DS_Standa_Motor device server... && python DS_Standa_Motor.py %INSTANCE_NAME%"
) else (
    echo Windows Terminal not found; starting in a separate window...
    start "%DS_TITLE%" cmd /k "cd /d "%PYCONLYSE%\DeviceServers\motion\standa" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && echo Starting DS_Standa_Motor device server... && python DS_Standa_Motor.py %INSTANCE_NAME%"
)
