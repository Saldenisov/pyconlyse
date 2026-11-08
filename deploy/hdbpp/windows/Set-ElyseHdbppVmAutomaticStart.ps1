[CmdletBinding()]
param(
    [string]$VmName = 'ELYSE-HDBPP',
    [string]$ResultPath = 'C:\ProgramData\ELYSE-HDBPP\vm-startup-policy.json'
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell.'
}

$vm = Get-VM -Name $VmName -ErrorAction Stop
Set-VM -VM $vm `
    -AutomaticStartAction Start `
    -AutomaticStartDelay 30 `
    -AutomaticStopAction ShutDown

$vm = Get-VM -Name $VmName
$result = [ordered]@{
    Timestamp = (Get-Date).ToUniversalTime().ToString('o')
    Name = $vm.Name
    State = $vm.State.ToString()
    AutomaticStartAction = $vm.AutomaticStartAction.ToString()
    AutomaticStartDelay = $vm.AutomaticStartDelay
    AutomaticStopAction = $vm.AutomaticStopAction.ToString()
}
$result | ConvertTo-Json | Set-Content -LiteralPath $ResultPath -Encoding ascii
$result
