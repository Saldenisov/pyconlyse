start cmd /c %PYCONLYSE%\bin\start_all_NETIO.cmd
start cmd /c %PYCONLYSE%\bin\start_all_STANDA.cmd
start cmd /c %PYCONLYSE%\bin\start_all_TOPDIRECT.cmd

start cmd /c %TANGO_ROOT%\bin\Starter.exe witchi
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-jive.bat
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-astor.bat
