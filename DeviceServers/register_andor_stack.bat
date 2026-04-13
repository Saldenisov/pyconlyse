@echo off
REM =====================================================
REM Register Andor Tango devices
REM =====================================================

setlocal enabledelayedexpansion

if not defined ANACONDA (
    echo ERROR: ANACONDA environment variable not set!
    pause
    exit /b 1
)

if not defined PYCONLYSE (
    echo ERROR: PYCONLYSE environment variable not set!
    pause
    exit /b 1
)

if not defined PYCONLYSE_ENV (
    set PYCONLYSE_ENV=pyconlyse39
    echo INFO: Using default conda environment: pyconlyse39
)

cd /d "%PYCONLYSE%\DeviceServers\andor"
call "%ANACONDA%\Scripts\activate.bat" %PYCONLYSE_ENV%
set PYTHONPATH=%PYCONLYSE%
python add_ds_ANDOR_STACK.py
