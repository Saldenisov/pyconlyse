@echo off
REM Start NETIO Client using Conda Environment (Fixed DLL Issues)
REM Usage: start_netio_conda.cmd [instance] [vis_type]
REM   instance: V0, VD2, all (or leave blank for dialog)
REM   vis_type: FULL, MIN (default: FULL)

echo === NETIO Client Launcher (Conda) ===
echo Available instances: V0, VD2, all
echo Available vis_types: FULL, MIN
echo.
echo Using conda environment: pyconlyse39
echo Python: C:\Users\denisov\miniconda3\envs\pyconlyse39\python.exe
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

echo Starting NETIO client...
if "%VIS_TYPE%"=="" (
    "C:\Users\denisov\miniconda3\envs\pyconlyse39\python.exe" start_netio_client.py "%INSTANCE%"
) else (
    "C:\Users\denisov\miniconda3\envs\pyconlyse39\python.exe" start_netio_client.py "%INSTANCE%" "%VIS_TYPE%"
)

echo.
echo NETIO client finished.
pause