@echo off
call %ANACONDA%/Scripts/activate.bat
ECHO 'Starting Main Control'
timeout 2
start /min cmd /c cd %PYCONLYSE%\bin & conda activate py38_32 & python main_ctrl.py