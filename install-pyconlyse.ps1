#Requires -Version 5.1
<#
.SYNOPSIS
    Install PyConlyse with conda environment and Poetry-managed dependencies

.DESCRIPTION
    This script creates a conda environment called 'pyconlyse39' and installs
    all required dependencies using Poetry from the poetry.lock file.

.PARAMETER EnvironmentName
    Name of the conda environment to create (default: pyconlyse39)

.PARAMETER Force
    Force recreation of environment if it already exists

.EXAMPLE
    .\install-pyconlyse.ps1
    
.EXAMPLE
    .\install-pyconlyse.ps1 -Force
    
.EXAMPLE
    .\install-pyconlyse.ps1 -EnvironmentName "my_pyconlyse"
#>

param(
    [string]$EnvironmentName = "pyconlyse39",
    [switch]$Force
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
$Green = "Green"
$Yellow = "Yellow" 
$Red = "Red"
$Cyan = "Cyan"

function Write-Status {
    param([string]$Message, [string]$Color = "White")
    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] $Message" -ForegroundColor $Color
}

function Test-CommandExists {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Install-Poetry {
    param([string]$PythonPath)
    
    Write-Status "Installing Poetry in conda environment..." -Color $Cyan
    
    # Install poetry using pip in the conda environment
    & $PythonPath -m pip install poetry
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Poetry"
    }
    
    Write-Status "Poetry installed successfully" -Color $Green
}

# Main installation process
try {
    Write-Status "Starting PyConlyse installation..." -Color $Green
    Write-Status "Target environment: $EnvironmentName" -Color $Cyan
    
    # Check if conda is available
    if (-not (Test-CommandExists "conda")) {
        Write-Status "ERROR: conda command not found. Please install Anaconda or Miniconda first." -Color $Red
        Write-Status "Download from: https://docs.conda.io/en/latest/miniconda.html" -Color $Yellow
        exit 1
    }
    
    Write-Status "Found conda: $(conda --version)" -Color $Green
    
    # Check if we're in the right directory
    if (-not (Test-Path "pyproject.toml")) {
        Write-Status "ERROR: pyproject.toml not found. Please run this script from the pyconlyse root directory." -Color $Red
        exit 1
    }
    
    if (-not (Test-Path "poetry.lock")) {
        Write-Status "ERROR: poetry.lock not found. Please run 'poetry lock' first." -Color $Red
        exit 1
    }
    
    # Check if environment already exists
    $envList = conda env list --json | ConvertFrom-Json
    $existingEnv = $envList.envs | Where-Object { $_ -like "*$EnvironmentName*" }
    
    if ($existingEnv -and -not $Force) {
        Write-Status "Environment '$EnvironmentName' already exists. Use -Force to recreate it." -Color $Yellow
        Write-Status "Existing environment path: $existingEnv" -Color $Yellow
        
        # Ask user if they want to continue
        $response = Read-Host "Continue with existing environment? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            Write-Status "Installation cancelled." -Color $Yellow
            exit 0
        }
    }
    elseif ($existingEnv -and $Force) {
        Write-Status "Removing existing environment '$EnvironmentName'..." -Color $Yellow
        conda env remove -n $EnvironmentName --yes
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to remove existing environment"
        }
    }
    
    # Create conda environment with Python 3.9
    if (-not $existingEnv -or $Force) {
        Write-Status "Creating conda environment '$EnvironmentName' with Python 3.9..." -Color $Cyan
        conda create -n $EnvironmentName python=3.9 --yes
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create conda environment"
        }
        
        Write-Status "Conda environment created successfully" -Color $Green
    }
    
    # Get the path to the conda environment's Python
    $condaEnvPath = conda info --envs | Select-String $EnvironmentName | ForEach-Object { ($_ -split '\s+')[-1] }
    
    if (-not $condaEnvPath) {
        throw "Could not find path for conda environment '$EnvironmentName'"
    }
    
    $pythonPath = Join-Path $condaEnvPath "python.exe"
    $pipPath = Join-Path $condaEnvPath "Scripts\pip.exe"
    
    if (-not (Test-Path $pythonPath)) {
        throw "Python executable not found at: $pythonPath"
    }
    
    Write-Status "Using Python: $pythonPath" -Color $Cyan
    
    # Install poetry if not already installed
    Write-Status "Checking for Poetry installation..." -Color $Cyan
    $poetryInstalled = $false
    
    try {
        & $pythonPath -m poetry --version | Out-Null
        $poetryInstalled = $true
        Write-Status "Poetry is already installed" -Color $Green
    }
    catch {
        Install-Poetry -PythonPath $pythonPath
        $poetryInstalled = $true
    }
    
    if (-not $poetryInstalled) {
        throw "Failed to install or verify Poetry"
    }
    
    # Configure Poetry to use conda environment
    Write-Status "Configuring Poetry to use conda environment..." -Color $Cyan
    
    # Set Poetry to use the conda environment
    & $pythonPath -m poetry env use $pythonPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Status "Warning: Could not configure Poetry environment. Continuing..." -Color $Yellow
    }
    
    # Install dependencies using Poetry
    Write-Status "Installing project dependencies with Poetry..." -Color $Cyan
    Write-Status "This may take several minutes..." -Color $Yellow
    
    # Install dependencies from poetry.lock
    & $pythonPath -m poetry install --no-dev
    
    if ($LASTEXITCODE -ne 0) {
        Write-Status "Warning: Poetry install failed. Trying with pip..." -Color $Yellow
        
        # Fallback: Export dependencies and install with pip
        Write-Status "Exporting dependencies to requirements.txt..." -Color $Cyan
        & $pythonPath -m poetry export --without-hashes -o requirements.txt
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Installing dependencies with pip..." -Color $Cyan
            & $pipPath install -r requirements.txt
            
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install dependencies with pip"
            }
            
            # Clean up
            Remove-Item requirements.txt -ErrorAction SilentlyContinue
        }
        else {
            throw "Failed to export dependencies"
        }
    }
    
    # Set environment variable for pyconlyse
    Write-Status "Setting PYCONLYSE_ENV environment variable..." -Color $Cyan
    [Environment]::SetEnvironmentVariable("PYCONLYSE_ENV", $EnvironmentName, [EnvironmentVariableTarget]::User)
    $env:PYCONLYSE_ENV = $EnvironmentName
    
    # Verify installation
    Write-Status "Verifying installation..." -Color $Cyan
    
    $verificationScript = @"
