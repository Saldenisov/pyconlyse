@echo off
REM Pyconlyse Elysium2 Starter launcher
setlocal
set "STARTER_HOME=C:\dev\pyconlyse-runtime\starter-9.1"
set "TANGO_HOST=10.20.30.202:10000"
set "OMNIORB_CONFIG=C:\dev\pyconlyse\OMNIORB.CFG"
if not exist "%STARTER_HOME%\Starter.exe" (
  echo ERROR: Starter.exe missing at %STARTER_HOME%
  exit /b 1
)
start "" "%STARTER_HOME%\Starter.exe" elysium2
endlocal
