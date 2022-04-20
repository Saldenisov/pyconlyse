@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO Starting ARCHIVES
set list=1_Archive
timeout 1
for %%x in (%list%) do (
start /min cmd /k "cd %PYCONLYSE%\DeviceServers\ARCHIVE & conda activate %PYCONLYSE_ENV% & python DS_Archive.py %%x"
timeout 1)
