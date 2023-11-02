@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting BASLER cameras'
set list=1_Cam1_V0 2_Cam2_V0 3_Cam3_V0
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\BASLER & conda activate %PYCONLYSE_ENV% & python DS_Basler_camera.py %%x"
timeout 3
)



