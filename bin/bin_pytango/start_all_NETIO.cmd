@echo off
ECHO 'Starting STANDA axes'
for /l %%x in (1, 1, 4) do (
start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\NETIO & conda activate py38_32 & python DS_Netio_pdu.py %%x"
)
