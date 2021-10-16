@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /k "cd C:\dev\pyconlyse\DeviceServers\NETIO & conda activate py38_32 & python DS_Netio_pdu.py %arg1%"
