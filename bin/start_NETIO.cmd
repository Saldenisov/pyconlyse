@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\NETIO & conda activate %PYCONLYSE_ENV% & python DS_Netio_pdu.py %arg1%"
