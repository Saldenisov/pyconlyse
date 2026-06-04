# Gamma-spectrometer first-run installer for Windows.
# Creates pyconlyse39 or pyconlyse313 conda env, then starts Avantes Dual Viewer.

$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $script = $MyInvocation.MyCommand.Path
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$script`""
    )
    exit
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$env:PYTHONNOUSERSITE = "1"

function Find-Conda {
    $cmd = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "$env:ProgramData\miniconda3\Scripts\conda.exe",
        "$env:ProgramData\anaconda3\Scripts\conda.exe",
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\anaconda3\Scripts\conda.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Install-Miniconda {
    $installDir = "$env:ProgramData\miniconda3"
    $condaExe = Join-Path $installDir "Scripts\conda.exe"
    if (Test-Path $condaExe) {
        return $condaExe
    }

    Write-Host "Conda not found. Installing Miniconda to $installDir"
    $installer = Join-Path $env:TEMP "Miniconda3-latest-Windows-x86_64.exe"
    $url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer
    Start-Process -FilePath $installer -ArgumentList @(
        "/S",
        "/InstallationType=AllUsers",
        "/RegisterPython=0",
        "/AddToPath=0",
        "/D=$installDir"
    ) -Wait

    if (-not (Test-Path $condaExe)) {
        throw "Miniconda install failed: $condaExe not found"
    }

    return $condaExe
}

function Test-CondaEnv {
    param(
        [string]$CondaExe,
        [string]$EnvName
    )

    & $CondaExe run -n $EnvName python --version *> $null
    return ($LASTEXITCODE -eq 0)
}

$conda = Find-Conda
if (-not $conda) {
    $conda = Install-Miniconda
}

Write-Host "Using conda: $conda"
Write-Host ""
Write-Host "Choose Python environment:"
Write-Host "  1. pyconlyse39  - Python 3.9, recommended for real Avantes hardware"
Write-Host "  2. pyconlyse313 - Python 3.13, modern test environment"
$choice = Read-Host "Choice [1/2]"

if ($choice -eq "2") {
    $envName = "pyconlyse313"
    $envFile = Join-Path $ProjectRoot "environment-py313.yml"
} else {
    $envName = "pyconlyse39"
    $envFile = Join-Path $ProjectRoot "environment-py39.yml"
}

if (-not (Test-Path $envFile)) {
    throw "Environment file not found: $envFile"
}

if (Test-CondaEnv -CondaExe $conda -EnvName $envName) {
    Write-Host "Updating existing conda env: $envName"
    & $conda env update -n $envName -f $envFile
} else {
    Write-Host "Creating conda env: $envName"
    & $conda env create -f $envFile
}

if ($LASTEXITCODE -ne 0) {
    throw "Conda environment setup failed"
}

$emulatorChoice = Read-Host "Run emulator mode? [y/N]"
if ($emulatorChoice -match "^[Yy]") {
    $env:AVANTES_EMULATOR = "1"
} else {
    Remove-Item Env:\AVANTES_EMULATOR -ErrorAction SilentlyContinue
}

Write-Host "Starting Gamma-spectrometer in $envName"
& $conda run -n $envName python (Join-Path $ProjectRoot "avantes_dual_viewer.py")

if ($LASTEXITCODE -ne 0) {
    throw "Gamma-spectrometer exited with code $LASTEXITCODE"
}
