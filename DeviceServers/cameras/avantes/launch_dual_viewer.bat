@echo off
REM Avantes Dual Spectrometer Viewer Launcher
REM ==========================================

echo.
echo ========================================
echo Avantes Dual Spectrometer Viewer
echo ========================================
echo.
echo Starting application...
echo.

REM Navigate to script directory
cd /d %~dp0

REM Launch the PyQt5 application
python avantes_dual_viewer.py

REM Pause if there's an error
if errorlevel 1 (
    echo.
    echo ========================================
    echo ERROR: Application failed to start!
    echo ========================================
    echo.
    echo Possible issues:
    echo - Python not installed or not in PATH
    echo - Required packages not installed
    echo - Missing dependencies
    echo.
    echo Please run: pip install PyQt5 pyqtgraph numpy msl-equipment
    echo.
    pause
)
