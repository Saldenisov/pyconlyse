@echo off
REM DS_HAMAMATSU_STREAK Wrapper for Astor.
setlocal
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME set "INSTANCE_NAME=1_hamamatsu_streak_main"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
if not defined TANGO_HOST set "TANGO_HOST=10.20.30.202:10000"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_HAMAMATSU_STREAK [%INSTANCE_NAME%]" "DS_HAMAMATSU_STREAK" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\cameras\hamamatsu_streak" "DS_HAMAMATSU_STREAK.py" ""
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
