[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$configRoot = 'C:\ProgramData\Pyconlyse'
$authPath = Join-Path $configRoot 'auth-users.json'
$environmentPath = Join-Path $configRoot 'production.env.cmd'
$credentialPath = Join-Path $configRoot 'initial-operator-credentials.txt'
$python = 'C:\Users\elyse\.conda\envs\pyconlyse39\python.exe'
$policyRoot = 'C:\ProgramData\PyconlyseHardwarePolicy'
$approvalRoot = 'C:\ProgramData\PyconlyseHardwareApprovals'
$consumedRoot = 'C:\ProgramData\PyconlyseHardwareConsumed'
$policyPath = Join-Path $policyRoot 'policy.json'

New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
New-Item -ItemType Directory -Path $policyRoot, $approvalRoot, $consumedRoot -Force | Out-Null

# The initializer may be rerun by this account. Temporarily restore its write
# access, create the deny-all policy, then lock policy/approval input back down.
& icacls.exe $policyRoot /grant:r 'EVEREST\elyse:(OI)(CI)F' | Out-Null
& icacls.exe $approvalRoot /grant:r 'EVEREST\elyse:(OI)(CI)F' | Out-Null

$passwordBytes = New-Object byte[] 18
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($passwordBytes)
$operatorPassword = [Convert]::ToBase64String($passwordBytes).TrimEnd('=')
$jwtBytes = New-Object byte[] 48
$rng.GetBytes($jwtBytes)
$rng.Dispose()
$jwtSecret = [Convert]::ToBase64String($jwtBytes)

$passwordHash = & $python -c 'from werkzeug.security import generate_password_hash; import sys; print(generate_password_hash(sys.argv[1]))' $operatorPassword
if ($LASTEXITCODE -ne 0 -or -not $passwordHash) {
    throw 'Could not generate the operator password hash.'
}

$authJson = @{ operator = $passwordHash } | ConvertTo-Json -Compress
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($authPath, $authJson, $utf8WithoutBom)
$policyJson = @{
    version = 1
    subjects = @{ operator = @{ roles = @('operator') } }
    roles = @{ operator = @{} }
    operations = @()
    starter_servers = @{}
} | ConvertTo-Json -Compress -Depth 5
[IO.File]::WriteAllText($policyPath, $policyJson, $utf8WithoutBom)

@(
    '@echo off'
    'set "PYCONLYSE_PYTHON=C:\Users\elyse\.conda\envs\pyconlyse39\python.exe"'
    ('set "JWT_SECRET_KEY={0}"' -f $jwtSecret)
    ('set "PYCONLYSE_AUTH_USERS_FILE={0}"' -f $authPath)
    'set "PYCONLYSE_WEB_HOST=0.0.0.0"'
    'set "PYCONLYSE_WEB_PORT=5000"'
    'set "PYCONLYSE_ENFORCE_DEVICE_AUTH=true"'
    'set "PYCONLYSE_JWT_COOKIE_CSRF_PROTECT=true"'
    'set "PYCONLYSE_JWT_COOKIE_SECURE=true"'
    ('set "PYCONLYSE_HARDWARE_POLICY_PATH={0}"' -f $policyPath)
    ('set "PYCONLYSE_HARDWARE_APPROVAL_DIR={0}"' -f $approvalRoot)
    ('set "PYCONLYSE_HARDWARE_CONSUMED_DIR={0}"' -f $consumedRoot)
) | Set-Content -LiteralPath $environmentPath -Encoding ascii

@(
    'Pyconlyse initial operator login'
    'Username: operator'
    ('Password: {0}' -f $operatorPassword)
    'Delete this file after recording the password in the approved password manager.'
) | Set-Content -LiteralPath $credentialPath -Encoding utf8

& icacls.exe $configRoot /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'EVEREST\elyse:(OI)(CI)F' | Out-Null
& icacls.exe $policyRoot /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' 'EVEREST\elyse:(OI)(CI)RX' | Out-Null
& icacls.exe $approvalRoot /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' 'EVEREST\elyse:(OI)(CI)RX' | Out-Null
& icacls.exe $consumedRoot /inheritance:r /grant:r 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' 'EVEREST\elyse:(OI)(CI)M' | Out-Null
Write-Host "Production configuration created under $configRoot"
Write-Host "Initial operator credentials: $credentialPath"
Write-Host 'Hardware web mutations default to deny-all until an approved policy is installed.'
