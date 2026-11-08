[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell window."
}

$hyperVGroup = Get-LocalGroup -SID "S-1-5-32-578"
$member = "EVEREST\elyse"
$existing = Get-LocalGroupMember -Group $hyperVGroup -ErrorAction Stop |
    Where-Object Name -eq $member
if (-not $existing) {
    Add-LocalGroupMember -Group $hyperVGroup -Member $member
}

Write-Host "Granted $member membership in $($hyperVGroup.Name)."
Write-Host "The permission applies to normal applications after sign-out/sign-in."

Start-Process `
    -FilePath "$env:SystemRoot\System32\vmconnect.exe" `
    -ArgumentList @("localhost", "ELYSE-HDBPP")
