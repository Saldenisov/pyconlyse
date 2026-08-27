@echo off
REM DS_LaserPointing Wrapper for Astor.
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME (
    echo ERROR: No instance name provided.
    exit /b 1
)
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
set "DS_TITLE=DS_LaserPointing [%INSTANCE_NAME%]"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "%DS_TITLE%" "DS_LaserPointing" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\control\laser_pointing" "DS_LaserPointing.py" "DISABLE_ARCHIVE=1"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
