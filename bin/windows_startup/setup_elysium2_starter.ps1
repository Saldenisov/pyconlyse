# Update the existing Elysium2 boot task without changing server policies.
[CmdletBinding()]
param([switch]$Apply, [switch]$StartNow)

$ErrorActionPreference = 'Stop'
$taskName = 'Pyconlyse-Starter-Elysium2-Background'
$launcher = Join-Path $PSScriptRoot 'Start-PyconlyseStarter-Elysium2.ps1'
if (-not $Apply) {
    Write-Output "Dry run: update $taskName to run $launcher under SYSTEM with failure retries."
    exit 0
}
if ($env:COMPUTERNAME -ine 'elysium2') { throw 'This task belongs to Elysium2' }
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Launcher missing: $launcher" }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator rights are required to update the SYSTEM boot task'
}
$pythonExecutable = [Environment]::GetEnvironmentVariable('PYCONLYSE_PYTHON', 'Machine')
if (-not $pythonExecutable -or -not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw 'Machine PYCONLYSE_PYTHON is unavailable'
}
& $pythonExecutable -c 'import tango; import pyvisa_py'
if ($LASTEXITCODE -ne 0) {
    throw 'Runtime dependencies missing; install requirements-elysium2.in into PYCONLYSE_PYTHON'
}

$backupDirectory = Join-Path $env:ProgramData ('Pyconlyse\startup-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $backupDirectory 'task.xml') -Encoding Unicode
if ($task.State -eq 'Running') { throw 'Boot task is already running; stop its supervisor before changing settings' }
$principalId = $task.Principal.UserId
if ($principalId -notmatch '^S-1-') {
    $account = New-Object Security.Principal.NTAccount($principalId)
    $principalId = $account.Translate([Security.Principal.SecurityIdentifier]).Value
}
if ($principalId -ne 'S-1-5-18') { throw 'Unexpected boot task account' }
if (-not @($task.Triggers | Where-Object { $_.CimClass.CimClassName -eq 'MSFT_TaskBootTrigger' }).Count) {
    throw 'Existing task has no boot trigger'
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcher`"" `
    -WorkingDirectory $PSScriptRoot
$settings = $task.Settings
$settings.StartWhenAvailable = $true
$settings.DisallowStartIfOnBatteries = $false
$settings.StopIfGoingOnBatteries = $false
$settings.ExecutionTimeLimit = 'PT0S'
$settings.RestartCount = 10
$settings.RestartInterval = 'PT1M'
Set-ScheduledTask -TaskName $taskName -Action $action -Settings $settings | Out-Null
Enable-ScheduledTask -TaskName $taskName | Out-Null
Write-Output "Updated $taskName; rollback XML: $backupDirectory\task.xml"
if ($StartNow) { Start-ScheduledTask -TaskName $taskName }
