@echo off
call %ANACONDA%/Scripts/activate.bat
ECHO 'Starting Main Control'
timeout 2
start /min cmd /k "cd %PYCONLYSE%\bin & conda activate %PYCONLYSE_ENV% & python main_ctrl.py"