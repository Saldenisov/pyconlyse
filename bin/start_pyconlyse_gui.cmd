@echo off
REM PyConlyse GUI Application Startup Script
REM This script starts the GUI-first PyConlyse application

echo Starting PyConlyse GUI Application...
echo GUI will start immediately, connections established in background
echo.

REM Set the application root
set APP_ROOT=%~dp0..
set MAIN_APP_PATH=%APP_ROOT%\main_app

echo Application Root: %APP_ROOT%
echo Main App Path: %MAIN_APP_PATH%
echo.

echo TANGO_HOST environment: %TANGO_HOST%
if "%TANGO_HOST%"=="" (
    echo WARNING: TANGO_HOST is not set. The GUI may not detect a running Tango DB.
    echo You can set it for this session with:  set TANGO_HOST=localhost:10000
    echo Or set the appropriate host:port for your DB server.
    echo.
)

REM Check if main_app directory exists
if not exist "%MAIN_APP_PATH%" (
    echo ERROR: main_app directory not found at %MAIN_APP_PATH%
    echo Please ensure the modular application structure is in place.
    pause
    exit /b 1
)

REM Change to the main_app directory and run the GUI application
cd /d "%MAIN_APP_PATH%"
echo Running: python main_gui.py
echo.

REM Start the GUI application
python main_gui.py

echo.
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyConlyse GUI application failed to start
    echo Error code: %ERRORLEVEL%
) else (
    echo PyConlyse GUI application exited successfully
)

echo.
echo Press any key to exit...
pause >nul