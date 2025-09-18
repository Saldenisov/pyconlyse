start cmd /c %PYCONLYSE%\bin\start_all_NETIO.cmd
start cmd /c %PYCONLYSE%\bin\start_all_STANDA.cmd
start cmd /c %PYCONLYSE%\bin\start_all_TOPDIRECT.cmd
timeout 20
start /min cmd /c %TANGO_ROOT%\bin\start-astor.bat
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-jive.bat
timeout 10
start cmd /c %TANGO_ROOT%\bin\Starter.exe elysium
