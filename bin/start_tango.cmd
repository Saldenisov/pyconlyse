start /min cmd /c %TANGO_ROOT%\bin\start-db.bat
start /min cmd /c %PYCONLYSE%\bin\start_main_ctrl.cmd
timeout 10
start cmd /c %PYCONLYSE%\bin\start_all_NETIO.cmd
start cmd /c %PYCONLYSE%\bin\start_all_OWIS.cmd
start cmd /c %PYCONLYSE%\bin\start_all_BASLER.cmd
start cmd /c %PYCONLYSE%\bin\start_all_STANDA.cmd
start cmd /c %PYCONLYSE%\bin\start_all_TOPDIRECT.cmd
timeout 7
start cmd /c %TANGO_ROOT%\bin\Starter.exe everest
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-jive.bat
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-astor.bat
