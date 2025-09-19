@echo off
REM PyConlyse Interactive Application Startup Script
REM This script starts the interactive PyConlyse application with menu system

echo Starting PyConlyse Interactive Application...
echo.

REM Set the application root
set APP_ROOT=%~dp0..
set MAIN_APP_PATH=%APP_ROOT%\main_app

echo Application Root: %APP_ROOT%
echo Main App Path: %MAIN_APP_PATH%
echo.

REM Check if main_app directory exists
if not exist "%MAIN_APP_PATH%" (
    echo ERROR: main_app directory not found at %MAIN_APP_PATH%
    echo Please ensure the modular application structure is in place.
    pause
    exit /b 1
)

REM Change to the main_app directory and run the interactive application
cd /d "%MAIN_APP_PATH%"
echo Running: python main_interactive.py
echo.

python main_interactive.py

echo.
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyConlyse interactive application failed to start
    echo Error code: %ERRORLEVEL%
) else (
    echo PyConlyse interactive application exited successfully
)

echo.
echo Press any key to exit...
pause >nul