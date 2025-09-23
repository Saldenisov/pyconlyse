# =====================================================
# TANGO DATABASE - Windows Startup Service (PowerShell)
# This script starts Tango Database on Windows boot
# =====================================================

$ScriptDir = $PSScriptRoot
$LogFile = Join-Path $ScriptDir "tango_db_startup.log"

# Function to write log entries
function Write-Log {
    param($Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] $Message"
    Write-Host $LogEntry -ForegroundColor Cyan
    Add-Content -Path $LogFile -Value $LogEntry
}

Write-Log "Starting Tango Database service..."

# Set environment variables if not set
if (-not $env:TANGO_ROOT) {
    $env:TANGO_ROOT = "C:\dev\tango-install"
    Write-Log "Set TANGO_ROOT to: $env:TANGO_ROOT"
}

if (-not $env:TANGO_HOST) {
    $env:TANGO_HOST = "10.20.30.202:10000"
    Write-Log "Set TANGO_HOST to: $env:TANGO_HOST"
}

Write-Log "TANGO_ROOT: $env:TANGO_ROOT"
Write-Log "TANGO_HOST: $env:TANGO_HOST"

# Check if database is already running by checking port 10000
Write-Log "Checking if Tango Database is already running on port 10000..."

$Port10000InUse = Get-NetTCPConnection -LocalPort 10000 -ErrorAction SilentlyContinue
if ($Port10000InUse) {
    Write-Log "Tango Database appears to be already running on port 10000"
    Write-Host "Database is already running!" -ForegroundColor Green
    exit 0
}

# Check if the start-db.bat file exists
$StartDbPath = Join-Path $env:TANGO_ROOT "bin\start-db.bat"
if (-not (Test-Path $StartDbPath)) {
    Write-Log "ERROR: start-db.bat not found at: $StartDbPath"
    Write-Host "Error: start-db.bat not found!" -ForegroundColor Red
    exit 1
}

# Start the Tango Database
Write-Log "Starting Tango Database from: $StartDbPath"
Write-Host "Starting Tango Database in new window..." -ForegroundColor Green

# Start database in a new CMD window
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$StartDbPath`"" -WindowStyle Normal

# Wait a moment for startup
Write-Log "Waiting 10 seconds for database to start..."
Start-Sleep -Seconds 10

# Check if database started successfully
Write-Log "Verifying database startup..."
$Port10000InUse = Get-NetTCPConnection -LocalPort 10000 -ErrorAction SilentlyContinue
if ($Port10000InUse) {
    Write-Log "SUCCESS: Tango Database started successfully"
    Write-Host "Database started successfully!" -ForegroundColor Green
} else {
    Write-Log "WARNING: Tango Database may not have started properly (port 10000 not active)"
    Write-Host "Warning: Database may not have started properly" -ForegroundColor Yellow
}

Write-Log "Tango Database startup script completed"