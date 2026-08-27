@echo off
REM DS_OWIS_Aggregator Wrapper for Astor
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME (
    echo ERROR: No instance name provided.
    exit /b 1
)
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_OWIS_Aggregator [%INSTANCE_NAME%]" "DS_OWIS_Aggregator" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\motion\owis" "DS_OWIS_Aggregator.py" "DISABLE_ARCHIVE=1"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
