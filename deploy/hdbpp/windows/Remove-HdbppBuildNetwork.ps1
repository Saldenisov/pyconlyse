[CmdletBinding()]
param(
    [string]$VmName = 'ELYSE-HDBPP',
    [string]$BuildAdapterName = 'HDBPP-Build-NAT',
    [string]$ResultPath = 'C:\ProgramData\ELYSE-HDBPP\build-network-removed.json'
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell.'
}

$adapter = Get-VMNetworkAdapter -VMName $VmName -Name $BuildAdapterName -ErrorAction SilentlyContinue
if ($adapter) {
    Remove-VMNetworkAdapter -VMName $VmName -Name $BuildAdapterName -Confirm:$false
}

$resultDirectory = Split-Path -Parent $ResultPath
New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null

$result = [ordered]@{
    Timestamp = (Get-Date).ToString('o')
    VmName = $VmName
    VmState = (Get-VM -Name $VmName).State.ToString()
    RemovedAdapter = $BuildAdapterName
    RemainingAdapters = @(Get-VMNetworkAdapter -VMName $VmName | ForEach-Object {
        [ordered]@{
            Name = $_.Name
            SwitchName = $_.SwitchName
            MacAddress = $_.MacAddress
        }
    })
}

$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultPath -Encoding utf8
$result | ConvertTo-Json -Depth 5
