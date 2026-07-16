@echo off
REM =====================================================
REM DS_DAQmx Wrapper for Astor
REM This batch file allows Astor to launch the Python device server
REM =====================================================

setlocal enabledelayedexpansion

if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable not set!
    pause
    exit /b 1
)

if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    pause
    exit /b 1
)

if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
    echo INFO: Using default conda environment: pyconlyse39
)

set INSTANCE_NAME=%1
if "%INSTANCE_NAME%"=="" (
    echo ERROR: No instance name provided!
    echo Usage: DS_DAQmx.bat [instance_name]
    echo Example: DS_DAQmx.bat 1_DAQMX_1
    pause
    exit /b 1
)

set "DS_TITLE=DS_DAQmx [%INSTANCE_NAME%]"
where wt >nul 2>&1
if %errorlevel%==0 (
    wt -w 0 nt --title "%DS_TITLE%" -d "%PYCONLYSE%\DeviceServers\control\daqmx" cmd /k "call "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && set DISABLE_ARCHIVE=1 && set PYTHONPATH=%PYCONLYSE% && echo Starting DS_DAQmx device server... && python DS_DAQmx.py %INSTANCE_NAME%"
) else (
    start "%DS_TITLE%" cmd /k "cd /d "%PYCONLYSE%\DeviceServers\control\daqmx" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && set DISABLE_ARCHIVE=1 && set PYTHONPATH=%PYCONLYSE% && echo Starting DS_DAQmx device server... && python DS_DAQmx.py %INSTANCE_NAME%"
)
