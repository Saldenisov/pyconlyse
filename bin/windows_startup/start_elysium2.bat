@echo off
REM Pyconlyse Elysium2 Starter launcher.
REM The Tango database is on Everest; this launcher must not start a database.

setlocal EnableExtensions EnableDelayedExpansion
set "STARTER_HOME=C:\dev\pyconlyse-runtime\starter-9.1"
set "TANGO_HOST=10.20.30.202:10000"
if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
set "OMNIORB_CONFIG=%PYCONLYSE%\OMNIORB.CFG"
set "LOG_FILE=%~dp0elysium2_starter_startup.log"
set "STARTER_READY_TIMEOUT_SECONDS=30"
set "TANGO_PROBE=%~dp0probe_tango_readiness.py"
set "PYCONLYSE_STARTER_HOST=elysium2"

call :log "ELYSIUM2_STARTER launch requested tango_host=%TANGO_HOST%"
if not exist "%STARTER_HOME%\Starter.exe" (
    call :log "ERROR: Starter.exe missing at %STARTER_HOME%"
    exit /b 1
)
if not exist "%PYCONLYSE%\DeviceServers\prepare_python_runtime.cmd" (
    call :log "ERROR: Python runtime resolver missing under %PYCONLYSE%"
    exit /b 1
)
if not defined PYCONLYSE_PYTHON (
    call :log "ERROR: Set an absolute PYCONLYSE_PYTHON for the Elysium2 startup account"
    exit /b 1
)
call "%PYCONLYSE%\DeviceServers\prepare_python_runtime.cmd"
if errorlevel 1 (
    call :log "ERROR: PYCONLYSE_PYTHON is invalid or unavailable"
    exit /b 1
)
if not exist "%TANGO_PROBE%" (
    call :log "ERROR: Tango readiness probe missing: %TANGO_PROBE%"
    exit /b 1
)
pushd "%STARTER_HOME%"

call :starter_for_host_running
if not errorlevel 1 (
    call :log "ELYSIUM2_STARTER process already running"
    goto wait_for_starter
)

start "Tango-Starter-elysium2" /min cmd /k ""%STARTER_HOME%\Starter.exe" elysium2"
if errorlevel 1 (
    call :log "ERROR: Elysium2 Starter terminal could not be launched"
    exit /b 1
)

:wait_for_starter
call :wait_for_starter "%STARTER_READY_TIMEOUT_SECONDS%"
if errorlevel 1 (
    call :log "ERROR: Elysium2 Starter was not Tango-ready within %STARTER_READY_TIMEOUT_SECONDS%s"
    exit /b 1
)
call :log "ELYSIUM2_STARTER_COMPLETE"
popd
exit /b 0

:starter_for_host_running
powershell.exe -NoProfile -NonInteractive -Command "$name = [regex]::Escape($env:PYCONLYSE_STARTER_HOST); $pattern = '(^|\s)\"?' + $name + '\"?(\s|$)'; $match = Get-CimInstance Win32_Process -Filter \"Name = 'Starter.exe'\" | Where-Object { $_.CommandLine -match $pattern } | Select-Object -First 1; if ($match) { exit 0 }; exit 1" >nul 2>&1
exit /b %errorlevel%

:probe_starter
"%PYCONLYSE_PYTHON%" "%TANGO_PROBE%" --starter "tango/admin/%PYCONLYSE_STARTER_HOST%" >nul 2>&1
exit /b %errorlevel%

:wait_for_starter
set /a "elapsed=0"
:wait_for_starter_loop
call :starter_for_host_running
if not errorlevel 1 (
    call :probe_starter
    if not errorlevel 1 (
        call :log "ELYSIUM2_STARTER_READY elapsed_seconds=!elapsed!"
        exit /b 0
    )
)
if !elapsed! GEQ %~1 exit /b 1
timeout /t 1 /nobreak >nul
set /a "elapsed+=1"
goto wait_for_starter_loop

:log
setlocal DisableDelayedExpansion
set "MESSAGE=%~1"
echo [%date% %time%] %MESSAGE%
>> "%LOG_FILE%" echo [%date% %time%] %MESSAGE%
endlocal
exit /b 0
