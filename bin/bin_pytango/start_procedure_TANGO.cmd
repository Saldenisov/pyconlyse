@echo off
call C:/Users/Elyse/miniconda3/Scripts/activate.bat C:/Users/Elyse/miniconda3/
ECHO 'Starting TANGO DB'
start cmd /c "C:\dev\tango_root\tango\bin\start-db.bat"
timeout 2
ECHO 'Starting ASTOR'
start cmd /cC:\dev\tango_root\tango\bin\start-astor.bat
ECHO 'Starting JIVE'
start cmd /cC:\dev\tango_root\tango\bin\start-jive.bat
timeout 1
start cmd /c "C:\dev\pyconlyse\bin\bin_pytango\start_all_NETIO"
timeout 2
start cmd /c "C:\dev\pyconlyse\bin\bin_pytango\start_all_STANDA"
timeout 1
start cmd /ccmd /c "C:\dev\pyconlyse\bin\bin_pytango\start_all_OWIS"

