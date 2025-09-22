@echo off
REM =====================================================
REM DS_OWIS_PS90 Wrapper for Astor
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
    echo Usage: DS_OWIS_PS90.bat [instance_name]
    echo Example: DS_OWIS_PS90.bat 1
    pause
    exit /b 1
)

echo =====================================================
echo Starting DS_OWIS_PS90 Device Server
echo Instance: %INSTANCE_NAME%
echo Environment: %PYCONLYSE_ENV%
echo =====================================================
echo.
echo Attempting to open in Windows Terminal tab (if available)...

echo.
REM Disable archive for this process (inherited by child tab/window)
set DISABLE_ARCHIVE=1

REM Start the device server in a Windows Terminal tab if possible; otherwise fallback to a new window
set "DS_TITLE=DS_OWIS_PS90 [%INSTANCE_NAME%]"
where wt >nul 2>&1
if %errorlevel%==0 (
    wt -w 0 nt --title "%DS_TITLE%" -d "%PYCONLYSE%\DeviceServers\motion\owis" cmd /k "call "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && echo Starting DS_OWIS_PS90 device server... && python DS_OWIS_PS90.py %INSTANCE_NAME%"
) else (
    echo Windows Terminal not found; starting in a separate window...
    start "%DS_TITLE%" cmd /k "cd /d "%PYCONLYSE%\DeviceServers\motion\owis" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && echo Starting DS_OWIS_PS90 device server... && python DS_OWIS_PS90.py %INSTANCE_NAME%"
)

echo Device server started in terminal tab/window!
echo.
echo To close the device server:
echo - Use Ctrl+C in that tab, or close the tab/window, or
echo - Use Astor to manage the device server
echo.