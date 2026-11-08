[CmdletBinding()]
param(
    [string]$VmIPv4Address = '10.20.30.203',
    [string]$ResultRoot = 'C:\ProgramData\ELYSE-HDBPP'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell.'
}

New-Item -ItemType Directory -Path $ResultRoot -Force | Out-Null
$transcriptPath = Join-Path $ResultRoot 'mariadb-provisioning.log'
$resultPath = Join-Path $ResultRoot 'mariadb-provisioning-result.json'
$provisioner = Join-Path $PSScriptRoot 'New-HdbppMariaDbInstance.ps1'

Start-Transcript -LiteralPath $transcriptPath -Force | Out-Null
try {
    & $provisioner `
        -VmIPv4Address $VmIPv4Address `
        -GenerateCredentials `
        -StartService `
        -Confirm:$false
    [ordered]@{
        Success = $true
        CompletedAt = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding utf8
}
catch {
    [ordered]@{
        Success = $false
        CompletedAt = (Get-Date).ToUniversalTime().ToString('o')
        Error = $_.Exception.Message
        Position = $_.InvocationInfo.PositionMessage
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding utf8
    Write-Error $_
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
