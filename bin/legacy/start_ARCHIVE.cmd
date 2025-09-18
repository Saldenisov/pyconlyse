@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\ARCHIVE & conda activate %PYCONLYSE_ENV% & python DS_Archive.py %arg1%"
