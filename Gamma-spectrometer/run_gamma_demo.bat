@echo off
cd /d "%~dp0"
set AVANTES_EMULATOR=1
set AVANTES_DEMO_KINETICS=1
set AVANTES_DEMO_DURATION_S=40
set AVANTES_DEMO_MAX_OD=0.95
set "CONDA_EXE=%ProgramData%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%ProgramData%\miniconda3\condabin\conda.bat"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%USERPROFILE%\miniconda3\condabin\conda.bat"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\condabin\conda.bat"
if not exist "%CONDA_EXE%" set "CONDA_EXE=conda"
"%CONDA_EXE%" run -n pyconlyse311 python avantes_dual_viewer.py
pause
