@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO Starting TopDirect axes
set list=1_Lense260 2_DL_SC1
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\TopDirect & conda activate %PYCONLYSE_ENV% & python DS_TopDirect_Motor.py %%x"
timeout 1)
