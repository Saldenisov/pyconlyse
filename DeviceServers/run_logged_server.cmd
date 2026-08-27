@echo off
REM Run one Python Tango device server while preserving terminal output and
REM mirroring it into the file convention used by Tango Starter DevReadLog.
setlocal EnableExtensions

set "SERVER_NAME=%~1"
set "INSTANCE_NAME=%~2"
set "DEVICE_DIR=%~3"
set "DEVICE_SCRIPT=%~4"
set "SERVER_ENVIRONMENT=%~5"
set "SERVER_EXTRA_ARGUMENT=%~6"

if "%SERVER_NAME%"=="" (
    echo ERROR: Server name is required.
    exit /b 2
)
if "%INSTANCE_NAME%"=="" (
    echo ERROR: Server instance is required.
    exit /b 2
)
if "%DEVICE_DIR%"=="" (
    echo ERROR: Device directory is required.
    exit /b 2
)
if "%DEVICE_SCRIPT%"=="" (
    echo ERROR: Device script is required.
    exit /b 2
)

if not defined PYCONLYSE set "PYCONLYSE=C:\dev\pyconlyse"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
if not defined PYCONLYSE_LOG_DIR set "PYCONLYSE_LOG_DIR=C:\temp\ds.log"
if not "%SERVER_ENVIRONMENT%"=="" set "%SERVER_ENVIRONMENT%"

if not exist "%PYCONLYSE_LOG_DIR%" mkdir "%PYCONLYSE_LOG_DIR%"
set "PYCONLYSE_DS_LOG_FILE=%PYCONLYSE_LOG_DIR%\%SERVER_NAME%_%INSTANCE_NAME%.log"
echo ==== %date% %time% runner entered %SERVER_NAME%/%INSTANCE_NAME% ==== >> "%PYCONLYSE_DS_LOG_FILE%"
set "PYCONLYSE_DS_SCRIPT=%DEVICE_SCRIPT%"
set "PYCONLYSE_DS_INSTANCE=%INSTANCE_NAME%"
set "PYCONLYSE_DS_EXTRA_ARGUMENT=%SERVER_EXTRA_ARGUMENT%"

cd /d "%DEVICE_DIR%"
call "%~dp0prepare_python_runtime.cmd"
if errorlevel 1 (
    echo ERROR: No direct PYCONLYSE_PYTHON executable found. >> "%PYCONLYSE_DS_LOG_FILE%"
    echo ERROR: No direct PYCONLYSE_PYTHON executable found.
    exit /b 2
)
echo ==== %date% %time% direct runtime ready %PYCONLYSE_PYTHON% ==== >> "%PYCONLYSE_DS_LOG_FILE%"

set "PYTHONPATH=%PYCONLYSE%;%PYTHONPATH%"
set "PYTHONUNBUFFERED=1"
echo ==== %date% %time% starting %SERVER_NAME%/%INSTANCE_NAME% ==== >> "%PYCONLYSE_DS_LOG_FILE%"
echo PYCONLYSE_PYTHON=%PYCONLYSE_PYTHON% source=%PYCONLYSE_PYTHON_SOURCE% >> "%PYCONLYSE_DS_LOG_FILE%"
echo Log file: %PYCONLYSE_DS_LOG_FILE%
echo Starting %SERVER_NAME%/%INSTANCE_NAME%...

REM Start the configured interpreter directly. A separate terminal tab tails
REM this log, so PowerShell/Tee startup is not part of Tango registration.
if defined PYCONLYSE_DS_EXTRA_ARGUMENT (
    "%PYCONLYSE_PYTHON%" %PYCONLYSE_DS_SCRIPT% %PYCONLYSE_DS_INSTANCE% %PYCONLYSE_DS_EXTRA_ARGUMENT% >> "%PYCONLYSE_DS_LOG_FILE%" 2>&1
) else (
    "%PYCONLYSE_PYTHON%" %PYCONLYSE_DS_SCRIPT% %PYCONLYSE_DS_INSTANCE% >> "%PYCONLYSE_DS_LOG_FILE%" 2>&1
)
set "EXIT_CODE=%ERRORLEVEL%"
echo ==== %date% %time% exited with %EXIT_CODE% ==== >> "%PYCONLYSE_DS_LOG_FILE%"
exit /b %EXIT_CODE%
