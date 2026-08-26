@echo off
REM =====================================================
REM DS_ANDOR_SPECTROGRAPH Wrapper for Astor
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
    echo Usage: DS_ANDOR_SPECTROGRAPH.bat [instance_name]
    echo Example: DS_ANDOR_SPECTROGRAPH.bat 1_ANDOR_SHAMROCK1
    pause
    exit /b 1
)

echo =====================================================
echo Starting DS_ANDOR_SPECTROGRAPH Device Server
echo Instance: %INSTANCE_NAME%
echo Environment: %PYCONLYSE_ENV%
echo =====================================================
echo.

set DISABLE_ARCHIVE=1
set "DS_TITLE=DS_ANDOR_SPECTROGRAPH [%INSTANCE_NAME%]"
where wt >nul 2>&1
if %errorlevel%==0 (
    wt -w PyconlyseTango new-tab --title "%DS_TITLE%" -d "%PYCONLYSE%\DeviceServers\spectrographs\andor" cmd /k "call "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && set PYTHONPATH=%PYCONLYSE% && echo Starting DS_ANDOR_SPECTROGRAPH device server... && %PYCONLYSE_PYTHON% DS_ANDOR_SPECTROGRAPH.py %INSTANCE_NAME%"
) else (
    echo Windows Terminal not found; starting in a separate window...
    start "%DS_TITLE%" cmd /k "cd /d "%PYCONLYSE%\DeviceServers\spectrographs\andor" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && set PYTHONPATH=%PYCONLYSE% && echo Starting DS_ANDOR_SPECTROGRAPH device server... && %PYCONLYSE_PYTHON% DS_ANDOR_SPECTROGRAPH.py %INSTANCE_NAME%"
)

echo Device server started in terminal tab/window!
echo.
