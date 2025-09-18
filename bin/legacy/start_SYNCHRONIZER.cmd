@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\SYNC & conda activate %PYCONLYSE_ENV% & python DS_SYNCHRONIZER.py %arg1%"
