@echo off
REM =====================================================
REM DS_Basler_camera Wrapper for Astor
REM This batch file allows Astor to launch the Python device server
REM =====================================================

setlocal enabledelayedexpansion

REM Validate environment variables
if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable not set!
    echo Please set ANACONDA to your Anaconda installation directory
    pause
    exit /b 1
)

if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    echo Please set PYCONLYSE to your PyConlyse project directory
    pause
    exit /b 1
)

if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
    echo INFO: Using default conda environment: pyconlyse39
)

REM Get the device server instance name from command line argument
set INSTANCE_NAME=%1
if "%INSTANCE_NAME%"=="" (
    echo ERROR: No instance name provided!
    echo Usage: DS_Basler_camera.bat [instance_name]
    echo Example: DS_Basler_camera.bat 1_Cam1_V0
    pause
    exit /b 1
)

echo =====================================================
echo Starting DS_Basler_camera Device Server
echo Instance: %INSTANCE_NAME%
echo Environment: %PYCONLYSE_ENV%
echo =====================================================
echo.

REM Astor starts devices sequentially, so no startup delays needed
echo.
echo Starting in new visible terminal window...
echo Terminal title: DS_Basler_camera [%INSTANCE_NAME%]
echo.

REM Start the device server in a new visible terminal window
start "DS_Basler_camera [%INSTANCE_NAME%]" cmd /k "cd /d "%PYCONLYSE%\DeviceServers\cameras\basler" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && echo Starting DS_Basler_camera device server... && python DS_Basler_camera.py %INSTANCE_NAME%"

echo Device server started in separate terminal window!
echo You can monitor and control it from the terminal titled:
echo "DS_Basler_camera [%INSTANCE_NAME%]"
echo.
echo To close the device server:
echo - Use Ctrl+C in the device server terminal, or
echo - Close the terminal window, or
echo - Use Astor to manage the device server
echo.
