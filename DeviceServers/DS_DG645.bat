@echo off
REM DS_DG645 Wrapper for Astor
setlocal

set "INSTANCE_NAME=%~1"
if "%INSTANCE_NAME%"=="" set "INSTANCE_NAME=1_DG645"

if "%PYCONLYSE%"=="" set "PYCONLYSE=C:\dev\pyconlyse"
if "%PYCONLYSE_ENV%"=="" set "PYCONLYSE_ENV=pyconlyse39"
if "%ANACONDA%"=="" set "ANACONDA=C:\Users\elyse\miniconda3"

set "DEVICE_DIR=%PYCONLYSE%\DeviceServers\instruments\dg645"
set "DS_TITLE=DS_DG645 [%INSTANCE_NAME%]"

echo Starting DS_DG645 Device Server
echo Instance: %INSTANCE_NAME%
echo Directory: %DEVICE_DIR%

where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    wt -w 0 nt --title "%DS_TITLE%" -d "%DEVICE_DIR%" cmd /k "call "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && set PYTHONPATH=%PYCONLYSE% && echo Starting DS_DG645 device server... && python DS_DG645.py %INSTANCE_NAME%"
) else (
    start "%DS_TITLE%" cmd /k "cd /d "%DEVICE_DIR%" && "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV% && set PYTHONPATH=%PYCONLYSE% && echo Starting DS_DG645 device server... && python DS_DG645.py %INSTANCE_NAME%"
)

echo Device server start requested.
endlocal
