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

echo A separate Control window will open. Type STOP there to terminate this DS.

set DISABLE_ARCHIVE=1

set "DS_TITLE=DS_Standa_Motor [%INSTANCE_NAME%]"
start "%DS_TITLE%" cmd /k "cd /d "%PYCONLYSE%\DeviceServers\motion\standa" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && echo Starting DS_Standa_Motor device server... && python DS_Standa_Motor.py %INSTANCE_NAME%"

REM Open control window to allow typing STOP to close DS
start "Control - %DS_TITLE%" cmd /k "echo Control for %DS_TITLE%. & echo Type STOP to terminate this device server, or EXIT to close this control. & :control & set /p USER_INPUT=Command (STOP/EXIT):  & if /I "%USER_INPUT%"=="STOP" (taskkill /FI "WINDOWTITLE eq %DS_TITLE%" /T & echo Sent stop to %DS_TITLE%.) & if /I "%USER_INPUT%"=="EXIT" exit & goto control"
