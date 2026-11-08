@echo off
setlocal
REM Development backend with Socket.IO, on loopback port 5000 by default.
set "PYCONLYSE_PRODUCTION=false"
set "PYCONLYSE_ENFORCE_DEVICE_AUTH=false"
set "PYCONLYSE_JWT_COOKIE_SECURE=false"
if not defined PYCONLYSE_WEB_HOST set "PYCONLYSE_WEB_HOST=127.0.0.1"
if not defined PYCONLYSE_WEB_PORT set "PYCONLYSE_WEB_PORT=5000"
if not defined PYCONLYSE_WEB_DEBUG set "PYCONLYSE_WEB_DEBUG=true"
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse312"
call "%~dp0..\..\DeviceServers\prepare_python_runtime.cmd"
if errorlevel 1 (
    echo ERROR: Python environment %PYCONLYSE_ENV% could not be resolved.
    exit /b 1
)
cd /d "%~dp0.."
"%PYCONLYSE_PYTHON%" -u start_pyconlyse_server.py
exit /b %errorlevel%
