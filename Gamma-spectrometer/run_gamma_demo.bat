@echo off
cd /d "%~dp0"
set AVANTES_EMULATOR=1
set AVANTES_DEMO_KINETICS=1
set AVANTES_DEMO_DURATION_S=40
set AVANTES_DEMO_MAX_OD=0.95
conda run -n pyconlyse39 python avantes_dual_viewer.py
