@echo off
setlocal EnableExtensions
rem Start NETIO client with the selected Pyconlyse Python runtime.
rem Usage: start_netio_conda.cmd [instance] [vis_type]

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "ENTRY=%ROOT%\scripts\start_netio_client.py"
if not exist "%ENTRY%" (
    echo Error: NETIO client entry point not found: "%ENTRY%".
    exit /b 1
)

if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse312"
if /I "%PYCONLYSE_ENV%"=="pyconlyse312" set "PYTHONNOUSERSITE=1"
set "PY=%PYCONLYSE_PYTHON%"
if not defined PY (
    for %%P in (
        "%ANACONDA%\envs\%PYCONLYSE_ENV%\python.exe"
        "%USERPROFILE%\miniconda3\envs\%PYCONLYSE_ENV%\python.exe"
        "%USERPROFILE%\.conda\envs\%PYCONLYSE_ENV%\python.exe"
        "%ProgramData%\miniconda3\envs\%PYCONLYSE_ENV%\python.exe"
    ) do if not defined PY if exist "%%~P" set "PY=%%~P"
)
if not exist "%PY%" (
    echo Error: Python for "%PYCONLYSE_ENV%" not found: "%PY%".
    exit /b 1
)

echo NETIO client runtime: "%PY%"
pushd "%ROOT%" || exit /b 1
if "%~2"=="" (
    "%PY%" "%ENTRY%" "%~1"
) else (
    "%PY%" "%ENTRY%" "%~1" "%~2"
)
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
