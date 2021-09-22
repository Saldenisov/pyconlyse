@echo off
ECHO 'Starting STANDA axes'
for /l %%x in (1, 1, 25) do start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\STANDA & conda activate py38_32 & python DS_Standa_Motor.py %%x"
