@echo off
REM Batch file to start Elysium2 starter using TANGO_ROOT environment variable
REM Created for Windows startup

REM Check if TANGO_ROOT is set
if not defined TANGO_ROOT (
    echo ERROR: TANGO_ROOT environment variable is not set!
    echo Please set TANGO_ROOT to your Tango installation directory.
    pause
    exit /b 1
)

REM Display TANGO_ROOT for verification
echo Starting Elysium2 with TANGO_ROOT: %TANGO_ROOT%

REM Ensure Python can import DeviceServers (add project root to PYTHONPATH)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\..\.."
set "PYCONLYSE_ROOT=%CD%"
popd

if defined PYTHONPATH (
    set "PYTHONPATH=%PYCONLYSE_ROOT%;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%PYCONLYSE_ROOT%"
)

echo Using PYTHONPATH: %PYTHONPATH%

REM Check if Starter.exe exists in TANGO_ROOT\tango\bin
set "STARTER_PATH=%TANGO_ROOT%\tango\bin\Starter.exe"

if not exist "%STARTER_PATH%" (
    echo ERROR: Could not find Starter.exe at: %STARTER_PATH%
    echo Please check your Tango installation path.
    pause
    exit /b 1
)

REM Start Elysium2 using Starter.exe
echo Starting Elysium2 using: "%STARTER_PATH%" elysium2
start "" "%STARTER_PATH%" elysium2

echo Elysium2 started successfully.