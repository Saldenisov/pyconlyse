@echo off
setlocal

set "INSTANCE_NAME=%~1"
if "%INSTANCE_NAME%"=="" set "INSTANCE_NAME=1_hamamatsu_streak_main"

if "%PYCONLYSE%"=="" set "PYCONLYSE=C:\dev\pyconlyse"
if "%PYCONLYSE_ENV%"=="" set "PYCONLYSE_ENV=pyconlyse39"
if "%TANGO_HOST%"=="" set "TANGO_HOST=10.20.30.202:10000"

set "PYTHON_EXE=C:\Users\elyse\.conda\envs\%PYCONLYSE_ENV%\python.exe"
set "DEVICE_DIR=%PYCONLYSE%\DeviceServers\cameras\hamamatsu_streak"

if not exist "%PYTHON_EXE%" (
    echo Python environment not found: %PYTHON_EXE%
    exit /b 1
)

cd /d "%DEVICE_DIR%"
set "PYTHONPATH=%PYCONLYSE%"
"%PYTHON_EXE%" DS_HAMAMATSU_STREAK.py %INSTANCE_NAME%
endlocal
