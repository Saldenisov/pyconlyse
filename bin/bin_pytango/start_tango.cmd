start cmd /c %TANGO_ROOT%\bin\start-db.bat
timeout 25
start cmd /c %TANGO_ROOT%\bin\Starter.exe everest
timeout 5
start cmd /c %TANGO_ROOT%\bin\start-jive.bat
timeout 1
start cmd /c %TANGO_ROOT%\bin\start-astor.bat
