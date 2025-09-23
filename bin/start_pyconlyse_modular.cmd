@echo off
REM PyConlyse Modular Application Startup Script
REM This script starts the new modular PyConlyse application

echo Starting PyConlyse Modular Application...
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

REM Change to the main_app directory and run the application
cd /d "%MAIN_APP_PATH%"
echo Running: python main.py
echo.

python main.py

echo.
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyConlyse application failed to start
    echo Error code: %ERRORLEVEL%
) else (
    echo PyConlyse application completed successfully
)

echo.
echo Press any key to exit...
pause >nul