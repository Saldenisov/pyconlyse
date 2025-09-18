@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting NETIO axes'
set list=1_Cam1 2_Cam2 3_Cam3
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\LaserPointing & conda activate %PYCONLYSE_ENV% & python DS_LaserPointing.py %%x"
)
