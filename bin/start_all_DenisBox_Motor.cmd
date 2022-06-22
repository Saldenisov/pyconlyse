@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO Starting DenisBox_Motor
set list=1_Mirror_VD2
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\TopDirect & conda activate %PYCONLYSE_ENV% & python DS_DenisBox_Motor.py %%x"
timeout 1)
