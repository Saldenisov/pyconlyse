[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell window."
}

$feature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
if ($feature.State -eq "Enabled") {
    Write-Host "Hyper-V is already enabled."
    return
}

if ($PSCmdlet.ShouldProcess("Microsoft-Hyper-V-All", "Enable the Windows Hyper-V feature")) {
    $result = Enable-WindowsOptionalFeature `
        -Online `
        -FeatureName Microsoft-Hyper-V-All `
        -All `
        -NoRestart

    $result | Select-Object FeatureName, Online, RestartNeeded
    if ($result.RestartNeeded) {
        Write-Host "Hyper-V is staged. Restart Windows before creating the VM."
    }
}
