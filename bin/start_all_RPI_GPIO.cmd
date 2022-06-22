@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting RPI GPIO controllers'
set list=1_RPI4_GPIO_V0 2_RPI3_GPIO_Controller
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\RPI_GPIO & conda activate %PYCONLYSE_ENV% & python DS_RPI_GPIO.py %%x"
)



