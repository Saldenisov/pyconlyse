@echo off
ECHO 'Starting OWIS DL'
call C:/Users/Elyse/miniconda3/Scripts/activate.bat C:/Users/Elyse/miniconda3/
start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\OWIS & conda activate py38_32 & python DS_Owis_delay_line.py %%x"

