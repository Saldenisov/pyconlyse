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

rem Prefer the configured direct runtime, then the configured Conda environment.
rem A selected Pyconlyse runtime must never fall back to system Python.
set "CONDA_CMD="
set "PY="
if not defined PYCONLYSE_ENV set "PYCONLYSE_ENV=pyconlyse312"
set "pyconlyse_env=%PYCONLYSE_ENV%"
if /I "%PYCONLYSE_ENV%"=="pyconlyse312" set "PYTHONNOUSERSITE=1"

if defined PYCONLYSE_PYTHON (
  set "PY=%PYCONLYSE_PYTHON%"
  if not exist "%PY%" (
    echo Error: configured PYCONLYSE_PYTHON "%PY%" not found.
    exit /b 1
  )
  goto :gotpy
)

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
if not defined PY if defined PYCONLYSE_ENV if not defined CONDA_CMD (
  echo Error: Conda was not found for configured PYCONLYSE_ENV "%PYCONLYSE_ENV%".
  exit /b 1
)

rem Fallback to system Python only when no Pyconlyse runtime was configured.
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
