@echo off
setlocal EnableExtensions
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_PYTHON set "PYCONLYSE_PYTHON=python"
set "DEVICE_DIR=%PYCONLYSE%\DeviceServers\data\ml"
set "DS_TITLE=DS_ML_Stability"
if not exist "%PYCONLYSE_PYTHON%" (
    echo Python environment not found: %PYCONLYSE_PYTHON%
    exit /b 1
)
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    wt -w PyconlyseTango new-tab --title "%DS_TITLE%" -d "%DEVICE_DIR%" cmd /k "set PYTHONPATH=%PYCONLYSE%&& echo Starting DS_ML_Stability...&& %PYCONLYSE_PYTHON% DS_ML_Stability.py DS_ML_Stability/1_UV1 -v4"
) else (
    start "%DS_TITLE%" cmd /k "cd /d "%DEVICE_DIR%"&& set PYTHONPATH=%PYCONLYSE%&& echo Starting DS_ML_Stability...&& %PYCONLYSE_PYTHON% DS_ML_Stability.py DS_ML_Stability/1_UV1 -v4"
)
endlocal