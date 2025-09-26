@echo off
setlocal

rem Resolve project root (parent of this script's directory)
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

set "MAIN_APP=%ROOT%\main_app"
set "ENTRY=%MAIN_APP%\main_gui.py"

if not exist "%ENTRY%" (
  echo Error: "%ENTRY%" not found.
  exit /b 1
)

rem Use pyconlyse_env conda environment
set "CONDA_CMD="
set "PY="

rem Try to find conda
where conda >nul 2>&1
if not errorlevel 1 (
  set "CONDA_CMD=conda"
) else (
  rem Use ANACONDA environment variable if available
  if defined ANACONDA (
    if exist "%ANACONDA%\Scripts\conda.exe" (
      set "CONDA_CMD=%ANACONDA%\Scripts\conda.exe"
    )
  ) else (
    rem Try common installation paths
    if exist "%USERPROFILE%\Anaconda3\Scripts\conda.exe" (
      set "CONDA_CMD=%USERPROFILE%\Anaconda3\Scripts\conda.exe"
    ) else if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" (
      set "CONDA_CMD=%USERPROFILE%\Miniconda3\Scripts\conda.exe"
    ) else if exist "C:\Anaconda3\Scripts\conda.exe" (
      set "CONDA_CMD=C:\Anaconda3\Scripts\conda.exe"
    ) else if exist "C:\Miniconda3\Scripts\conda.exe" (
      set "CONDA_CMD=C:\Miniconda3\Scripts\conda.exe"
    ) else if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
      set "CONDA_CMD=C:\ProgramData\miniconda3\Scripts\conda.exe"
    )
  )
)

if defined CONDA_CMD if defined pyconlyse_env (
  set "USE_CONDA=1"
  goto :gotpy
)

:gotpy
rem Fallback to system Python if conda not found
if not defined PY (
  where pythonw >nul 2>&1
  if not errorlevel 1 set "PY=pythonw"
)

if not defined PY set "PY=python"

if defined USE_CONDA (
  echo Using Conda environment: %pyconlyse_env%
  echo Working directory: %MAIN_APP%
  echo Entry script: %ENTRY%
  
  pushd "%MAIN_APP%" >nul
  %CONDA_CMD% run -n %pyconlyse_env% python "%ENTRY%" %*
  set "EXIT_CODE=%errorlevel%"
  popd >nul
) else (
  echo Using Python: %PY%
  echo Working directory: %MAIN_APP%
  echo Entry script: %ENTRY%
  
  pushd "%MAIN_APP%" >nul
  "%PY%" "%ENTRY%" %*
  set "EXIT_CODE=%errorlevel%"
  popd >nul
)

if %EXIT_CODE% neq 0 (
  echo.
  echo Python exited with error code %EXIT_CODE%
  pause
)

endlocal
exit /b 0
