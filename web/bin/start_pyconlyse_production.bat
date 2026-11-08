@echo off
REM Start the production backend on Everest. The backend serves the compiled
REM React frontend from web\frontend\build, so no development server is needed.

setlocal EnableExtensions
set "PROJECT_ROOT=C:\dev\pyconlyse"
set "RUNTIME_CONFIG=C:\ProgramData\Pyconlyse\production.env.cmd"

if not exist "%RUNTIME_CONFIG%" (
    echo ERROR: production web configuration is missing: %RUNTIME_CONFIG%
    exit /b 1
)
call "%RUNTIME_CONFIG%"

if not exist "%PYCONLYSE_PYTHON%" (
    echo ERROR: PYCONLYSE_PYTHON is unavailable: %PYCONLYSE_PYTHON%
    exit /b 1
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":5000 .*LISTENING"') do (
    echo Pyconlyse production server is already listening on port 5000.
    exit /b 0
)

"%PYCONLYSE_PYTHON%" -B "%ProgramData%\Pyconlyse\deployment\everest_git_release.py" launch-production
exit /b %errorlevel%
