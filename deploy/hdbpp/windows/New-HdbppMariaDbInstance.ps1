[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(?:\d{1,3}\.){3}\d{1,3}$')]
    [string]$VmIPv4Address,

    [ValidatePattern('^(?:\d{1,3}\.){3}\d{1,3}$')]
    [string]$BindIPv4Address = "10.20.30.202",

    [string]$MariaDbBin = "C:\Program Files\MariaDB 10.6\bin",
    [string]$DataRoot = "D:\ELYSE-Archive\MariaDB",
    [string]$ServiceName = "MariaDB-HDBPP",
    [ValidateRange(1024, 65535)]
    [int]$Port = 3307,
    [ValidateRange(256, 32768)]
    [int]$BufferPoolSizeMB = 4096,
    [switch]$StartService,
    [switch]$GenerateCredentials,
    [string]$CredentialStorePath = "C:\ProgramData\ELYSE-HDBPP\mariadb-credentials.clixml"
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

function Convert-SecureStringToPlainText([Security.SecureString]$Value) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function New-RandomHexPassword([int]$ByteCount = 32) {
    $bytes = New-Object byte[] $ByteCount
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        return -join ($bytes | ForEach-Object { $_.ToString("x2") })
    }
    finally {
        $rng.Dispose()
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

Assert-Administrator

$installer = Join-Path $MariaDbBin "mariadb-install-db.exe"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "MariaDB instance utility not found at '$installer'."
}
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    throw "Service '$ServiceName' already exists; refusing to alter it."
}
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "TCP port $Port is already in use."
}

$resolvedDataRoot = [IO.Path]::GetFullPath($DataRoot)
if (Test-Path -LiteralPath $resolvedDataRoot) {
    if (Get-ChildItem -LiteralPath $resolvedDataRoot -Force -ErrorAction Stop | Select-Object -First 1) {
        throw "Data directory '$resolvedDataRoot' is not empty; refusing to overwrite it."
    }
}

$description = @"
Create isolated MariaDB service '$ServiceName'
  Data directory : $resolvedDataRoot
  Listen address : ${BindIPv4Address}:$Port
  Allowed client : $VmIPv4Address (firewall is configured separately)
"@

if (-not $PSCmdlet.ShouldProcess($ServiceName, $description)) {
    return
}

if ($GenerateCredentials) {
    $rootPassword = New-RandomHexPassword
    $writerPassword = New-RandomHexPassword
    $rootPasswordSecure = ConvertTo-SecureString $rootPassword -AsPlainText -Force
    $writerPasswordSecure = ConvertTo-SecureString $writerPassword -AsPlainText -Force
}
else {
    $rootPasswordSecure = Read-Host "New local root password for the isolated HDB++ MariaDB" -AsSecureString
    $rootPassword = Convert-SecureStringToPlainText $rootPasswordSecure
    $writerPasswordSecure = Read-Host "New password for hdbpp_writer from $VmIPv4Address" -AsSecureString
    $writerPassword = Convert-SecureStringToPlainText $writerPasswordSecure
}
if ($rootPassword.Length -lt 16) {
    throw "Use a root password of at least 16 characters."
}
if ($writerPassword -notmatch '^[A-Za-z0-9._~!@%+=:,?-]{16,128}$') {
    throw "Use 16-128 characters from A-Z, a-z, 0-9, and ._~!@%+=:,?- for hdbpp_writer."
}

New-Item -ItemType Directory -Path $resolvedDataRoot -Force | Out-Null
# MariaDB's official Windows bootstrap utility requires the initial password
# as an argument. Run only from an administrator-controlled local session.
& $installer `
    "--datadir=$resolvedDataRoot" `
    "--service=$ServiceName" `
    "--password=$rootPassword" `
    "--port=$Port"
if ($LASTEXITCODE -ne 0) {
    throw "mariadb-install-db.exe failed with exit code $LASTEXITCODE."
}

$configPath = Join-Path $resolvedDataRoot "my.ini"
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "MariaDB did not create '$configPath'."
}

