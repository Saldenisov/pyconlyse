#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Sets up Tango Database and Starter to automatically start on Windows boot.

.DESCRIPTION
    This script creates Windows Task Scheduler jobs to automatically start:
    1. Tango Database on system startup
    2. Tango Starter after Database is ready
    
    These will run as background services when Windows starts.

.EXAMPLE
    .\setup_tango_windows_startup.ps1
    
.NOTES
    Must be run as Administrator to create system startup tasks.
#>

[CmdletBinding()]
param(
    [ValidateRange(0, 300)]
    [int]$StartupDelaySeconds = 5,
    [ValidateSet("headless")]
    [string]$LaunchMode = "headless",
    [string]$PythonExecutable = "",
    [switch]$Apply,
    [switch]$StartNow
)

# Script configuration
$ErrorActionPreference = 'Stop'
$InformationPreference = 'Continue'

# Paths
$ScriptPath = $PSScriptRoot
$TangoStartupScript = Join-Path $ScriptPath "tango_windows_startup.cmd"

Write-Host "=" * 60 -ForegroundColor Green
Write-Host "TANGO INFRASTRUCTURE - Windows Startup Setup" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green
Write-Host

if (-not $Apply) {
    Write-Host "Dry run. No scheduled task is created, replaced, or started." -ForegroundColor Yellow
    Write-Host "Use -Apply to change the task and -StartNow to start it afterwards." -ForegroundColor Yellow
    exit 0
}

# Verify we're running as administrator
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run as Administrator to create system startup tasks!"
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Red
    exit 1
}

# Verify TANGO_ROOT environment variable
$tangoRoot = [Environment]::GetEnvironmentVariable("TANGO_ROOT", "Machine")
if (-not $tangoRoot -or -not (Test-Path $tangoRoot)) {
    Write-Error "TANGO_ROOT environment variable is not set or path doesn't exist!"
    Write-Host "Please set TANGO_ROOT system environment variable to your Tango installation." -ForegroundColor Red
    exit 1
}

if (-not $PythonExecutable) {
    $PythonExecutable = [Environment]::GetEnvironmentVariable("PYCONLYSE_PYTHON", "Machine")
}
if (-not $PythonExecutable -or -not [IO.Path]::IsPathFullyQualified($PythonExecutable) -or -not (Test-Path $PythonExecutable)) {
    Write-Error "A valid absolute PYCONLYSE_PYTHON is required for the SYSTEM task."
    exit 1
}

Write-Host "✓ Running as Administrator" -ForegroundColor Green
Write-Host "✓ TANGO_ROOT found: $tangoRoot" -ForegroundColor Green
Write-Host "✓ PYCONLYSE_PYTHON found: $PythonExecutable" -ForegroundColor Green
Write-Host "✓ Script location: $ScriptPath" -ForegroundColor Green
Write-Host

# Verify startup script exists
if (-not (Test-Path $TangoStartupScript)) {
    Write-Error "Startup script not found: $TangoStartupScript"
    exit 1
}

Write-Host "✓ Startup script found: $TangoStartupScript" -ForegroundColor Green
Write-Host

$previousPythonExecutable = [Environment]::GetEnvironmentVariable("PYCONLYSE_PYTHON", "Machine")
$pythonEnvironmentChanged = $false

