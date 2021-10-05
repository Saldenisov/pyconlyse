@echo off
ECHO 'Starting OWIS DL'
for /L %%x in (1, 1, 4) do start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\OWIS & conda activate py38_32 & python DS_Owis_delay_line.py %%x"
