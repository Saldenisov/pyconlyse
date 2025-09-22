# Simple Tango Database test

Write-Host "=== Simple Database Test ===" -ForegroundColor Yellow

# Set environment variables
$env:TANGO_ROOT = "C:\dev\tango-install"
$env:TANGO_HOST = "10.20.30.202:10000"

Write-Host "TANGO_ROOT: $env:TANGO_ROOT"
Write-Host "TANGO_HOST: $env:TANGO_HOST"

# Check if database executable exists
$DatabasePath = "C:\dev\tango-install\bin\Databaseds.exe"
if (Test-Path $DatabasePath) {
    Write-Host "✓ Database executable found" -ForegroundColor Green
} else {
    Write-Host "✗ Database executable NOT found" -ForegroundColor Red
    exit 1
}

# Check required DLLs
Write-Host "Checking DLLs:"
$dlls = @("tango.dll", "libmariadb.dll")
foreach ($dll in $dlls) {
    if (Test-Path "C:\dev\tango-install\bin\$dll") {
        Write-Host "✓ $dll found" -ForegroundColor Green
    } else {
        Write-Host "✗ $dll missing" -ForegroundColor Red
    }
}

# Try starting database manually in the current window to see any errors
Write-Host ""
Write-Host "Attempting to start database (this will show any errors):" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop if it hangs"

try {
    Set-Location "C:\dev\tango-install\bin"
    & .\Databaseds.exe 2 -ORBendPoint giop:tcp::10000 -poolSize 3
} catch {
    Write-Host "Error starting database: $($_.Exception.Message)" -ForegroundColor Red
}