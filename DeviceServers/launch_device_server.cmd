@echo off
REM Open a Tango server in the existing Windows Terminal window/tab topology.
REM Arguments: title, server name, instance, directory, script, environment, mode.

setlocal EnableExtensions
set "DS_TITLE=%~1"
set "SERVER_NAME=%~2"
set "INSTANCE_NAME=%~3"
set "DEVICE_DIR=%~4"
set "DEVICE_SCRIPT=%~5"
set "SERVER_ENVIRONMENT=%~6"
set "SERVER_EXTRA_ARGUMENT=%~7"
set "LAUNCH_MODE=%~8"

if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_WT_WINDOW set "PYCONLYSE_WT_WINDOW=PyconlyseTango"
if not defined PYCONLYSE_LOG_DIR set "PYCONLYSE_LOG_DIR=C:\temp\ds.log"
set "LOGGED_LAUNCHER=%PYCONLYSE%\DeviceServers\run_logged_server.cmd"
set "TAIL_LAUNCHER=%PYCONLYSE%\DeviceServers\tail_device_server_log.cmd"
if not exist "%LOGGED_LAUNCHER%" (
    echo ERROR: Shared device-server launcher missing: %LOGGED_LAUNCHER%
    exit /b 2
)
if not exist "%TAIL_LAUNCHER%" (
    echo ERROR: Device-server log tailer missing: %TAIL_LAUNCHER%
    exit /b 2
)

REM Start Python before requesting any terminal UI. Windows Terminal can take
REM several seconds to create a tab in a background session; that must not
REM delay Tango registration.
if not exist "%PYCONLYSE_LOG_DIR%" mkdir "%PYCONLYSE_LOG_DIR%"
set "SERVER_LOG_FILE=%PYCONLYSE_LOG_DIR%\%SERVER_NAME%_%INSTANCE_NAME%.log"
echo ==== %date% %time% dispatching %SERVER_NAME%/%INSTANCE_NAME% ==== >> "%SERVER_LOG_FILE%"
start "" /b cmd.exe /d /c call "%LOGGED_LAUNCHER%" "%SERVER_NAME%" "%INSTANCE_NAME%" "%DEVICE_DIR%" "%DEVICE_SCRIPT%" "%SERVER_ENVIRONMENT%" "%SERVER_EXTRA_ARGUMENT%"
if errorlevel 1 exit /b %errorlevel%

if /I "%LAUNCH_MODE%"=="window" goto window
where wt >nul 2>&1
if not errorlevel 1 (
    start "" /b wt -w "%PYCONLYSE_WT_WINDOW%" nt --title "%DS_TITLE%" -d "%DEVICE_DIR%" cmd /k call "%TAIL_LAUNCHER%" "%SERVER_LOG_FILE%"
    exit /b %errorlevel%
)

:window
start "%DS_TITLE%" cmd /k call "%TAIL_LAUNCHER%" "%SERVER_LOG_FILE%"
exit /b %errorlevel%
