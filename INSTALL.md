# PyConlyse Installation Guide

This document provides instructions for setting up the PyConlyse environment using the automated PowerShell installation script.

## Prerequisites

- **Windows** (PowerShell 5.1+)
- **Conda/Anaconda/Miniconda** installed and available in PATH
  - Download from: https://docs.conda.io/en/latest/miniconda.html

## Quick Installation

1. **Open PowerShell as Administrator** (recommended)

2. **Navigate to the PyConlyse directory:**
   ```powershell
   cd C:\dev\pyconlyse
   ```

3. **Run the installation script:**
   ```powershell
   .\install-pyconlyse.ps1
   ```

## Installation Options

### Basic Installation
```powershell
.\install-pyconlyse.ps1
```
Creates the `pyconlyse39` environment with all dependencies.

### Force Reinstallation
```powershell
.\install-pyconlyse.ps1 -Force
```
Removes and recreates the environment even if it already exists.

### Custom Environment Name
```powershell
.\install-pyconlyse.ps1 -EnvironmentName "my_pyconlyse"
```
Creates an environment with a custom name.

## What the Script Does

1. **Checks Prerequisites:**
   - Verifies conda is installed and available
   - Confirms pyproject.toml and poetry.lock exist

2. **Creates Conda Environment:**
   - Creates `pyconlyse39` environment with Python 3.9
   - Handles existing environment (asks for confirmation or forces recreation)

3. **Installs Poetry:**
   - Installs Poetry package manager in the conda environment
   - Configures Poetry to use the conda environment

4. **Installs Dependencies:**
   - Uses Poetry to install all packages from poetry.lock
   - Falls back to pip if Poetry installation fails
   - Installs exact versions specified in the lock file

5. **Sets Environment Variables:**
   - Sets `PYCONLYSE_ENV=pyconlyse39` for the current user
   - Used by PyConlyse GUI to find the correct Python interpreter

6. **Verifies Installation:**
   - Tests import of key packages (PyQt5, Taurus, PyTango, etc.)
   - Reports any missing or failed imports

## After Installation

### Activate the Environment
```powershell
conda activate pyconlyse39
```

### Run PyConlyse Applications

**Main GUI (Advanced):**
```powershell
conda activate pyconlyse39
python main_app/main_gui.py
```

**Simple GUI (Legacy-style):**
```powershell
conda activate pyconlyse39
python main_app/ui/simple_main_window.py
```

**Interactive CLI:**
```powershell
conda activate pyconlyse39
python main_app/main_interactive.py
```

### Launch Device Server Clients

The GUI applications will automatically use the conda environment when launching device server clients (like Keysight, NETIO, etc.) thanks to the `PYCONLYSE_ENV` environment variable.

## Troubleshooting

### Poetry Installation Issues
If Poetry fails to install dependencies:
- The script automatically falls back to pip
- Dependencies are exported to requirements.txt and installed via pip

### Environment Already Exists
- Use `-Force` parameter to recreate the environment
- Or continue with existing environment when prompted

### Missing Packages
- Check the verification output at the end of installation
- Manually install missing packages: `conda activate pyconlyse39 && pip install <package>`

### Permission Issues
- Run PowerShell as Administrator
- Ensure you have write permissions to the conda environments directory

## Manual Installation Alternative

If the automated script fails, you can install manually:

```powershell
# Create conda environment
conda create -n pyconlyse39 python=3.9 -y
conda activate pyconlyse39

# Install Poetry
pip install poetry

# Install dependencies
poetry install --no-dev

# Set environment variable
[Environment]::SetEnvironmentVariable("PYCONLYSE_ENV", "pyconlyse39", [EnvironmentVariableTarget]::User)
```

## Updating Dependencies

To update to new dependency versions:

```powershell
conda activate pyconlyse39
cd C:\dev\pyconlyse
poetry update
poetry lock
```

Then reinstall with `-Force` or manually update the environment.