[CmdletBinding(SupportsShouldProcess)]
param([switch]$Unregister)

$ErrorActionPreference = 'Stop'
$taskName = 'Avantes Gamma - Resume active acquisition'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($Unregister) {
    if ((Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue) -and
        $PSCmdlet.ShouldProcess($taskName, 'Unregister scheduled task')) {
        Unregister-ScheduledTask -TaskName $taskName -TaskPath '\' -Confirm:$false
    }
    return
}

$launcher = Join-Path $PSScriptRoot 'install_gamma_packages.ps1'
if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Gamma launcher not found: $launcher"
}

$powerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Launch -RecoverOnly' -f $launcher
$action = New-ScheduledTaskAction -Execute $powerShell -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

if ($PSCmdlet.ShouldProcess($taskName, "Register Gamma acquisition recovery at sign-in for $user")) {
    Register-ScheduledTask -TaskName $taskName -TaskPath '\' -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description 'Resume an interrupted Avantes Gamma acquisition at Windows sign-in.' -Force
}
