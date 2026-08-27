@echo off
REM DS_DG645 Wrapper for Astor
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME set "INSTANCE_NAME=1_DG645"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_DG645 [%INSTANCE_NAME%]" "DS_DG645" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\instruments\dg645" "DS_DG645.py" ""
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
