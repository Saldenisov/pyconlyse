@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /c "cd C:\dev\pyconlyse\DeviceServers\OWIS & conda activate py38_32 & python DS_OWIS_PS90.py %arg1%"