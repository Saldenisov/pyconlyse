#Requires -Version 3.0
<#
.SYNOPSIS
    Compiles DS_Basler_camera C# wrapper to executable for use with Astor.

.DESCRIPTION
    This script compiles the C# wrapper source code to create DS_Basler_camera.exe
    that Astor can recognize and launch to start the Python device server.

.EXAMPLE
    .\compile_wrapper.ps1
#>

[CmdletBinding()]
param()

Write-Host "=====================================================" -ForegroundColor Green
Write-Host "DS_Basler_camera C# Wrapper Compilation" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host

$ScriptPath = $PSScriptRoot
$SourceFile = Join-Path $ScriptPath "DS_Basler_camera_wrapper.cs"
$OutputFile = Join-Path $ScriptPath "DS_Basler_camera.exe"

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
    Write-Host "1. Visual Studio 2019/2022 (Community, Professional, or Enterprise)" -ForegroundColor White
    Write-Host "2. .NET Framework SDK" -ForegroundColor White
    Write-Host "3. .NET Core SDK" -ForegroundColor White
    Write-Host "" 
    Write-Host "Or use the batch file alternative: DS_Basler_camera.bat" -ForegroundColor White
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
Write-Host "✅ Created: DS_Basler_camera.exe" -ForegroundColor Green
    
    # Also compile DS_LaserPointing if wrapper exists
    $LaserPointingSource = Join-Path $ScriptPath "DS_LaserPointing_wrapper.cs"
    $LaserPointingOutput = Join-Path $ScriptPath "DS_LaserPointing.exe"
    
    if (Test-Path $LaserPointingSource) {
        Write-Host "Compiling DS_LaserPointing_wrapper.cs..." -ForegroundColor Yellow
        & $CscPath /out:$LaserPointingOutput /target:exe $LaserPointingSource
        
        if ($LASTEXITCODE -eq 0 -and (Test-Path $LaserPointingOutput)) {
            Write-Host "✅ Created: DS_LaserPointing.exe" -ForegroundColor Green
        } else {
            Write-Warning "Failed to compile DS_LaserPointing_wrapper.cs"
        }
    }

    # Also compile DS_Netio_pdu if wrapper exists
    $NetioSource = Join-Path $ScriptPath "DS_Netio_pdu_wrapper.cs"
    $NetioOutput = Join-Path $ScriptPath "DS_Netio_pdu.exe"
    if (Test-Path $NetioSource) {
        Write-Host "Compiling DS_Netio_pdu_wrapper.cs..." -ForegroundColor Yellow
        & $CscPath /out:$NetioOutput /target:exe $NetioSource
        if ($LASTEXITCODE -eq 0 -and (Test-Path $NetioOutput)) {
            Write-Host "✅ Created: DS_Netio_pdu.exe" -ForegroundColor Green
        } else {
            Write-Warning "Failed to compile DS_Netio_pdu_wrapper.cs"
        }
    }

    # Also compile DS_iTest_PSU if wrapper exists
    $ITestSource = Join-Path $ScriptPath "DS_iTest_PSU_wrapper.cs"
    $ITestOutput = Join-Path $ScriptPath "DS_iTest_PSU.exe"
    if (Test-Path $ITestSource) {
        Write-Host "Compiling DS_iTest_PSU_wrapper.cs..." -ForegroundColor Yellow
        & $CscPath /out:$ITestOutput /target:exe $ITestSource
        if ($LASTEXITCODE -eq 0 -and (Test-Path $ITestOutput)) {
            Write-Host "✅ Created: DS_iTest_PSU.exe" -ForegroundColor Green
        } else {
            Write-Warning "Failed to compile DS_iTest_PSU_wrapper.cs"
        }
    }

    # Also compile DS_ML_Stability if wrapper exists
    $MLStabilitySource = Join-Path $ScriptPath "DS_ML_Stability_wrapper.cs"
    $MLStabilityOutput = Join-Path $ScriptPath "DS_ML_Stability.exe"
    if (Test-Path $MLStabilitySource) {
        Write-Host "Compiling DS_ML_Stability_wrapper.cs..." -ForegroundColor Yellow
        & $CscPath /out:$MLStabilityOutput /target:exe $MLStabilitySource
        if ($LASTEXITCODE -eq 0 -and (Test-Path $MLStabilityOutput)) {
            Write-Host "✅ Created: DS_ML_Stability.exe" -ForegroundColor Green
        } else {
            Write-Warning "Failed to compile DS_ML_Stability_wrapper.cs"
        }
    }

    # Also compile DS_OWIS_Aggregator if wrapper exists
    $OwisAggSource = Join-Path $ScriptPath "DS_OWIS_Aggregator_wrapper.cs"
    $OwisAggOutput = Join-Path $ScriptPath "DS_OWIS_Aggregator.exe"
    if (Test-Path $OwisAggSource) {
        Write-Host "Compiling DS_OWIS_Aggregator_wrapper.cs..." -ForegroundColor Yellow
        & $CscPath /out:$OwisAggOutput /target:exe $OwisAggSource
        if ($LASTEXITCODE -eq 0 -and (Test-Path $OwisAggOutput)) {
            Write-Host "✅ Created: DS_OWIS_Aggregator.exe" -ForegroundColor Green
        } else {
            Write-Warning "Failed to compile DS_OWIS_Aggregator_wrapper.cs"
        }
    }

    # Also compile DS_PSP if wrapper exists
    $PSPSource = Join-Path $ScriptPath "DS_PSP_wrapper.cs"
    $PSPOutput = Join-Path $ScriptPath "DS_PSP.exe"
    if (Test-Path $PSPSource) {
        Write-Host "Compiling DS_PSP_wrapper.cs..." -ForegroundColor Yellow
        & $CscPath /out:$PSPOutput /target:exe $PSPSource
        if ($LASTEXITCODE -eq 0 -and (Test-Path $PSPOutput)) {
            Write-Host "✅ Created: DS_PSP.exe" -ForegroundColor Green
        } else {
            Write-Warning "Failed to compile DS_PSP_wrapper.cs"
        }
    }
    
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
    Write-Host "1. In Astor, refresh the device server list" -ForegroundColor White
    Write-Host "2. DS_Basler_camera should now appear in the available servers" -ForegroundColor White
    Write-Host "3. You can test it manually: DS_Basler_camera.exe 1_Cam1_V0" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Error "Compilation error: $_"
    Write-Host "Exception details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")