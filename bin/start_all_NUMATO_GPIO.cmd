@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting NUMATO GPIO controllers'
set list=1_Numato1
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\NUMATO & conda activate %PYCONLYSE_ENV% & python DS_NUMATO_GPIO.py %%x"
)