try {
    Write-Host "Creating Windows Task Scheduler job for Tango Infrastructure..." -ForegroundColor Yellow
    if ($previousPythonExecutable -ne $PythonExecutable) {
        [Environment]::SetEnvironmentVariable("PYCONLYSE_PYTHON", $PythonExecutable, "Machine")
        $pythonEnvironmentChanged = $true
        Write-Host "✓ Persisted PYCONLYSE_PYTHON for the SYSTEM task" -ForegroundColor Green
    }
    
    # Remove existing task if it exists
    $taskName = "TangoInfrastructureStartup"
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    $backupXml = $null
    if ($existingTask) {
        $backupXml = Export-ScheduledTask -TaskName $taskName
        Write-Host "Removing existing task: $taskName" -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    # Create task action
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$TangoStartupScript`""
    
    # This installer is intentionally headless: Session 0 cannot host visible
    # Windows Terminal tabs. Configure any interactive Starter task separately.
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $trigger.Delay = "PT${StartupDelaySeconds}S"
    
    # Create task settings
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartOnFailure -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    
    # Register the task
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Automatically starts Tango Database and Starter on Windows boot"
    
    Write-Host "✓ Task Scheduler job created successfully!" -ForegroundColor Green
    Write-Host "  Task Name: $taskName" -ForegroundColor Cyan
    Write-Host "  Mode: $LaunchMode" -ForegroundColor Cyan
    Write-Host "  Runs after: $StartupDelaySeconds second delay" -ForegroundColor Cyan
    Write-Host "  Script: $TangoStartupScript" -ForegroundColor Cyan
    Write-Host
    
    if (-not $StartNow) {
        Write-Host "Task registered. It was not started; use -StartNow after operator review." -ForegroundColor Yellow
        return
    }

    Write-Host "Starting the scheduled task..." -ForegroundColor Yellow
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 5
    
    # Check task status
    $task = Get-ScheduledTask -TaskName $taskName
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
    
    Write-Host "Task Status:" -ForegroundColor Cyan
    Write-Host "  State: $($task.State)" -ForegroundColor White
    Write-Host "  Last Run Time: $($taskInfo.LastRunTime)" -ForegroundColor White
    Write-Host "  Last Result: $($taskInfo.LastTaskResult)" -ForegroundColor White
    Write-Host
    
    if ($taskInfo.LastTaskResult -eq 0) {
        Write-Host "✓ Task executed successfully!" -ForegroundColor Green
    } else {
        Write-Warning "Task may have encountered issues (exit code: $($taskInfo.LastTaskResult))"
        Write-Host "Check the log file for details: $ScriptPath\tango_windows_startup.log" -ForegroundColor Yellow
    }
    
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "SETUP COMPLETED" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host
    Write-Host "What happens now:" -ForegroundColor Cyan
    Write-Host "✓ Tango Database and Starter will automatically start on Windows boot" -ForegroundColor Green
    Write-Host "✓ $StartupDelaySeconds-second delay; passive Tango probes gate startup" -ForegroundColor Green
    Write-Host "✓ Automatic restart if services crash (up to 3 attempts)" -ForegroundColor Green
    Write-Host "✓ Headless Session 0 mode; visible Windows Terminal tabs are not expected" -ForegroundColor Yellow
    Write-Host
    Write-Host "Log files location:" -ForegroundColor Cyan
    Write-Host "  $ScriptPath\tango_db_startup.log" -ForegroundColor White
    Write-Host "  $ScriptPath\tango_starter_startup.log" -ForegroundColor White
    Write-Host "  $ScriptPath\tango_windows_startup.log" -ForegroundColor White
    Write-Host
    Write-Host "To test now: Restart Windows and check if Tango is running automatically." -ForegroundColor Yellow
    Write-Host "To remove: Run 'schtasks /delete /tn `"TangoInfrastructureStartup`" /f' as Administrator" -ForegroundColor Yellow
    Write-Host

} catch {
    if ($backupXml) {
        try {
            Register-ScheduledTask -TaskName $taskName -Xml $backupXml -Force | Out-Null
            Write-Warning "Restored previous task after setup failure."
        } catch {
            Write-Error "Could not restore previous task: $($_.Exception.Message)"
        }
    }
    if ($pythonEnvironmentChanged) {
        [Environment]::SetEnvironmentVariable("PYCONLYSE_PYTHON", $previousPythonExecutable, "Machine")
        Write-Warning "Restored previous machine PYCONLYSE_PYTHON after setup failure."
    }
    Write-Error "Failed to create scheduled task: $_"
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
