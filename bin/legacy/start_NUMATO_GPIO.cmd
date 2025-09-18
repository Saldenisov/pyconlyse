@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\NUMATO & conda activate %PYCONLYSE_ENV% & python DS_NUMATO_GPIO.py %arg1%"
