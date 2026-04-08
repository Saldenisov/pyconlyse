@echo off
REM DS_ML_Stability - Tango Device Server for ML Stability Prediction
REM This batch file starts the ML stability prediction device server

echo Starting DS_ML_Stability Tango Device Server...

REM Set the Python path to ensure all modules can be found
set PYTHONPATH=%PYTHONPATH%;C:\dev\pyconlyse

REM Change to the device server directory
cd /d "C:\dev\pyconlyse\DeviceServers\data\ml"

REM Start the device server
python DS_ML_Stability.py DS_ML_Stability/1_UV1 -v4

REM Pause to see any error messages
if errorlevel 1 (
    echo.
    echo ERROR: Device server failed to start!
    echo Check the logs for more information.
    echo.
    pause
)