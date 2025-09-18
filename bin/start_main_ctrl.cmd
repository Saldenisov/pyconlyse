@echo off
REM =====================================================
REM PYCONLYSE - Main Control Interface Startup v2.0
REM Starts the refactored main control interface
REM =====================================================

call %ANACONDA%/Scripts/activate.bat

REM Validate environment
if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    pause
    exit /b 1
)

REM Set default conda environment if not specified
if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
    echo INFO: Using default conda environment: pyconlyse39
)

ECHO Starting PYCONLYSE Control Center v2.0...
timeout 2

REM Start the main control interface
start /min cmd /c "cd %PYCONLYSE%\bin & conda activate %PYCONLYSE_ENV% & python main_ctrl.py"

echo Main Control Interface started successfully!
echo Check the application window for Tango startup controls.