#Requires -Version 5.0
<#
.SYNOPSIS
    Starts the PYCONLYSE Tango infrastructure with proper DeviceServer management via Astor.

.DESCRIPTION
    This script starts the Tango infrastructure components in the correct order:
    1. Tango Database
    2. Main Control GUI
    3. Tango Starter (for DeviceServer management)
    4. Astor (DeviceServer manager GUI)
    5. Jive (optional Tango GUI)
    
    Instead of manually starting DeviceServers, this script relies on Astor to manage them
    automatically based on the Tango database configuration.

.PARAMETER WaitTime
    Time to wait between starting services (default: 5 seconds)

.PARAMETER SkipJive
    Skip starting the Jive GUI

.PARAMETER LogLevel
    Logging level: Info, Warning, Error (default: Info)

.EXAMPLE
    .\Start-TangoInfrastructure.ps1
    
.EXAMPLE
    .\Start-TangoInfrastructure.ps1 -WaitTime 10 -SkipJive
#>

[CmdletBinding()]
param(
    [int]$WaitTime = 5,
    [switch]$SkipJive,
    [ValidateSet('Info', 'Warning', 'Error')]
    [string]$LogLevel = 'Info'
)

# Script configuration
$ErrorActionPreference = 'Stop'
$InformationPreference = 'Continue'

# Define paths and logging
$ScriptPath = $PSScriptRoot
$LogFile = Join-Path $ScriptPath "tango_startup.log"
$StartTime = Get-Date

# Color scheme for output
$Colors = @{
    Header    = 'Green'
    Step      = 'Yellow'
    Success   = 'Green'
    Warning   = 'Yellow'
    Error     = 'Red'
    Info      = 'Cyan'
}

function Write-LogMessage {
    param(
        [string]$Message,
        [ValidateSet('Info', 'Warning', 'Error', 'Success')]
        [string]$Level = 'Info'
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    # Write to log file
    Add-Content -Path $LogFile -Value $logEntry
    
    # Write to console with colors
    $color = $Colors[$Level]
    if (-not $color) { $color = 'White' }
    
    Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Test-EnvironmentVariable {
    param([string]$VarName)
    
    $value = [Environment]::GetEnvironmentVariable($VarName)
    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-LogMessage "Environment variable '$VarName' is not defined!" -Level Error
        throw "Missing environment variable: $VarName"
    }
    
    Write-LogMessage "Environment variable '$VarName' = '$value'" -Level Info
    return $value
}

function Start-TangoService {
    param(
        [string]$Name,
        [string]$Command,
        [string]$Arguments = "",
        [switch]$Minimized,
        [int]$WaitSeconds = 0
    )
    
    Write-LogMessage "Starting $Name..." -Level Step
    
    try {
        $processArgs = @{
            FilePath = $Command
            WindowStyle = if ($Minimized) { 'Minimized' } else { 'Normal' }
        }
        
        if ($Arguments) {
            $processArgs.ArgumentList = $Arguments.Split(' ')
        }
        
        $process = Start-Process @processArgs -PassThru
        Write-LogMessage "$Name started successfully (PID: $($process.Id))" -Level Success
        
        if ($WaitSeconds -gt 0) {
            Write-LogMessage "Waiting $WaitSeconds seconds for $Name to initialize..." -Level Info
            Start-Sleep -Seconds $WaitSeconds
        }
        
        return $process
    }
    catch {
        Write-LogMessage "Failed to start $Name : $_" -Level Error
        throw
    }
}

function Test-TangoDatabase {
    param([int]$TimeoutSeconds = 30)
    
    Write-LogMessage "Testing Tango Database connection..." -Level Info
    
    $timeout = (Get-Date).AddSeconds($TimeoutSeconds)
    
    while ((Get-Date) -lt $timeout) {
        try {
            # Try to connect to Tango DB using tango_admin command if available
            # This is a simplified test - you might need to adjust based on your setup
            $env:PYTHONPATH = "$env:PYCONLYSE;$env:PYTHONPATH"
            
            # Test with a simple Python command
            $testCmd = @"
import sys
sys.path.append('$($env:PYCONLYSE)')
try:
    from tango import Database
    db = Database()
    db.get_info()
    print('OK')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)
"@
            
            $result = & python -c $testCmd 2>&1
            if ($result -eq 'OK') {
                Write-LogMessage "Tango Database connection successful" -Level Success
                return $true
            }
        }
        catch {
            # Continue trying
        }
        
        Start-Sleep -Seconds 2
    }
    
    Write-LogMessage "Tango Database connection test timed out" -Level Warning
    return $false
}

