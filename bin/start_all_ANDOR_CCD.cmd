@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting ANDOR cameras'
set list=1_ANDOR_CCD1
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\ANDOR_CCD & conda activate %PYCONLYSE_ENV% & python DS_ANDOR_CCD.py %%x"
)



