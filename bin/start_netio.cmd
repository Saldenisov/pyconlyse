@echo off
rem Start NETIO client using the selected Pyconlyse environment.
call "%~dp0start_netio_conda.cmd" %*
exit /b %ERRORLEVEL%
