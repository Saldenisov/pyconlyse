@echo off
setlocal
set "PSModulePath="
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_gamma_packages.ps1" -Launch %*
set "GAMMA_EXIT=%ERRORLEVEL%"
if not "%GAMMA_EXIT%"=="0" pause
exit /b %GAMMA_EXIT%