$config = Get-Content -Raw -LiteralPath $configPath
if ($config -notmatch '(?m)^\s*bind-address\s*=') {
    # Firewall scope, rather than MariaDB root access, limits the remote peer.
    # Listening on all local interfaces also permits root administration through
    # 127.0.0.1; mariadb-install-db leaves remote root access disabled.
    $config = $config -replace '(?m)^\[mysqld\]\s*$', "[mysqld]`r`nbind-address=0.0.0.0"
}
if ($config -notmatch '(?m)^\s*innodb_buffer_pool_size\s*=') {
    $config = $config -replace '(?m)^\[mysqld\]\s*$', "[mysqld]`r`ninnodb_buffer_pool_size=${BufferPoolSizeMB}M"
}
# Windows PowerShell's ``-Encoding UTF8`` writes a BOM. MariaDB 10.6 can
# misread the first [mysqld] section when that BOM is present, then start with
# the wrong defaults and terminate. Write explicit UTF-8 without a BOM.
$utf8WithoutBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($configPath, $config, $utf8WithoutBom)

Set-Service -Name $ServiceName -StartupType Automatic

Start-Service -Name $ServiceName
$deadline = [DateTime]::UtcNow.AddSeconds(30)
do {
    $listening = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listening) {
        break
    }
    Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $deadline)
if (-not $listening) {
    throw "Service '$ServiceName' started but did not listen on port $Port within 30 seconds."
}

$client = Join-Path $MariaDbBin "mariadb.exe"
if (-not (Test-Path -LiteralPath $client -PathType Leaf)) {
    $client = Join-Path $MariaDbBin "mysql.exe"
}
if (-not (Test-Path -LiteralPath $client -PathType Leaf)) {
    throw "MariaDB command-line client not found in '$MariaDbBin'."
}

$sql = @"
CREATE DATABASE IF NOT EXISTS ``hdbpp``
  CHARACTER SET latin1 COLLATE latin1_swedish_ci;
CREATE USER IF NOT EXISTS 'hdbpp_writer'@'$VmIPv4Address' IDENTIFIED BY '$writerPassword';
ALTER USER 'hdbpp_writer'@'$VmIPv4Address' IDENTIFIED BY '$writerPassword';
GRANT ALL PRIVILEGES ON ``hdbpp``.* TO 'hdbpp_writer'@'$VmIPv4Address';
FLUSH PRIVILEGES;
"@

try {
    $sql | & $client `
        --protocol=tcp `
        --host=127.0.0.1 `
        "--port=$Port" `
        --user=root `
        "--password=$rootPassword"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the HDB++ database and VM-scoped writer account."
    }

    if ($GenerateCredentials) {
        $credentialDirectory = Split-Path -Parent $CredentialStorePath
        $credentialOwner = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        New-Item -ItemType Directory -Path $credentialDirectory -Force | Out-Null
        [ordered]@{
            Root = [Management.Automation.PSCredential]::new("root", $rootPasswordSecure)
            Writer = [Management.Automation.PSCredential]::new("hdbpp_writer", $writerPasswordSecure)
            DatabaseHost = $BindIPv4Address
            DatabasePort = $Port
            DatabaseName = "hdbpp"
            AllowedClient = $VmIPv4Address
            CreatedAt = (Get-Date).ToUniversalTime().ToString("o")
        } | Export-Clixml -LiteralPath $CredentialStorePath -Force
        & icacls.exe $credentialDirectory /inheritance:r /grant:r `
            "SYSTEM:(OI)(CI)F" `
            "Administrators:(OI)(CI)F" `
            "${credentialOwner}:(OI)(CI)F" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to restrict ACLs on '$credentialDirectory'."
        }
        & icacls.exe $CredentialStorePath /inheritance:r /grant:r `
            "SYSTEM:F" `
            "Administrators:F" `
            "${credentialOwner}:F" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to restrict ACLs on '$CredentialStorePath'."
        }
    }
}
finally {
    $sql = $null
    $rootPassword = $null
    $writerPassword = $null
}

$ruleName = "ELYSE HDBPP MariaDB from VM"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Remove-NetFirewallRule -DisplayName $ruleName
}
New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalAddress $BindIPv4Address `
    -LocalPort $Port `
    -RemoteAddress $VmIPv4Address `
    -Profile Any | Out-Null

if (-not $StartService) {
    Stop-Service -Name $ServiceName
}

Get-Service -Name $ServiceName | Select-Object Name, Status, StartType
Write-Host "Created the isolated archive service, empty hdbpp database, and VM-scoped writer."
if ($GenerateCredentials) {
    Write-Host "Generated credentials were stored with Windows DPAPI at '$CredentialStorePath'."
}
Write-Host "The official HDB++ schema is imported from Ubuntu in the next deployment step."
