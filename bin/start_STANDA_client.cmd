@echo off
call %ANACONDA%/Scripts/activate.bat %ANACONDA%
ECHO 'Starting STANDA client'
timeout 1
start cmd /c "cd C:\dev\pyconlyse\bin & conda activate py38_32 & python DS_STANDA_client.py alignment 4"

