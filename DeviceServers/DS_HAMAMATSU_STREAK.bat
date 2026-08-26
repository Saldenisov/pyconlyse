@echo off
setlocal EnableExtensions
set "INSTANCE_NAME=%~1"
if "%INSTANCE_NAME%"=="" set "INSTANCE_NAME=1_hamamatsu_streak_main"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined TANGO_HOST set "TANGO_HOST=10.20.30.202:10000"
if not defined PYCONLYSE_PYTHON set "PYCONLYSE_PYTHON=python"
set "DEVICE_DIR=%PYCONLYSE%\DeviceServers\cameras\hamamatsu_streak"
set "DS_TITLE=DS_HAMAMATSU_STREAK [%INSTANCE_NAME%]"
if not exist "%PYCONLYSE_PYTHON%" (
    echo Python environment not found: %PYCONLYSE_PYTHON%
    exit /b 1
)
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    wt -w PyconlyseTango new-tab --title "%DS_TITLE%" -d "%DEVICE_DIR%" cmd /k "set PYTHONPATH=%PYCONLYSE%&& echo Starting DS_HAMAMATSU_STREAK...&& %PYCONLYSE_PYTHON% DS_HAMAMATSU_STREAK.py %INSTANCE_NAME%"
) else (
    start "%DS_TITLE%" cmd /k "cd /d "%DEVICE_DIR%"&& set PYTHONPATH=%PYCONLYSE%&& echo Starting DS_HAMAMATSU_STREAK...&& %PYCONLYSE_PYTHON% DS_HAMAMATSU_STREAK.py %INSTANCE_NAME%"
)
endlocal