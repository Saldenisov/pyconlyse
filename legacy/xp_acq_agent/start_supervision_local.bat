@echo off
cd /d "%~dp0"
if not exist "runtime\acq.key" (
    echo Missing runtime\acq.key. Generate a shared key before starting.
    exit /b 1
)
"C:\Python34\python.exe" main.py --config config.simulation.everest.json --supervision --key-file "runtime\acq.key"
