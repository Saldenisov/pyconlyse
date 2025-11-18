@echo off
echo =======================================================
echo Restarting iTest PSU Device Server with Enhanced Logging
echo =======================================================

REM Kill existing device server
echo Killing existing device server...
python -c "import tango; tango.Database().kill_server('DS_itest_psu/1_iTest')" 2>nul

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start device server in new window with extensive logging
echo Starting device server with enhanced logging...
echo Check the new console window for detailed connection logs

start "iTest PSU Device Server" cmd /k "cd /d C:\dev\pyconlyse\DeviceServers\power\iTest & conda activate pyconlyse39 & python DS_itest_psu.py 1_iTest"

echo.
echo Device server restart initiated!
echo - Check the new console window for connection logs
echo - The server should show detailed SCPI connection attempts
echo - Watch for '[ITestSCPI]' messages to see connection progress
echo.
pause