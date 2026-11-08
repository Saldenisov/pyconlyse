@echo off
REM Separate XP command bridge. Starting this process never initializes NI cards.
setlocal EnableExtensions
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME set "INSTANCE_NAME=everest"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined TANGO_HOST set "TANGO_HOST=10.20.30.202:10000"
call "%~dp0run_logged_server.cmd" "DS_AcqTelemetryControl" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\control\elyse_acq" "DS_AcqTelemetryControl.py" "" ""
set "EXIT_CODE=%ERRORLEVEL%"
REM No automatic process restart, XP lifecycle call or command replay.
endlocal & exit /b %EXIT_CODE%
