@echo off
setlocal
REM Start the web development services; Tango runs independently.
powershell -NoProfile -Command "$ErrorActionPreference = 'Stop'; foreach ($devPort in @(5000, 3000)) { if (Get-NetTCPConnection -State Listen -LocalPort $devPort -ErrorAction SilentlyContinue) { throw ('Port ' + $devPort + ' is already in use. Stop the existing web server first.') } }; Start-Process -FilePath '%~dp0start_dev_backend.bat' -WindowStyle Hidden; Start-Process -FilePath '%~dp0start_dev_frontend.bat' -WindowStyle Hidden"
if errorlevel 1 exit /b 1
echo Development backend: http://127.0.0.1:5000
echo React hot reload: http://127.0.0.1:3000
