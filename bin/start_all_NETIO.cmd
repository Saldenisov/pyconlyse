@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting NETIO axes'
timeout 5
for /l %%x in (1, 1, 4) do (
start cmd /c "cd C:\dev\pyconlyse\DeviceServers\NETIO & conda activate py38_32 & python DS_Netio_pdu.py %%x"
)
