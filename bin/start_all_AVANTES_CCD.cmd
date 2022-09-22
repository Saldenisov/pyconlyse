@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting AVANTES spectrographs'
set list=1_AVANTES_CCD1 2_AVANTES_CCD2
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\AVANTES_CCD & conda activate %PYCONLYSE_ENV% & python DS_AVANTES_CCD.py %%x"
)



