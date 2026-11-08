[CmdletBinding()]
param(
    [string]$VmName = 'ELYSE-HDBPP',
    [string]$BuildAdapterName = 'HDBPP-Build-NAT',
    [string]$BuildSwitchName = 'Default Switch',
    [string]$ResultPath = 'C:\ProgramData\ELYSE-HDBPP\post-install.json'
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell.'
}

$vm = Get-VM -Name $VmName

foreach ($dvd in @(Get-VMDvdDrive -VMName $VmName)) {
    if ($dvd.Path) {
        Set-VMDvdDrive -VMName $VmName `
            -ControllerNumber $dvd.ControllerNumber `
            -ControllerLocation $dvd.ControllerLocation `
            -Path $null
    }
}

$adapter = Get-VMNetworkAdapter -VMName $VmName -Name $BuildAdapterName -ErrorAction SilentlyContinue
if (-not $adapter) {
    Add-VMNetworkAdapter -VMName $VmName -Name $BuildAdapterName -SwitchName $BuildSwitchName
} elseif ($adapter.SwitchName -ne $BuildSwitchName) {
    Connect-VMNetworkAdapter -VMName $VmName -Name $BuildAdapterName -SwitchName $BuildSwitchName
}

$resultDirectory = Split-Path -Parent $ResultPath
New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null

$result = [ordered]@{
    Timestamp = (Get-Date).ToString('o')
    VmName = $VmName
    VmState = (Get-VM -Name $VmName).State.ToString()
    DvdPaths = @((Get-VMDvdDrive -VMName $VmName).Path)
    Adapters = @(Get-VMNetworkAdapter -VMName $VmName | ForEach-Object {
        [ordered]@{
            Name = $_.Name
            SwitchName = $_.SwitchName
            Status = $_.Status.ToString()
            MacAddress = $_.MacAddress
            IPAddresses = @($_.IPAddresses)
        }
    })
}

$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultPath -Encoding utf8
$result | ConvertTo-Json -Depth 5
