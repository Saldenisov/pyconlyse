@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting NETIO axes'
set list=1_V0 2_VD2 3_SD1 4_SD2 5_ELYSE
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\NETIO & conda activate py38_32 & python DS_Netio_pdu.py %%x"
)



