@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\TopDirect & conda activate %PYCONLYSE_ENV% & python DS_TopDirect_Motor.py %arg1%"