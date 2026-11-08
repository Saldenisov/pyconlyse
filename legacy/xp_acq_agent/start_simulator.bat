@echo off
cd /d "%~dp0"
"C:\Python34\python.exe" main.py --config config.simulation.xp.json --initialize-simulation
pause
