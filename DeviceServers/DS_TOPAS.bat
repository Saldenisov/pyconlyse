@echo off
setlocal
if not defined PYCONLYSE_PYTHON (
  echo Set PYCONLYSE_PYTHON to the absolute Python interpreter containing PyTango.
  exit /b 1
)
pushd "%~dp0.."
"%PYCONLYSE_PYTHON%" -u -m DeviceServers.lasers.topas.DS_TOPAS %*
set "TOPAS_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %TOPAS_EXIT_CODE%
