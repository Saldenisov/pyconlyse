[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$UbuntuIsoPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ExternalAdapterName,

    [string]$VmName = "ELYSE-HDBPP",
    [string]$SwitchName = "ELYSE-Lab-External",
    [string]$VmRoot = "E:\ELYSE-VMs\HDBPP",
    [UInt64]$MemoryStartupBytes = 4GB,
    [UInt64]$DiskSizeBytes = 60GB,
    [ValidateRange(1, 16)]
    [int]$ProcessorCount = 2,
    [switch]$StartVm
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell window."
    }
}

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is unavailable. Enable Hyper-V, reboot, and retry."
    }
}

Assert-Administrator
Assert-Command "Get-VM"
Assert-Command "New-VM"

$resolvedIso = (Resolve-Path -LiteralPath $UbuntuIsoPath).Path
$resolvedVmRoot = [IO.Path]::GetFullPath($VmRoot)
$driveRoot = [IO.Path]::GetPathRoot($resolvedVmRoot)
if ($driveRoot -in @("C:\", "D:\", "E:\", "F:\")) {
    $volume = Get-Volume -DriveLetter $driveRoot.Substring(0, 1)
    if ($volume.SizeRemaining -lt ($DiskSizeBytes + 10GB)) {
        throw "The target volume needs at least the VM disk size plus 10 GB free."
    }
}

if (Get-VM -Name $VmName -ErrorAction SilentlyContinue) {
    throw "VM '$VmName' already exists; refusing to alter it."
}

$adapter = Get-NetAdapter -Name $ExternalAdapterName -ErrorAction Stop
if ($adapter.Status -ne "Up") {
    throw "Network adapter '$ExternalAdapterName' is not connected."
}

$vmDirectory = Join-Path $resolvedVmRoot $VmName
$vhdPath = Join-Path $vmDirectory "$VmName.vhdx"
if (Test-Path -LiteralPath $vmDirectory) {
    throw "Target directory '$vmDirectory' already exists; refusing to overwrite it."
}

$switch = Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue
if ($switch -and $switch.SwitchType -ne "External") {
    throw "A non-external Hyper-V switch already uses the name '$SwitchName'."
}

$description = @"
Create Ubuntu HDB++ VM '$VmName'
  VM root : $vmDirectory
  VHDX    : $vhdPath (dynamic, maximum $([math]::Round($DiskSizeBytes / 1GB)) GB)
  ISO     : $resolvedIso
  Network : external switch '$SwitchName' on '$ExternalAdapterName'
"@

if (-not $PSCmdlet.ShouldProcess($VmName, $description)) {
    return
}

if (-not $switch) {
    # Creating an external switch can briefly interrupt the host network.
    $switch = New-VMSwitch `
        -Name $SwitchName `
        -NetAdapterName $ExternalAdapterName `
        -AllowManagementOS $true
}

New-Item -ItemType Directory -Path $vmDirectory | Out-Null

$vm = New-VM `
    -Name $VmName `
    -Generation 2 `
    -MemoryStartupBytes $MemoryStartupBytes `
    -NewVHDPath $vhdPath `
    -NewVHDSizeBytes $DiskSizeBytes `
    -Path $vmDirectory `
    -SwitchName $switch.Name

Set-VMProcessor -VMName $VmName -Count $ProcessorCount
Set-VM `
    -VMName $VmName `
    -AutomaticStartAction Start `
    -AutomaticStartDelay 30 `
    -AutomaticStopAction ShutDown `
    -CheckpointType Production `
    -AutomaticCheckpointsEnabled $false

Set-VMFirmware `
    -VMName $VmName `
    -EnableSecureBoot On `
    -SecureBootTemplate MicrosoftUEFICertificateAuthority

$dvd = Add-VMDvdDrive -VMName $VmName -Path $resolvedIso -Passthru
Set-VMFirmware -VMName $VmName -FirstBootDevice $dvd

if ($StartVm) {
    Start-VM -Name $VmName | Out-Null
}

Get-VM -Name $VmName | Select-Object Name, State, ProcessorCount, MemoryStartup, AutomaticStartAction
Get-VHD -Path $vhdPath | Select-Object Path, VhdType, FileSize, Size

Write-Host "VM created. Install Ubuntu, assign the reserved laboratory IP, then run the Linux bootstrap."
