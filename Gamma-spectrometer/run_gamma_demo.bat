@echo off
setlocal
cd /d "%~dp0"
set AVANTES_EMULATOR=1
set AVANTES_DEMO_KINETICS=1
set AVANTES_DEMO_DURATION_S=40
set AVANTES_DEMO_MAX_OD=0.95
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -E -s avantes_dual_viewer.py
    goto finish
)
set "CONDA_EXE=%ProgramData%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%ProgramData%\miniconda3\condabin\conda.bat"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%USERPROFILE%\miniconda3\condabin\conda.bat"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
if not exist "%CONDA_EXE%" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\condabin\conda.bat"
if not exist "%CONDA_EXE%" set "CONDA_EXE=conda"
call "%CONDA_EXE%" run -n pyconlyse311 python avantes_dual_viewer.py
:finish
set "GAMMA_EXIT=%ERRORLEVEL%"
pause
exit /b %GAMMA_EXIT%