# Main script execution
try {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor $Colors.Header
    Write-Host "PYCONLYSE - Tango Infrastructure Startup" -ForegroundColor $Colors.Header
    Write-Host "=" * 60 -ForegroundColor $Colors.Header
    Write-Host "`n" -NoNewline
    
    Write-LogMessage "Starting Tango infrastructure startup sequence" -Level Info
    Write-LogMessage "Script path: $ScriptPath" -Level Info
    Write-LogMessage "Log file: $LogFile" -Level Info
    
    # Validate environment variables
    Write-LogMessage "Validating environment variables..." -Level Step
    $tangoRoot = Test-EnvironmentVariable "TANGO_ROOT"
    $pyconlyse = Test-EnvironmentVariable "PYCONLYSE"
    $anaconda = Test-EnvironmentVariable "ANACONDA"
    # Set default environment if not specified
    $pyconlyseEnv = [Environment]::GetEnvironmentVariable("PYCONLYSE_ENV")
    if ([string]::IsNullOrWhiteSpace($pyconlyseEnv)) {
        $pyconlyseEnv = "pyconlyse39"
        Write-LogMessage "Using default conda environment: $pyconlyseEnv" -Level Info
    } else {
        Write-LogMessage "PYCONLYSE_ENV = $pyconlyseEnv" -Level Info
    }
    
    # Store started processes for cleanup if needed
    $startedProcesses = @()
    
    # Step 1: Start Tango Database
    $dbProcess = Start-TangoService -Name "Tango Database" -Command "cmd" -Arguments "/c `"$tangoRoot\bin\start-db.bat`"" -WaitSeconds $WaitTime
    $startedProcesses += $dbProcess
    
    # Test database connectivity
    if (-not (Test-TangoDatabase)) {
        Write-LogMessage "Warning: Could not verify Tango Database connectivity" -Level Warning
    }
    
    # Step 2: Start Main Control
    $mainCtrlProcess = Start-TangoService -Name "Main Control GUI" -Command "cmd" -Arguments "/c `"$pyconlyse\bin\start_main_ctrl.cmd`"" -WaitSeconds $WaitTime
    $startedProcesses += $mainCtrlProcess
    
    # Step 3: Start Tango Starter (critical for Astor DeviceServer management)
    $starterProcess = Start-TangoService -Name "Tango Starter (everest)" -Command "$tangoRoot\bin\Starter.exe" -Arguments "everest" -WaitSeconds 3
    $startedProcesses += $starterProcess
    
    # Step 4: Start Astor (DeviceServer Manager)
    $astorProcess = Start-TangoService -Name "Astor DeviceServer Manager" -Command "cmd" -Arguments "/c `"$tangoRoot\bin\start-astor.bat`"" -WaitSeconds 2
    $startedProcesses += $astorProcess
    
    # Step 5: Start Jive (optional)
    if (-not $SkipJive) {
        $jiveProcess = Start-TangoService -Name "Jive GUI" -Command "cmd" -Arguments "/c `"$tangoRoot\bin\start-jive.bat`"" -WaitSeconds 1
        $startedProcesses += $jiveProcess
    }
    
    # Final status
    $duration = (Get-Date) - $StartTime
    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor $Colors.Success
    Write-LogMessage "Tango infrastructure startup completed successfully in $([math]::Round($duration.TotalSeconds, 2)) seconds" -Level Success
    Write-Host "=" * 60 -ForegroundColor $Colors.Success
    
    Write-Host "`nNext Steps:" -ForegroundColor $Colors.Info
    Write-Host "1. Open Astor GUI to configure and start DeviceServers automatically" -ForegroundColor White
    Write-Host "2. Use the Main Control GUI to manage device clients" -ForegroundColor White
    Write-Host "3. Check the log file: $LogFile" -ForegroundColor White
    Write-Host "`nStarted processes:" -ForegroundColor $Colors.Info
    
    foreach ($proc in $startedProcesses) {
        if (-not $proc.HasExited) {
            Write-Host "  - PID $($proc.Id): $($proc.ProcessName)" -ForegroundColor White
        }
    }
    
    Write-Host "`nIMPORTANT: DeviceServers should now be managed through Astor, not manual batch files!" -ForegroundColor $Colors.Warning
    
}
catch {
    Write-LogMessage "FATAL ERROR during startup: $_" -Level Error
    Write-LogMessage "Stack trace: $($_.ScriptStackTrace)" -Level Error
    
    Write-Host "`nStartup failed! Check the log file for details: $LogFile" -ForegroundColor $Colors.Error
    
    # Cleanup on failure (optional)
    Write-Host "Would you like to terminate any started processes? (y/N): " -ForegroundColor $Colors.Warning -NoNewline
    $response = Read-Host
    
    if ($response -eq 'y' -or $response -eq 'Y') {
        foreach ($proc in $startedProcesses) {
            if (-not $proc.HasExited) {
                try {
                    Write-LogMessage "Terminating process $($proc.Id) ($($proc.ProcessName))" -Level Info
                    $proc.Kill()
                }
                catch {
                    Write-LogMessage "Could not terminate process $($proc.Id): $_" -Level Warning
                }
            }
        }
    }
    
    exit 1
}