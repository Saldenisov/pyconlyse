@echo off
setlocal EnableExtensions
REM Batch file to start Treatment.py GUI application
REM Created for pyconlyse Treatment GUI
REM Uses conda environment pyconlyse39

set "TARGET_ENV=pyconlyse39"
echo Starting Treatment GUI...
echo Working directory: %CD%

REM Initialize and activate conda environment robustly
set "ACTIVATED_WITH_CONDA="
REM 1) Try conda from PATH
where conda >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using conda from PATH
    call conda activate %TARGET_ENV%
    if not errorlevel 1 set "ACTIVATED_WITH_CONDA=1"
) else (
    echo conda not found on PATH; probing ANACONDA and common locations...
    REM 2) Try ANACONDA env var then common install locations
    set "CONDA_BAT="
    set "ACTIVATE_BAT="
    if defined ANACONDA (
        if exist "%ANACONDA%\condabin\conda.bat" set "CONDA_BAT=%ANACONDA%\condabin\conda.bat"
        if not defined CONDA_BAT if exist "%ANACONDA%\Scripts\activate.bat" set "ACTIVATE_BAT=%ANACONDA%\Scripts\activate.bat"
    )
    if not defined CONDA_BAT if not defined ACTIVATE_BAT (
        for %%C in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\Anaconda3" "%ProgramData%\Miniconda3") do (
            if not defined CONDA_BAT if exist "%%~fC\condabin\conda.bat" set "CONDA_BAT=%%~fC\condabin\conda.bat"
            if not defined ACTIVATE_BAT if exist "%%~fC\Scripts\activate.bat" set "ACTIVATE_BAT=%%~fC\Scripts\activate.bat"
        )
    )
    if defined CONDA_BAT (
        echo Using "%CONDA_BAT%"
        call "%CONDA_BAT%" activate %TARGET_ENV%
        if not errorlevel 1 set "ACTIVATED_WITH_CONDA=1"
    ) else (
        if defined ACTIVATE_BAT (
            echo Using "%ACTIVATE_BAT%"
            call "%ACTIVATE_BAT%" %TARGET_ENV%
            if not errorlevel 1 set "ACTIVATED_WITH_CONDA=1"
        ) else (
            echo Warning: Could not locate conda scripts.
        )
    )
)

if not defined ACTIVATED_WITH_CONDA (
    echo Could not activate conda environment %TARGET_ENV% via scripts.
)

echo.

REM Ensure LOG directory exists
if not exist "C:\dev\pyconlyse\LOG" (
    echo Creating LOG directory...
    mkdir "C:\dev\pyconlyse\LOG"
)

REM Change to the Treatment directory (where main.py is located)
cd /d "C:\dev\pyconlyse\Treatment"

REM Determine interpreter and run main.py
if not defined ACTIVATED_WITH_CONDA (
    set "ENV_PY="
    if defined ANACONDA if exist "%ANACONDA%\envs\%TARGET_ENV%\python.exe" set "ENV_PY=%ANACONDA%\envs\%TARGET_ENV%\python.exe"
    if not defined ENV_PY (
        for %%C in ("%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%LOCALAPPDATA%\miniconda3" "%ProgramData%\Anaconda3" "%ProgramData%\Miniconda3") do (
            if not defined ENV_PY if exist "%%~fC\envs\%TARGET_ENV%\python.exe" set "ENV_PY=%%~fC\envs\%TARGET_ENV%\python.exe"
        )
    )
    if not defined ENV_PY (
        echo Error: Could not find Python interpreter for environment %TARGET_ENV%.
        echo Ensure conda is installed and the environment exists.
        pause
        exit /b 1
    )
)

echo Running Treatment main.py...
if defined ACTIVATED_WITH_CONDA (
    python main.py
) else (
    echo Using interpreter: "%ENV_PY%"
    "%ENV_PY%" main.py
)

REM Pause to see any error messages if the application closes unexpectedly
if errorlevel 1 (
    echo.
    echo An error occurred while running Treatment main.py
    pause
)

REM Deactivate conda environment if it was activated
if defined ACTIVATED_WITH_CONDA conda deactivate
