@echo off
ECHO 'Starting STANDA axes'
call C:/Users/Elyse/miniconda3/Scripts/activate.bat C:/Users/Elyse/miniconda3/
for /l %%x in (1, 1, 25) do (
ECHO 'STARTING STANDA AXIS %%x'
start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\STANDA & conda activate py38_32 & python DS_Standa_Motor.py %%x"
timeout 1)
