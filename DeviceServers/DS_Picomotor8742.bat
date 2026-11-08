@echo off
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME (
    echo ERROR: No instance name provided.
    exit /b 1
)
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse312"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_Picomotor8742 [%INSTANCE_NAME%]" "DS_Picomotor8742" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\motion\picomotor" "DS_Picomotor8742.py" "DISABLE_ARCHIVE=1"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
