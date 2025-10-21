# Tango Windows Startup Script (PowerShell)
# Purpose: Start Tango Database and Starter services in separate persistent windows
# Updated: For C:\dev\tango-install installation
# Usage: tango_windows_startup.ps1 -HostName <hostname>

param(
    [string]$HostName = $env:COMPUTERNAME
)

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting Tango Control System Services" -ForegroundColor Cyan
Write-Host "Host: $HostName" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if TANGO_ROOT is defined
if (-not $env:TANGO_ROOT) {
    Write-Host "ERROR: TANGO_ROOT is not defined!" -ForegroundColor Red
    Write-Host "Please define TANGO_ROOT environment variable pointing to your Tango installation." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "TANGO_ROOT: $env:TANGO_ROOT" -ForegroundColor Green

# Check if TANGO_HOST is defined
if (-not $env:TANGO_HOST) {
    Write-Host "ERROR: TANGO_HOST is not defined!" -ForegroundColor Red
    Write-Host "Please define TANGO_HOST environment variable (e.g., localhost:10000)." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "TANGO_HOST: $env:TANGO_HOST" -ForegroundColor Green

# Check if database executable exists
$databasePath = Join-Path $env:TANGO_ROOT "bin\Databaseds.exe"
if (-not (Test-Path $databasePath)) {
    Write-Host "ERROR: Databaseds.exe not found in $env:TANGO_ROOT\bin\" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if starter executable exists
$starterPath = Join-Path $env:TANGO_ROOT "bin\Starter.exe"
$starterExists = Test-Path $starterPath

if (-not $starterExists) {
    Write-Host "WARNING: Starter.exe not found in $env:TANGO_ROOT\bin\" -ForegroundColor Yellow
    Write-Host "Will start only the Database service." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting Tango Database in separate window..." -ForegroundColor Yellow

# Start Database in separate PowerShell window
$dbScriptPath = Join-Path $env:TANGO_ROOT "bin\start-db-persistent.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "`"$dbScriptPath`"" -WindowStyle Normal

# Wait a moment for database to start
Start-Sleep -Seconds 3

# Start Starter if it exists
if ($starterExists) {
    Write-Host "Starting Tango Starter in separate window..." -ForegroundColor Yellow
    $starterScriptPath = Join-Path $env:TANGO_ROOT "bin\start-starter-persistent.ps1"
    Start-Process powershell -ArgumentList "-NoExit", "-File", "`"$starterScriptPath`"" -WindowStyle Normal
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Tango services startup initiated" -ForegroundColor Green
Write-Host "Database: Running in separate window" -ForegroundColor Green

if ($starterExists) {
    Write-Host "Starter: Running in separate window" -ForegroundColor Green
} else {
    Write-Host "Starter: Not available" -ForegroundColor Yellow
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Start pyconlyse server if this is the everest host
if ($HostName.ToLower() -eq "everest") {
    Write-Host ""
    Write-Host "Starting pyconlyse server (everest host only)..." -ForegroundColor Yellow
    
    # Check if pyconlyse server script exists
    $pyconlyseScriptPath = "C:\dev\pyconlyse\web\start_pyconlyse_server.py"
    if (Test-Path $pyconlyseScriptPath) {
        # Start pyconlyse server in separate PowerShell window
        $pyconlyseArgs = @(
            "-NoExit",
            "-Command",
            "cd 'C:\dev\pyconlyse\web'; python start_pyconlyse_server.py"
        )
        Start-Process powershell -ArgumentList $pyconlyseArgs -WindowStyle Normal
        Write-Host "Pyconlyse server: Started in separate window" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Pyconlyse server script not found at $pyconlyseScriptPath" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "Pyconlyse server: Skipped (not everest host)" -ForegroundColor Yellow
}

Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Keep this window open briefly to show status
Write-Host "Press Enter to close this startup window..." -ForegroundColor Gray
Read-Host