import sys
import importlib
print(f"Python version: {sys.version}")

# Test key packages
packages_to_test = [
    'PyQt5',
    'taurus',
    'numpy',
    'matplotlib',
    'pytango',
    'pyqtgraph'
]

failed_imports = []
for package in packages_to_test:
    try:
        importlib.import_module(package)
        print(f"✓ {package}")
    except ImportError as e:
        print(f"✗ {package}: {e}")
        failed_imports.append(package)

if failed_imports:
    print(f"\\nWarning: {len(failed_imports)} packages failed to import")
    sys.exit(1)
else:
    print("\\nAll key packages imported successfully!")
    sys.exit(0)
"@
    
    $verificationScript | & $pythonPath -
    
    if ($LASTEXITCODE -ne 0) {
        Write-Status "Warning: Some packages may not have installed correctly" -Color $Yellow
    }
    else {
        Write-Status "Installation verification passed!" -Color $Green
    }
    
    # Success message
    Write-Status "" 
    Write-Status "=== PyConlyse Installation Complete! ===" -Color $Green
    Write-Status ""
    Write-Status "Environment name: $EnvironmentName" -Color $Cyan
    Write-Status "Python path: $pythonPath" -Color $Cyan
    Write-Status "Environment variable PYCONLYSE_ENV set to: $EnvironmentName" -Color $Cyan
    Write-Status ""
    Write-Status "To activate the environment manually:" -Color $Yellow
    Write-Status "    conda activate $EnvironmentName" -Color $Yellow
    Write-Status ""
    Write-Status "To run PyConlyse GUI:" -Color $Yellow
    Write-Status "    conda activate $EnvironmentName" -Color $Yellow
    Write-Status "    python main_app/main_gui.py" -Color $Yellow
    Write-Status ""
    Write-Status "To run Simple GUI:" -Color $Yellow
    Write-Status "    conda activate $EnvironmentName" -Color $Yellow
    Write-Status "    python main_app/ui/simple_main_window.py" -Color $Yellow
    Write-Status ""
    
}
catch {
    Write-Status "ERROR: $($_.Exception.Message)" -Color $Red
    Write-Status "Installation failed!" -Color $Red
    exit 1
}