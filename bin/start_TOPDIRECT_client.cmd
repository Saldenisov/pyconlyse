@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /k "cd %PYCONLYSE%\bin & conda activate py38_32 & python DS_TOPDIRECT_client.py %arg1%"
