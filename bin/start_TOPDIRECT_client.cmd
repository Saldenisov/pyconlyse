@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
set arg2=%2
start /min cmd /k "cd %PYCONLYSE%\bin & conda activate %PYCONLYSE_ENV% & python DS_TOPDIRECT_client.py  %arg1% %arg2%"
