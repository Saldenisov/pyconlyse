@echo off
ECHO 'Starting OWIS DL'
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set list=1
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\OWIS & conda activate %PYCONLYSE_ENV% & python DS_OWIS_PS90.py %%x"
timeout 1)

