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
param()

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

Write-Host "✓ Running as Administrator" -ForegroundColor Green
Write-Host "✓ TANGO_ROOT found: $tangoRoot" -ForegroundColor Green
Write-Host "✓ Script location: $ScriptPath" -ForegroundColor Green
Write-Host

# Verify startup script exists
if (-not (Test-Path $TangoStartupScript)) {
    Write-Error "Startup script not found: $TangoStartupScript"
    exit 1
}

Write-Host "✓ Startup script found: $TangoStartupScript" -ForegroundColor Green
Write-Host

try {
    Write-Host "Creating Windows Task Scheduler job for Tango Infrastructure..." -ForegroundColor Yellow
    
    # Remove existing task if it exists
    $taskName = "TangoInfrastructureStartup"
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Removing existing task: $taskName" -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    # Create task action
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$TangoStartupScript`""
    
    # Create task trigger (at startup, with delay)
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = "PT30S"  # 30 second delay after boot
    
    # Create task settings
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartOnFailure -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    
    # Create task principal (run as SYSTEM)
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    
    # Register the task
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Automatically starts Tango Database and Starter on Windows boot"
    
    Write-Host "✓ Task Scheduler job created successfully!" -ForegroundColor Green
    Write-Host "  Task Name: $taskName" -ForegroundColor Cyan
    Write-Host "  Runs at: Windows startup (30 second delay)" -ForegroundColor Cyan
    Write-Host "  Script: $TangoStartupScript" -ForegroundColor Cyan
    Write-Host
    
    # Test the task
    Write-Host "Testing the scheduled task..." -ForegroundColor Yellow
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
    Write-Host "✓ 30-second delay after boot to allow system to stabilize" -ForegroundColor Green
    Write-Host "✓ Automatic restart if services crash (up to 3 attempts)" -ForegroundColor Green
    Write-Host "✓ Services run in background (minimized windows)" -ForegroundColor Green
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
    Write-Error "Failed to create scheduled task: $_"
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}