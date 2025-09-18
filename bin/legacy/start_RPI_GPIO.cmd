@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\RPI_GPIO & conda activate %PYCONLYSE_ENV% & python DS_RPI_GPIO.py %arg1%"
