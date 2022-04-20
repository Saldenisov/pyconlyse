@echo off
call %ANACONDA%/Scripts/activate.bat
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%_old\bin & conda activate pyconlyse_old & python Treatment.py %arg1%"
