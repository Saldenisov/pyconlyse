@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%first_run_gamma_spectrometer.ps1" -EnvName pyconlyse39
pause
