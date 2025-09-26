start cmd /c %PYCONLYSE%\bin\start_all_STANDA.cmd
timeout 20
start /min cmd /c %TANGO_ROOT%\bin\start-astor.bat
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-jive.bat
timeout 60
start cmd /c %TANGO_ROOT%\bin\Starter.exe elysium2
