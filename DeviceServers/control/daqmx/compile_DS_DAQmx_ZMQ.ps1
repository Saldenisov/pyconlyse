#Requires -Version 3.0
<#
.SYNOPSIS
    Compiles DS_DAQmx_ZMQ C# wrapper to executable for use with Astor.

.DESCRIPTION
    This script compiles the C# wrapper source code to create DS_DAQmx_ZMQ.exe
    that Astor can recognize and launch to start the Python device server.

.EXAMPLE
    .\compile_DS_DAQmx_ZMQ.ps1
#>

[CmdletBinding()]
param()

Write-Host "=====================================================" -ForegroundColor Green
Write-Host "DS_DAQmx_ZMQ C# Wrapper Compilation" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host

$ScriptPath = $PSScriptRoot
$SourceFile = Join-Path $ScriptPath "DS_DAQmx_ZMQ_wrapper.cs"
$OutputFile = Join-Path $ScriptPath "DS_DAQmx_ZMQ.exe"

# Check if source file exists
if (-not (Test-Path $SourceFile)) {
    Write-Error "Source file not found: $SourceFile"
    exit 1
}

Write-Host "✓ Source file found: $SourceFile" -ForegroundColor Green

# Try to find C# compiler
$CscPaths = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\Professional\MSBuild\Current\Bin\Roslyn\csc.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\Roslyn\csc.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\Roslyn\csc.exe",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\Roslyn\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

$CscPath = $null
foreach ($path in $CscPaths) {
    if (Test-Path $path) {
        $CscPath = $path
        break
    }
}

# Try using 'where' command as fallback
if (-not $CscPath) {
    try {
        $whereResult = & where csc 2>$null
        if ($whereResult -and (Test-Path $whereResult[0])) {
            $CscPath = $whereResult[0]
        }
    } catch {
        # Ignore error
    }
}

if (-not $CscPath) {
    Write-Error "C# compiler (csc.exe) not found!"
    Write-Host "Please install one of the following:" -ForegroundColor Yellow
    Write-Host "1. Visual Studio 2019/2022" -ForegroundColor White
    Write-Host "2. .NET Framework SDK" -ForegroundColor White
    Write-Host "3. .NET Core SDK" -ForegroundColor White
    Write-Host "" 
    Write-Host "Or use the batch file alternative if needed" -ForegroundColor White
    Write-Host "Press any key to continue..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "✓ C# compiler found: $CscPath" -ForegroundColor Green

try {
    Write-Host "Compiling..." -ForegroundColor Yellow
    
    # Compile the C# source
    & $CscPath /out:$OutputFile /target:exe $SourceFile
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Compilation failed with exit code: $LASTEXITCODE"
        exit 1
    }
    
    # Verify output file was created
    if (-not (Test-Path $OutputFile)) {
        Write-Error "Output file was not created: $OutputFile"
        exit 1
    }
    
    Write-Host ""
    Write-Host "✅ Compilation successful!" -ForegroundColor Green
    Write-Host "✅ Created: DS_DAQmx_ZMQ.exe" -ForegroundColor Green
    Write-Host ""
    
    # Show file info
    $fileInfo = Get-Item $OutputFile
    Write-Host "File Information:" -ForegroundColor Cyan
    Write-Host "  Path: $($fileInfo.FullName)" -ForegroundColor White
    Write-Host "  Size: $($fileInfo.Length) bytes" -ForegroundColor White
    Write-Host "  Created: $($fileInfo.CreationTime)" -ForegroundColor White
    Write-Host ""
    
    Write-Host "The executable is now ready for use with Astor!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Register device to Tango DB: python add_ds_DAQmx_zmq.py" -ForegroundColor White
    Write-Host "2. In Astor, refresh the device server list" -ForegroundColor White
    Write-Host "3. DS_DAQmx_ZMQ should now appear in the available servers" -ForegroundColor White
    Write-Host "4. You can test it manually: DS_DAQmx_ZMQ.exe 1_DAQMX_ZMQ_1" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Error "Compilation error: $_"
    Write-Host "Exception details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
