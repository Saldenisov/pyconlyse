@echo off
REM Resolve PYCONLYSE_PYTHON without invoking conda activation.
REM Called with CALL so selected variables remain in the device-server shell.

if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
set "PYCONLYSE_PYTHON_SOURCE="

if defined PYCONLYSE_PYTHON (
    set "PYCONLYSE_PYTHON_ABSOLUTE="
    if "%PYCONLYSE_PYTHON:~1,2%"==":\" set "PYCONLYSE_PYTHON_ABSOLUTE=1"
    if "%PYCONLYSE_PYTHON:~0,2%"=="\\" set "PYCONLYSE_PYTHON_ABSOLUTE=1"
    if /I not "%PYCONLYSE_PYTHON:~-4%"==".exe" set "PYCONLYSE_PYTHON_ABSOLUTE="
    if defined PYCONLYSE_PYTHON_ABSOLUTE if exist "%PYCONLYSE_PYTHON%" (
        set "PYCONLYSE_PYTHON_SOURCE=PYCONLYSE_PYTHON"
        goto resolved
    )
)

set "PYCONLYSE_PYTHON="
call :try "%ANACONDA%\envs\%PYCONLYSE_ENV%\python.exe" "ANACONDA"
if /I "%CONDA_DEFAULT_ENV%"=="%PYCONLYSE_ENV%" call :try "%CONDA_PREFIX%\python.exe" "CONDA_PREFIX"
call :try "%USERPROFILE%\.conda\envs\%PYCONLYSE_ENV%\python.exe" "USERPROFILE/.conda"
call :try "%USERPROFILE%\miniconda3\envs\%PYCONLYSE_ENV%\python.exe" "USERPROFILE/miniconda3"
call :try "%USERPROFILE%\anaconda3\envs\%PYCONLYSE_ENV%\python.exe" "USERPROFILE/anaconda3"
call :try "%USERPROFILE%\miniforge3\envs\%PYCONLYSE_ENV%\python.exe" "USERPROFILE/miniforge3"
call :try "%LOCALAPPDATA%\miniconda3\envs\%PYCONLYSE_ENV%\python.exe" "LOCALAPPDATA/miniconda3"
call :try "C:\ProgramData\miniconda3\envs\%PYCONLYSE_ENV%\python.exe" "ProgramData/miniconda3"
call :try "C:\ProgramData\anaconda3\envs\%PYCONLYSE_ENV%\python.exe" "ProgramData/anaconda3"

if not defined PYCONLYSE_PYTHON exit /b 1

:resolved
for %%I in ("%PYCONLYSE_PYTHON%") do set "PYCONLYSE_PYTHON=%%~fI"
for %%I in ("%PYCONLYSE_PYTHON%") do set "PYCONLYSE_PYTHON_DIR=%%~dpI"
exit /b 0

:try
if defined PYCONLYSE_PYTHON exit /b 0
if exist "%~1" (
    set "PYCONLYSE_PYTHON=%~1"
    set "PYCONLYSE_PYTHON_SOURCE=%~2"
)
exit /b 0
