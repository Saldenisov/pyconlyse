@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Resolve project root (parent of this script's directory)
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

set "MAIN_APP=%ROOT%\main_app"
set "ENTRY=%MAIN_APP%\main_gui.py"

if not exist "%ENTRY%" (
  echo Error: "%ENTRY%" not found.
  exit /b 1
)

rem Prefer explicitly configured interpreter, then configured Conda environment.
rem A configured runtime must never silently fall back to system Python.
set "CONDA_CMD="
set "PY="
set "ENV_NAME="
set "USE_CONDA="

if defined PYCONLYSE_PYTHON (
  set "PY=%PYCONLYSE_PYTHON%"
  if not exist "!PY!" (
    echo Error: configured PYCONLYSE_PYTHON "!PY!" not found.
    exit /b 1
  )
)

if defined PYCONLYSE_ENV set "ENV_NAME=%PYCONLYSE_ENV%"

rem Keep Python 3.12 isolated from per-user package installations.
if /I "%ENV_NAME%"=="pyconlyse312" set "PYTHONNOUSERSITE=1"

rem Try to find Conda only for a configured environment.
if not defined PY if defined ENV_NAME (
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
)

if not defined PY if defined ENV_NAME if defined CONDA_CMD set "USE_CONDA=1"

if not defined PY if defined ENV_NAME if not defined USE_CONDA (
  echo Error: Conda was not found for configured PYCONLYSE_ENV "%ENV_NAME%".
  exit /b 1
)

rem Preserve legacy fallback only when no Pyconlyse runtime was configured.
if not defined PY (
  where pythonw >nul 2>&1
  if not errorlevel 1 set "PY=pythonw"
)

if not defined PY set "PY=python"

if defined PYCONLYSE_LAUNCHER_DRY_RUN (
  if defined USE_CONDA (
    echo Runtime: conda environment %ENV_NAME%
  ) else (
    echo Runtime: %PY%
  )
  exit /b 0
)

if defined USE_CONDA (
  echo Using Conda environment: %ENV_NAME%
  echo Working directory: %MAIN_APP%
  echo Entry script: %ENTRY%
  
  pushd "%MAIN_APP%" >nul
  call "%CONDA_CMD%" run -n "%ENV_NAME%" python "%ENTRY%" %*
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
exit /b %EXIT_CODE%
