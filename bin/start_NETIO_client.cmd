@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
set arg1=%1
start /min cmd /c "cd %PYCONLYSE%\bin & conda activate py38_32 & python DS_NETIO_client.py %arg1%"
