@echo off
REM DS_ML_Stability Wrapper for Astor.
setlocal
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
call "%PYCONLYSE%\DeviceServers\launch_device_server.cmd" "DS_ML_Stability [DS_ML_Stability/1_UV1]" "DS_ML_Stability" "DS_ML_Stability/1_UV1" "%PYCONLYSE%\DeviceServers\data\ml" "DS_ML_Stability.py" "" "-v4"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
