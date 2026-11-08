@echo off
REM Persistent receive-only Tango server for Starter/Astor. No timed soak runner.
setlocal EnableExtensions
set "INSTANCE_NAME=%~1"
if not defined INSTANCE_NAME set "INSTANCE_NAME=everest"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
REM Telemetry-only PostgreSQL release; XP Acquisition/card ownership is unchanged.
set "PYCONLYSE=F:\ELYSE_Telemetry_Server\postgres_v3"
set "PYCONLYSE_LOG_DIR=F:\ELYSE_PostgreSQL\logs\device_server"
:run
call "%~dp0run_logged_server.cmd" "DS_AcqTelemetry" "%INSTANCE_NAME%" "%PYCONLYSE%\DeviceServers\control\elyse_acq" "DS_AcqTelemetry.py" "" ""
set "EXIT_CODE=%ERRORLEVEL%"
REM A normal Tango/Astor shutdown exits zero and must stay stopped.
REM Retry only unexpected process failure; do not alter Starter-wide restart policy.
if "%EXIT_CODE%"=="0" goto done
timeout /t 5 /nobreak >nul
goto run
:done
endlocal & exit /b %EXIT_CODE%
