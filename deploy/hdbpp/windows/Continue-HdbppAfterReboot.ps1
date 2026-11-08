[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$vmScript = Join-Path $PSScriptRoot "New-ElyseHdbppVm.ps1"
$isoPath = "E:\ELYSE-Install\Ubuntu\ubuntu-24.04.4-live-server-amd64.iso"
$logDirectory = "E:\ELYSE-Install\HDBPP"
$logPath = Join-Path $logDirectory "hyperv-provision.log"

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
Start-Transcript -Path $logPath -Append | Out-Null
try {
    Set-Location $repositoryRoot
    & $vmScript `
        -UbuntuIsoPath $isoPath `
        -ExternalAdapterName "ELYSE" `
        -VmRoot "E:\ELYSE-VMs\HDBPP" `
        -StartVm `
        -Confirm:$false
}
finally {
    Stop-Transcript | Out-Null
}
