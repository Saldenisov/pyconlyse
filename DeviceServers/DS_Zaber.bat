@echo off
REM VD2 Zaber stage wrapper for Astor on Elysium2
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME set "INSTANCE_NAME=1_Zaber"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_Zaber [%INSTANCE_NAME%]" "DS_Zaber" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\motion\zaber" "DS_Zaber.py" ""
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
