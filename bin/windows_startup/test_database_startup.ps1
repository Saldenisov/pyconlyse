# Test script to diagnose Tango Database startup issues

Write-Host "=== Tango Database Startup Diagnostics ===" -ForegroundColor Yellow

# Set environment variables
$env:TANGO_ROOT = "C:\dev\tango-install"
$env:TANGO_HOST = "10.20.30.202:10000"

Write-Host "Environment Variables:" -ForegroundColor Cyan
Write-Host "TANGO_ROOT: $env:TANGO_ROOT"
Write-Host "TANGO_HOST: $env:TANGO_HOST"
Write-Host ""

# Check if executables exist
$DatabasePath = "C:\dev\tango-install\bin\Databaseds.exe"
Write-Host "Checking executables:" -ForegroundColor Cyan
Write-Host "Database executable: $DatabasePath"
if (Test-Path $DatabasePath) {
    Write-Host "✓ Databaseds.exe exists" -ForegroundColor Green
    $FileInfo = Get-Item $DatabasePath
    Write-Host "  Size: $($FileInfo.Length) bytes"
    Write-Host "  Modified: $($FileInfo.LastWriteTime)"
} else {
    Write-Host "✗ Databaseds.exe NOT FOUND" -ForegroundColor Red
    exit 1
}

# Check DLL dependencies
Write-Host ""
Write-Host "Checking required DLLs:" -ForegroundColor Cyan
$RequiredDlls = @("tango.dll", "libmariadb.dll")
foreach ($dll in $RequiredDlls) {
    $DllPath = "C:\dev\tango-install\bin\$dll"
    if (Test-Path $DllPath) {
        Write-Host "✓ $dll exists" -ForegroundColor Green
    } else {
        Write-Host "✗ $dll NOT FOUND" -ForegroundColor Red
    }
}

# Check if port 10000 is already in use
Write-Host ""
Write-Host "Checking port 10000:" -ForegroundColor Cyan
$PortInUse = Get-NetTCPConnection -LocalPort 10000 -ErrorAction SilentlyContinue
if ($PortInUse) {
    Write-Host "⚠ Port 10000 is already in use:" -ForegroundColor Yellow
    $PortInUse | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State
} else {
    Write-Host "✓ Port 10000 is available" -ForegroundColor Green
}

# Try to run the database with help option to test basic functionality
Write-Host ""
Write-Host "Testing database executable:" -ForegroundColor Cyan
try {
    $Process = Start-Process -FilePath $DatabasePath -ArgumentList "--version" -Wait -PassThru -NoNewWindow -RedirectStandardOutput "temp_output.txt" -RedirectStandardError "temp_error.txt"
    
    if (Test-Path "temp_output.txt") {
        $Output = Get-Content "temp_output.txt" -Raw
        if ($Output) {
            Write-Host "✓ Database executable responds:" -ForegroundColor Green
            Write-Host $Output
        }
        Remove-Item "temp_output.txt" -ErrorAction SilentlyContinue
    }
    
    if (Test-Path "temp_error.txt") {
        $Error = Get-Content "temp_error.txt" -Raw
        if ($Error) {
            Write-Host "⚠ Error output:" -ForegroundColor Yellow
            Write-Host $Error
        }
        Remove-Item "temp_error.txt" -ErrorAction SilentlyContinue
    }
    
    Write-Host "Exit code: $($Process.ExitCode)"
    
} catch {
    Write-Host "✗ Failed to run database executable: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Diagnostics Complete ===" -ForegroundColor Yellow