@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting STANDA axes'
timeout 1
for /l %%x in (1, 1, 25) do (
start cmd /c "cd C:\dev\pyconlyse\DeviceServers\STANDA & conda activate py38_32 & python DS_Standa_Motor.py %%x"
timeout 2)
