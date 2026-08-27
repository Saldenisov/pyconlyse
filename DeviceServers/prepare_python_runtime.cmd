@echo off
REM Prepare one process-local Python runtime. CALL this file from a wrapper.

if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse39"
call "%~dp0resolve_python.cmd"
if not errorlevel 1 (
    set "PATH=%PYCONLYSE_PYTHON_DIR%;%PYCONLYSE_PYTHON_DIR%Library\bin;%PYCONLYSE_PYTHON_DIR%Scripts;%PATH%"
    exit /b 0
)

exit /b 1
