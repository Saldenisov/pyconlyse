@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\STRESING_IR & conda activate %PYCONLYSE_ENV% & python DS_STRESING_IR.py %arg1%"
