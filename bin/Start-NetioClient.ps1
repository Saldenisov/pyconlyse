# Start-NetioClient.ps1
# PowerShell script to launch NETIO client with proper environment setup

param(
    [string]$DeviceName = "manip/sd1/pdu_sd1",
    [switch]$UsePoetry = $true,
    [switch]$UseConda = $false
)

Write-Host "=== NETIO Client Launcher (PowerShell) ===" -ForegroundColor Green
Write-Host "Device: $DeviceName"
Write-Host "Working Directory: $PWD"

# Change to pyconlyse directory
Set-Location "C:\dev\pyconlyse"

if ($UsePoetry) {
    Write-Host "Attempting to use Poetry environment..." -ForegroundColor Yellow
    
    # Check if poetry is available
    try {
        $poetryVersion = poetry --version
        Write-Host "Poetry found: $poetryVersion"
        
        Write-Host "Starting NETIO client with Poetry..." -ForegroundColor Cyan
        poetry run python start_netio_client.py $DeviceName
        
    } catch {
        Write-Host "Poetry failed: $_" -ForegroundColor Red
        $UsePoetry = $false
        $UseConda = $true
    }
}

if ($UseConda -and -not $UsePoetry) {
    Write-Host "Attempting to use Conda environment..." -ForegroundColor Yellow
    
    try {
        # Activate conda environment and run
        Write-Host "Activating conda environment pyconlyse39..." -ForegroundColor Cyan
        
        # Try to run with conda environment
        $condaPath = "C:\Users\denisov\miniconda3\envs\pyconlyse39\python.exe"
        
        if (Test-Path $condaPath) {
            Write-Host "Using conda python: $condaPath"
            & $condaPath start_netio_client.py $DeviceName
        } else {
            Write-Host "Conda environment not found at expected path" -ForegroundColor Red
            throw "Conda path not found"
        }
        
    } catch {
        Write-Host "Conda failed: $_" -ForegroundColor Red
        Write-Host "Trying system Python..." -ForegroundColor Yellow
        
        # Last resort - system Python
        python start_netio_client.py $DeviceName
    }
}

if (-not $UsePoetry -and -not $UseConda) {
    Write-Host "Using system Python as fallback..." -ForegroundColor Yellow
    python start_netio_client.py $DeviceName
}

Write-Host "NETIO client launch attempt completed." -ForegroundColor Green