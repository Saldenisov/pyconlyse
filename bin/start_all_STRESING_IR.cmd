@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting Stresing IR cameras'
set list=1_IR_det
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\STRESING_IR & conda activate %PYCONLYSE_ENV% & python DS_STRESING_IR.py %%x"
)

