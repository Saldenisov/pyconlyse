start /min cmd /c %TANGO_ROOT%\bin\start-astor.bat
timeout 1
start /min cmd /c %TANGO_ROOT%\bin\start-jive.bat
start cmd /c %TANGO_ROOT%\bin\Starter.exe alabama
