@echo off
REM Run one Python Tango device server while preserving terminal output and
REM mirroring it into the file convention used by Tango Starter DevReadLog.
setlocal EnableExtensions

set "SERVER_NAME=%~1"
set "INSTANCE_NAME=%~2"
set "DEVICE_DIR=%~3"
set "DEVICE_SCRIPT=%~4"
set "SERVER_ENVIRONMENT=%~5"

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

if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
if not defined PYCONLYSE_PYTHON set "PYCONLYSE_PYTHON=python"
if not defined PYCONLYSE_LOG_DIR set "PYCONLYSE_LOG_DIR=C:\temp\ds.log"
if not "%SERVER_ENVIRONMENT%"=="" set "%SERVER_ENVIRONMENT%"

if not exist "%PYCONLYSE_LOG_DIR%" mkdir "%PYCONLYSE_LOG_DIR%"
set "PYCONLYSE_DS_LOG_FILE=%PYCONLYSE_LOG_DIR%\%SERVER_NAME%_%INSTANCE_NAME%.log"
set "PYCONLYSE_DS_SCRIPT=%DEVICE_SCRIPT%"
set "PYCONLYSE_DS_INSTANCE=%INSTANCE_NAME%"

if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable is not set. >> "%PYCONLYSE_DS_LOG_FILE%"
    echo ERROR: ANACONDA environment variable is not set.
    exit /b 2
)

cd /d "%DEVICE_DIR%"
call "%ANACONDA%\Scripts\activate.bat" "%PYCONLYSE_ENV%"
if errorlevel 1 (
    echo ERROR: Could not activate conda environment %PYCONLYSE_ENV%. >> "%PYCONLYSE_DS_LOG_FILE%"
    echo ERROR: Could not activate conda environment %PYCONLYSE_ENV%.
    exit /b 3
)

if defined PYCONLYSE set "PYTHONPATH=%PYCONLYSE%"
echo ==== %date% %time% starting %SERVER_NAME%/%INSTANCE_NAME% ==== >> "%PYCONLYSE_DS_LOG_FILE%"
echo Log file: %PYCONLYSE_DS_LOG_FILE%
echo Starting %SERVER_NAME%/%INSTANCE_NAME%...
if defined DISABLE_ARCHIVE echo DISABLE_ARCHIVE=%DISABLE_ARCHIVE%

REM Older Windows PowerShell lacks Tee-Object -Encoding. Write UTF-8 explicitly
REM while preserving the same output in this terminal.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$utf8 = New-Object System.Text.UTF8Encoding($false); & $env:PYCONLYSE_PYTHON $env:PYCONLYSE_DS_SCRIPT $env:PYCONLYSE_DS_INSTANCE 2>&1 | ForEach-Object { $line = ($_ | Out-String); [Console]::Out.Write($line); [System.IO.File]::AppendAllText($env:PYCONLYSE_DS_LOG_FILE, $line, $utf8) }; exit $LASTEXITCODE"
set "EXIT_CODE=%ERRORLEVEL%"
echo ==== %date% %time% exited with %EXIT_CODE% ==== >> "%PYCONLYSE_DS_LOG_FILE%"
exit /b %EXIT_CODE%
