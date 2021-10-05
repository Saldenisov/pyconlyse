@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start cmd /c "cd C:\dev\pyconlyse\bin\DeviceServers\OWIS & conda activate py38_32 & python DS_OWIS_PS90.py %arg1%"