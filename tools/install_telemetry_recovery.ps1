param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$taskName = 'ELYSE-Telemetry-Recovery'
$python = 'C:\Users\elyse\miniconda3\envs\pyconlyse312\python.exe'
$pythonw = 'C:\Users\elyse\miniconda3\envs\pyconlyse312\pythonw.exe'
$destination = 'F:\ELYSE_PostgreSQL\recovery'
$script = Join-Path $destination 'telemetry_recovery_watchdog.py'
if ($env:COMPUTERNAME -ne 'EVEREST') { throw 'Everest only' }
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { throw 'Recovery task already exists; review before changing it' }
if (-not $Apply) {
    [pscustomobject]@{Task=$taskName;Script=$script;Interval='1 minute';Mode='REVIEW_ONLY'} | ConvertTo-Json
    exit 0
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
if (Test-Path -LiteralPath $script) {
    Copy-Item -LiteralPath $script -Destination ($script + '.' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.bak')
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'telemetry_recovery_watchdog.py') -Destination $script
& $python -B $script --once --arm
if ($LASTEXITCODE -ne 0) { throw 'Arming refused; task not registered' }
$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('-B "' + $script + '" --once') -WorkingDirectory $destination
$periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$logon = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($periodic,$logon) -Settings $settings -Principal $principal -Description 'Recover only absent Everest telemetry receiver and existing archive DB; respect normal stops and F:\ELYSE_PostgreSQL\recovery\PAUSE. No XP or hardware commands.' | Out-Null
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State | ConvertTo-Json
