@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /c cd %PYCONLYSE%\DeviceServers\TopDirect & conda activate py38_32 & python DS_TopDirect_Motor.py %arg1%