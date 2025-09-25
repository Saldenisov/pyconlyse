@echo off
REM Start NETIO Client with Device Selection
REM Usage: start_netio.cmd [instance] [vis_type]
REM   instance: V0, VD2, all (or leave blank for dialog)
REM   vis_type: FULL, MIN (default: FULL)

echo === NETIO Client Launcher ===
echo Available instances: V0, VD2, all
echo Available vis_types: FULL, MIN
echo.

set INSTANCE=%1
set VIS_TYPE=%2

if "%INSTANCE%"=="" (
    echo No instance specified - will show selection dialog
) else (
    echo Instance: %INSTANCE%
)

if "%VIS_TYPE%"=="" (
    echo Vis Type: FULL (default)
) else (
    echo Vis Type: %VIS_TYPE%
)

echo.

REM Change to script directory
cd /d "%~dp0"

echo Attempting to launch with Poetry...
if "%VIS_TYPE%"=="" (
    poetry run python start_netio_client.py "%INSTANCE%"
) else (
    poetry run python start_netio_client.py "%INSTANCE%" "%VIS_TYPE%"
)

if %ERRORLEVEL% NEQ 0 (
    echo Poetry failed, trying system Python...
    if "%VIS_TYPE%"=="" (
        python start_netio_client.py "%INSTANCE%"
    ) else (
        python start_netio_client.py "%INSTANCE%" "%VIS_TYPE%"
    )
)

echo.
echo NETIO client launcher finished.
pause
