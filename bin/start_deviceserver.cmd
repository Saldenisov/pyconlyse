@echo off
REM =====================================================
REM PYCONLYSE - Unified DeviceServer Startup Template
REM This script can start any DeviceServer with proper
REM error handling and logging
REM =====================================================

setlocal enabledelayedexpansion

REM Get parameters
set DEVICE_TYPE=%1
set DEVICE_INSTANCE=%2
set VISUALIZATION_TYPE=%3

REM Validate parameters
if "%DEVICE_TYPE%"=="" (
    echo ERROR: Device type is required!
    echo Usage: start_deviceserver.cmd DEVICE_TYPE [INSTANCE] [VIS_TYPE]
    echo Example: start_deviceserver.cmd ANDOR_CCD V0 FULL
    pause
    exit /b 1
)

if "%DEVICE_INSTANCE%"=="" set DEVICE_INSTANCE=default
if "%VISUALIZATION_TYPE%"=="" set VISUALIZATION_TYPE=FULL

REM Validate environment variables
if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    pause
    exit /b 1
)

REM Set default conda environment if not specified
if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
    echo INFO: Using default conda environment: pyconlyse39
)

if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable not set!
    pause
    exit /b 1
)

REM Define device server mappings
set ANDOR_CCD_PATH=%PYCONLYSE%\DeviceServers\ANDOR_CCD
set ANDOR_CCD_SCRIPT=DS_ANDOR_CCD.py

set BASLER_PATH=%PYCONLYSE%\DeviceServers\BASLER
set BASLER_SCRIPT=DS_Basler_camera.py

set ARCHIVE_PATH=%PYCONLYSE%\DeviceServers\ARCHIVE
set ARCHIVE_SCRIPT=DS_Archive.py

set OWIS_PATH=%PYCONLYSE%\DeviceServers\OWIS
set OWIS_SCRIPT=DS_OWIS_PS90.py

set STANDA_PATH=%PYCONLYSE%\DeviceServers\STANDA
set STANDA_SCRIPT=DS_Standa_Motor.py

set NETIO_PATH=%PYCONLYSE%\DeviceServers\NETIO
set NETIO_SCRIPT=DS_NetIO_PDU.py

set TOPDIRECT_PATH=%PYCONLYSE%\DeviceServers\TopDirect
set TOPDIRECT_SCRIPT=DS_TopDirect_Motor.py

set LASER_POINTING_PATH=%PYCONLYSE%\DeviceServers\LaserPointing
set LASER_POINTING_SCRIPT=DS_LaserPointing.py

set ML_STABILITY_PATH=%PYCONLYSE%\DeviceServers\data\ml
set ML_STABILITY_SCRIPT=DS_ML_client.py

REM Set device-specific path and script
call set DEVICE_PATH=%%!DEVICE_TYPE!_PATH%%
call set DEVICE_SCRIPT=%%!DEVICE_TYPE!_SCRIPT%%

if "%DEVICE_PATH%"=="" (
    echo ERROR: Unknown device type '%DEVICE_TYPE%'
    echo Supported types: ANDOR_CCD, BASLER, ARCHIVE, OWIS, STANDA, NETIO, TOPDIRECT, LASER_POINTING, ML_STABILITY
    pause
    exit /b 1
)

if not exist "%DEVICE_PATH%" (
    echo ERROR: Device path does not exist: %DEVICE_PATH%
    pause
    exit /b 1
)

if not exist "%DEVICE_PATH%\%DEVICE_SCRIPT%" (
    echo ERROR: Device script does not exist: %DEVICE_PATH%\%DEVICE_SCRIPT%
    pause
    exit /b 1
)

REM Logging
REM Ensure DS logs are written to <repo_root>\LOGS\DS\<DS_class>\<instance_name>\
set LOG_DIR=%PYCONLYSE%\LOGS\DS\%DEVICE_TYPE%\%DEVICE_INSTANCE%
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set DATESTAMP=%date:~-4,4%%date:~-7,2%%date:~-10,2%
set LOG_FILE=%LOG_DIR%\deviceserver_%DEVICE_TYPE%_%DEVICE_INSTANCE%_%DATESTAMP%.log

echo [%date% %time%] Starting DeviceServer %DEVICE_TYPE% instance %DEVICE_INSTANCE% >> "%LOG_FILE%"
echo [%date% %time%] Path: %DEVICE_PATH% >> "%LOG_FILE%"
echo [%date% %time%] Script: %DEVICE_SCRIPT% >> "%LOG_FILE%"
echo [%date% %time%] Visualization: %VISUALIZATION_TYPE% >> "%LOG_FILE%"

REM Display startup information
echo.
echo =====================================================
echo PYCONLYSE DeviceServer Startup
echo =====================================================
echo Device Type: %DEVICE_TYPE%
echo Instance: %DEVICE_INSTANCE%
echo Visualization: %VISUALIZATION_TYPE%
echo Path: %DEVICE_PATH%
echo Script: %DEVICE_SCRIPT%
echo Log: %LOG_FILE%
echo =====================================================
echo.

REM Activate conda environment and start DeviceServer
REM Capture stdout/stderr into the log file
REM Note: cd /d switches drive as well if necessary
echo Starting DeviceServer...
echo [%date% %time%] Activating conda environment %PYCONLYSE_ENV% >> "%LOG_FILE%"

start /min cmd /k "cd /d \"%DEVICE_PATH%\" ^& conda activate %PYCONLYSE_ENV% ^& python \"%DEVICE_SCRIPT%\" \"%DEVICE_INSTANCE%\" \"%VISUALIZATION_TYPE%\" >> \"%LOG_FILE%\" 2^>^&1 ^& echo [%date% %time%] DeviceServer %DEVICE_TYPE% exited >> \"%LOG_FILE%\""

echo DeviceServer %DEVICE_TYPE% (%DEVICE_INSTANCE%) started successfully!
echo Check the log file for details: %LOG_FILE%
echo.
