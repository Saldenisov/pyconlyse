@echo off
ECHO 'Starting OWIS DL'
set list=1
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\OWIS & conda activate py38_32 & python DS_OWIS_PS90.py %%x"
timeout 1)

