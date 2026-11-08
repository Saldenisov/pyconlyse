@echo off
setlocal
REM React hot reload; API and Socket.IO requests proxy to port 5000.
set "HOST=127.0.0.1"
set "PORT=3000"
set "BROWSER=none"
cd /d "%~dp0..\frontend"
if not exist "node_modules\react-scripts" (
    echo ERROR: Install frontend dependencies with npm ci first.
    exit /b 1
)
call npm start
exit /b %errorlevel%
