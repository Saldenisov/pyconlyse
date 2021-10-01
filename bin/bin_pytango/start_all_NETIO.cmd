@echo off
ECHO 'Starting NETIO pdus'
call C:/Users/Elyse/miniconda3/Scripts/activate.bat C:/Users/Elyse/miniconda3/
for /l %%x in (1, 1, 4) do (
ECHO 'STARTING NETIO AXIS %%x'
start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\NETIO & conda activate py38_32 & python DS_Netio_pdu.py %%x"
timeout 1
)