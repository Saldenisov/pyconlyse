@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\ANDOR_CCD & conda activate %PYCONLYSE_ENV% & python DS_ANDOR_CCD.py %arg1%"
