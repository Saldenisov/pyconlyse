@echo off
cd /d "%~dp0"
set "CONDA_EXE=%ProgramData%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=conda"
"%CONDA_EXE%" run -n pyconlyse311 python avantes_dual_viewer.py
pause
