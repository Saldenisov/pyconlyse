[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$VmIPv4Address = '10.20.30.203',
    [string]$ServiceName = 'MariaDB-HDBPP',
    [string]$DataRoot = 'D:\ELYSE-Archive\MariaDB',
    [string]$ResultRoot = 'C:\ProgramData\ELYSE-HDBPP'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell.'
}

$expectedDataRoot = [IO.Path]::GetFullPath('D:\ELYSE-Archive\MariaDB')
$resolvedDataRoot = [IO.Path]::GetFullPath($DataRoot)
if (-not [StringComparer]::OrdinalIgnoreCase.Equals($resolvedDataRoot, $expectedDataRoot)) {
    throw "Refusing unexpected data root '$resolvedDataRoot'."
}
if ($ServiceName -ne 'MariaDB-HDBPP') {
    throw "Refusing unexpected service '$ServiceName'."
}

$resultPath = Join-Path $ResultRoot 'mariadb-provisioning-result.json'
$credentialPath = Join-Path $ResultRoot 'mariadb-credentials.clixml'
if (Test-Path -LiteralPath $credentialPath) {
    throw 'Protected credentials already exist; this is not an incomplete bootstrap.'
}
if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
    throw 'Provisioning failure record is absent; refusing cleanup.'
}
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if ($result.Success -ne $false) {
    throw 'Provisioning record does not describe a failed attempt; refusing cleanup.'
}

$service = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'"
if (-not $service) {
    throw "Expected incomplete service '$ServiceName' was not found."
}
$expectedDefaults = '--defaults-file=D:\ELYSE-Archive\MariaDB\my.ini'
if ($service.PathName -notlike '*MariaDB 10.6\bin\mysqld.exe*' -or
    $service.PathName -notlike "*$expectedDefaults*") {
    throw "Service command line does not match the isolated HDB++ instance: $($service.PathName)"
}
if ($service.State -ne 'Stopped') {
    throw "Service is $($service.State), not the expected failed/stopped state."
}
if (Get-NetTCPConnection -LocalPort 3307 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 3307 is listening; refusing cleanup of an apparently active instance.'
}
if (Test-Path -LiteralPath (Join-Path $resolvedDataRoot 'hdbpp')) {
    throw 'An hdbpp database directory exists; refusing destructive recovery.'
}

$description = "Remove and recreate the verified incomplete $ServiceName bootstrap at $resolvedDataRoot"
if (-not $PSCmdlet.ShouldProcess($ServiceName, $description)) {
    return
}

& sc.exe delete $ServiceName | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not delete incomplete service '$ServiceName'."
}
$deadline = [DateTime]::UtcNow.AddSeconds(15)
do {
    Start-Sleep -Milliseconds 250
    $remaining = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
} while ($remaining -and [DateTime]::UtcNow -lt $deadline)
if ($remaining) {
    throw "Service '$ServiceName' is still present after deletion request."
}

# This directory contains only the failed MariaDB bootstrap. The checks above
# prohibit cleanup once credentials or an hdbpp database exist.
Remove-Item -LiteralPath $resolvedDataRoot -Recurse -Force
Remove-Item -LiteralPath $resultPath -Force

$provisioner = Join-Path $PSScriptRoot 'New-HdbppMariaDbInstance.ps1'
& $provisioner `
    -VmIPv4Address $VmIPv4Address `
    -GenerateCredentials `
    -StartService `
    -Confirm:$false

[ordered]@{
    Success = $true
    RecoveredIncompleteBootstrap = $true
    CompletedAt = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding utf8
