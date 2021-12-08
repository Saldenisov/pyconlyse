@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /k cd %PYCONLYSE%\DeviceServers\STANDA & conda activate py38_32 & python DS_Standa_Motor.py %arg1%
