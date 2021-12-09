@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\bin & conda activate %PYCONLYSE_ENV% & python DS_STANDA_client.py %arg1%"
