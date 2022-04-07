@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting RPI GPIO controllers'
set list=1_RPI_GPIO_V0
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\RPI_GPIO & conda activate %PYCONLYSE_ENV% & python DS_RPI_GPIO.py %%x"
)



