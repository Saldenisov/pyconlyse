[CmdletBinding()]
param(
    [string]$VmIPv4Address,
    [string]$VmRoot = "E:\ELYSE-VMs\HDBPP",
    [string]$ArchiveRoot = "D:\ELYSE-Archive\MariaDB",
    [int]$TangoPort = 10000,
    [int]$ArchiveDatabasePort = 3307
)

$ErrorActionPreference = "Continue"

$checks = [Collections.Generic.List[object]]::new()
function Add-Check([string]$Name, [bool]$Passed, [string]$Detail) {
    $checks.Add([pscustomobject]@{
        Check = $Name
        Passed = $Passed
        Detail = $Detail
    })
}

$vmDrive = Split-Path -Qualifier $VmRoot
$archiveDrive = Split-Path -Qualifier $ArchiveRoot
foreach ($entry in @(@("VM volume", $vmDrive), @("Archive volume", $archiveDrive))) {
    $drive = Get-PSDrive -Name $entry[1].TrimEnd(':') -ErrorAction SilentlyContinue
    Add-Check $entry[0] ($null -ne $drive) $(if ($drive) { "$([math]::Round($drive.Free / 1GB, 1)) GB free on $($entry[1])" } else { "$($entry[1]) is unavailable" })
}

$maria = Get-Service -Name "MariaDB" -ErrorAction SilentlyContinue
Add-Check "Existing Tango MariaDB" ($maria.Status -eq "Running") $(if ($maria) { "$($maria.Status), unchanged" } else { "Service not found" })

$archiveMaria = Get-Service -Name "MariaDB-HDBPP" -ErrorAction SilentlyContinue
Add-Check "Isolated HDB++ MariaDB" ($archiveMaria.Status -eq "Running") $(if ($archiveMaria) { "$($archiveMaria.Status)" } else { "Not provisioned" })

$tangoListening = [bool](Get-NetTCPConnection -State Listen -LocalPort $TangoPort -ErrorAction SilentlyContinue)
Add-Check "Tango database port" $tangoListening "localhost:$TangoPort"

$archiveListening = [bool](Get-NetTCPConnection -State Listen -LocalPort $ArchiveDatabasePort -ErrorAction SilentlyContinue)
Add-Check "HDB++ database port" $archiveListening "localhost:$ArchiveDatabasePort"

$hyperV = [bool](Get-Command Get-VM -ErrorAction SilentlyContinue)
Add-Check "Hyper-V PowerShell" $hyperV $(if ($hyperV) { "Available" } else { "Enable Hyper-V and reboot" })

if ($VmIPv4Address) {
    $ping = Test-Connection -TargetName $VmIPv4Address -Count 1 -Quiet -ErrorAction SilentlyContinue
    Add-Check "Ubuntu VM network" $ping $VmIPv4Address
}

$checks | Format-Table -AutoSize
if ($checks.Where({ -not $_.Passed }).Count -gt 0) {
    exit 1
}
