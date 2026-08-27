@echo off
REM =====================================================
REM TANGO INFRASTRUCTURE - Windows Auto Startup
REM Database and Starter are launched only when absent.
REM Readiness is detected instead of sleeping for a fixed delay.
REM =====================================================

setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%tango_windows_startup.log"
set "DB_READY_TIMEOUT_SECONDS=60"
set "STARTER_READY_TIMEOUT_SECONDS=30"
if not defined PYCONLYSE for %%I in ("%SCRIPT_DIR%\..\..") do set "PYCONLYSE=%%~fI"
set "TANGO_PROBE=%SCRIPT_DIR%probe_tango_readiness.py"

call :log "Tango infrastructure startup requested"

if not defined TANGO_ROOT (
    call :log "ERROR: TANGO_ROOT environment variable not set"
    exit /b 1
)

if not exist "%TANGO_ROOT%\bin\start-db.bat" (
    call :log "ERROR: start-db.bat missing under %TANGO_ROOT%\bin"
    exit /b 1
)

if not exist "%TANGO_ROOT%\bin\Starter.exe" (
    call :log "ERROR: Starter.exe missing under %TANGO_ROOT%\bin"
    exit /b 1
)
if not exist "%TANGO_PROBE%" (
    call :log "ERROR: Tango readiness probe missing: %TANGO_PROBE%"
    exit /b 1
)
call "%PYCONLYSE%\DeviceServers\prepare_python_runtime.cmd"
if errorlevel 1 (
    call :log "ERROR: PYCONLYSE_PYTHON could not be resolved"
    exit /b 1
)

set "DB_PORT=10000"
if defined TANGO_HOST (
    for /f "tokens=2 delims=:" %%A in ("%TANGO_HOST%") do set "DB_PORT=%%A"
)
if not defined DB_PORT set "DB_PORT=10000"

set "HOSTNAME=%COMPUTERNAME%"
if not defined HOSTNAME set "HOSTNAME=localhost"
set "PYCONLYSE_STARTER_HOST=%HOSTNAME%"
call :log "TANGO_ROOT=%TANGO_ROOT%; TANGO_HOST=%TANGO_HOST%; database_port=%DB_PORT%; hostname=%HOSTNAME%"

call :port_listening "%DB_PORT%"
if not errorlevel 1 goto database_ready

call :log "DATABASE launch requested"
start "Tango-Database-Service" /min cmd /k ""%TANGO_ROOT%\bin\start-db.bat""
if errorlevel 1 (
    call :log "ERROR: database terminal could not be launched"
    exit /b 1
)

call :wait_for_port "%DB_PORT%" "%DB_READY_TIMEOUT_SECONDS%"
if errorlevel 1 (
    call :log "ERROR: database port %DB_PORT% not ready within %DB_READY_TIMEOUT_SECONDS%s"
    exit /b 1
)
goto start_starter

:database_ready
call :log "DATABASE already listening on port %DB_PORT%"
call :wait_for_port "%DB_PORT%" "%DB_READY_TIMEOUT_SECONDS%"
if errorlevel 1 (
    call :log "ERROR: Tango database probe did not succeed within %DB_READY_TIMEOUT_SECONDS%s"
    exit /b 1
)

:start_starter
call :starter_for_host_running
if not errorlevel 1 goto wait_for_starter

call :log "STARTER launch requested for %HOSTNAME%"
start "Tango-Starter-%HOSTNAME%" /min cmd /k ""%TANGO_ROOT%\bin\Starter.exe" %HOSTNAME%"
if errorlevel 1 (
    call :log "ERROR: Starter terminal could not be launched"
    exit /b 1
)

:wait_for_starter
call :wait_for_starter "%STARTER_READY_TIMEOUT_SECONDS%"
if errorlevel 1 (
    call :log "ERROR: Starter %HOSTNAME% was not Tango-ready within %STARTER_READY_TIMEOUT_SECONDS%s"
    exit /b 1
)
goto complete

:complete
call :log "TANGO_STARTUP_COMPLETE database_port=%DB_PORT% starter_host=%HOSTNAME%"
exit /b 0

:port_listening
netstat -an | findstr /r /c:":%~1 .*LISTENING" >nul 2>&1
exit /b %errorlevel%

:wait_for_port
set /a "elapsed=0"
:wait_for_port_loop
call :port_listening "%~1"
if not errorlevel 1 (
    call :probe_database
    if not errorlevel 1 (
        call :log "DATABASE_READY port=%~1 elapsed_seconds=!elapsed!"
        exit /b 0
    )
)
if !elapsed! GEQ %~2 exit /b 1
timeout /t 1 /nobreak >nul
set /a "elapsed+=1"
goto wait_for_port_loop

:probe_database
"%PYCONLYSE_PYTHON%" "%TANGO_PROBE%" --database >nul 2>&1
exit /b %errorlevel%

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
        call :log "STARTER_READY host=%PYCONLYSE_STARTER_HOST% elapsed_seconds=!elapsed!"
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
