# Start Astor - Tango Administration Tool
# This script runs Astor using the old Tango installation's Java setup

Write-Host "=== Starting Astor - Tango Administration Tool ===" -ForegroundColor Green

# Set environment variables for our new Tango installation
$env:TANGO_ROOT = "C:\dev\tango-install"
$env:TANGO_HOST = "10.20.30.202:10000"

Write-Host "TANGO_ROOT: $env:TANGO_ROOT" -ForegroundColor Cyan
Write-Host "TANGO_HOST: $env:TANGO_HOST" -ForegroundColor Cyan

# Path to the old Tango installation for Java applications
$OldTangoRoot = "C:\dev\OLDtango\tango"
$JavaRoot = "$OldTangoRoot\share\tango\java"
$AstorJar = "$JavaRoot\Astor-6.7.0.jar"

# Check if Astor jar exists
if (-not (Test-Path $AstorJar)) {
    Write-Host "ERROR: Astor jar file not found at: $AstorJar" -ForegroundColor Red
    exit 1
}

Write-Host "Found Astor jar: $AstorJar" -ForegroundColor Green

# Try to find Java executable
$JavaPaths = @(
    "C:\Program Files\Java\*\bin\javaw.exe",
    "C:\Program Files (x86)\Java\*\bin\javaw.exe",
    "${env:JAVA_HOME}\bin\javaw.exe",
    "javaw.exe"
)

$JavaExe = $null
foreach ($path in $JavaPaths) {
    $found = Get-ChildItem $path -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $JavaExe = $found.FullName
        break
    }
}

if (-not $JavaExe) {
    # Try to find java in PATH
    try {
        $JavaExe = (Get-Command javaw -ErrorAction Stop).Source
    } catch {
        Write-Host "ERROR: Java not found. Please install Java to run Astor." -ForegroundColor Red
        Write-Host "You can download Java from: https://www.oracle.com/java/technologies/downloads/" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "Using Java: $JavaExe" -ForegroundColor Green

# Set up classpath with all necessary JAR files
$ClassPath = @(
    "$JavaRoot\Astor-6.7.0.jar",
    "$JavaRoot\JTango-9.0.7.jar",
    "$JavaRoot\ATKCore-9.1.13.jar",
    "$JavaRoot\ATKWidget-9.1.13.jar",
    "$JavaRoot\log4j-1.2.15.jar"
) -join ";"

Write-Host "Setting up classpath..." -ForegroundColor Cyan
Write-Host "Starting Astor application..." -ForegroundColor Green

# Start Astor
try {
    $Arguments = @(
        "-mx128m",
        "-DTANGO_HOST=$env:TANGO_HOST",
        "-cp", $ClassPath,
        "admin.astor.Astor"
    )
    
    Start-Process -FilePath $JavaExe -ArgumentList $Arguments -WindowStyle Normal
    Write-Host "Astor started successfully!" -ForegroundColor Green
    
} catch {
    Write-Host "ERROR: Failed to start Astor: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "Astor should now be starting..." -ForegroundColor Yellow