@echo off
REM Passive DS_HealthMonitor wrapper for Astor
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME (
    echo ERROR: No instance name provided.
    exit /b 1
)
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse312"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_HealthMonitor [%INSTANCE_NAME%]" "DS_HealthMonitor" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\control\health_monitor" "DS_HealthMonitor.py" "DISABLE_ARCHIVE=1"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
