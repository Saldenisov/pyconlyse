@echo off
setlocal EnableExtensions
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined TANGO_HOST set "TANGO_HOST=10.20.30.202:10000"
if not defined PYCONLYSE_PYTHON set "PYCONLYSE_PYTHON=python"
set "INSTANCE_NAME=%~1"
if "%INSTANCE_NAME%"=="" (
    echo ERROR: No instance name provided.
    exit /b 1
)
set "DISABLE_ARCHIVE=1"
set "DEVICE_DIR=%PYCONLYSE%\DeviceServers\control\laser_pointing"
set "DS_TITLE=DS_LaserPointing [%INSTANCE_NAME%]"
if not exist "%PYCONLYSE_PYTHON%" (
    echo Python environment not found: %PYCONLYSE_PYTHON%
    exit /b 1
)
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    wt -w PyconlyseTango new-tab --title "%DS_TITLE%" -d "%DEVICE_DIR%" cmd /k "set PYTHONPATH=%PYCONLYSE%&& echo Starting DS_LaserPointing...&& %PYCONLYSE_PYTHON% DS_LaserPointing.py %INSTANCE_NAME%"
    wt -w PyconlyseTango new-tab --title "Control - %DS_TITLE%" cmd /k "echo Control for %DS_TITLE%.&& echo Use Ctrl+C in the DS tab to stop it."
) else (
    start "%DS_TITLE%" cmd /k "cd /d "%DEVICE_DIR%"&& set PYTHONPATH=%PYCONLYSE%&& echo Starting DS_LaserPointing...&& %PYCONLYSE_PYTHON% DS_LaserPointing.py %INSTANCE_NAME%"
)
endlocal