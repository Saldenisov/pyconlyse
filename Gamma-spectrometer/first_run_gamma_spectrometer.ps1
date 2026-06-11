param(
    [ValidateSet("pyconlyse311", "pyconlyse39", "pyconlyse313")]
    [string]$EnvName = "pyconlyse311",
    [switch]$Prompt,
    [switch]$Emulator
)

# Gamma-spectrometer first-run installer for Windows 10.
# Installs Miniconda if needed, creates/updates conda env, then starts the app.

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $script = $MyInvocation.MyCommand.Path
    $argsList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$script`"",
        "-EnvName", $EnvName
    )
    if ($Prompt) {
        $argsList += "-Prompt"
    }
    if ($Emulator) {
        $argsList += "-Emulator"
    }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argsList
    exit
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$env:PYTHONNOUSERSITE = "1"

$logPath = Join-Path $ProjectRoot "first_run_gamma_spectrometer.log"
Start-Transcript -Path $logPath -Append | Out-Null

try {
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
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing

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
            [string]$Name
        )

        & $CondaExe run -n $Name python --version *> $null
        return ($LASTEXITCODE -eq 0)
    }

    if ($Prompt) {
        Write-Host "Choose Python environment:"
        Write-Host "  1. pyconlyse311 - Python 3.11, recommended"
        Write-Host "  2. pyconlyse39  - Python 3.9, legacy fallback"
        Write-Host "  3. pyconlyse313 - Python 3.13, modern test environment"
        $choice = Read-Host "Choice [1/2/3]"
        if ($choice -eq "2") {
            $EnvName = "pyconlyse39"
        } elseif ($choice -eq "3") {
            $EnvName = "pyconlyse313"
        } else {
            $EnvName = "pyconlyse311"
        }
    }

    switch ($EnvName) {
        "pyconlyse39" { $envFile = Join-Path $ProjectRoot "environment-py39.yml" }
        "pyconlyse313" { $envFile = Join-Path $ProjectRoot "environment-py313.yml" }
        default { $envFile = Join-Path $ProjectRoot "environment-py311.yml" }
    }

    if (-not (Test-Path $envFile)) {
        throw "Environment file not found: $envFile"
    }

    $conda = Find-Conda
    if (-not $conda) {
        $conda = Install-Miniconda
    }

    Write-Host "Using conda: $conda"
    Write-Host "Using env file: $envFile"

    & $conda config --set channel_priority flexible

    if (Test-CondaEnv -CondaExe $conda -Name $EnvName) {
        Write-Host "Updating existing conda env: $EnvName"
        & $conda env update -n $EnvName -f $envFile
    } else {
        Write-Host "Creating conda env: $EnvName"
        & $conda env create -f $envFile
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Conda environment setup failed"
    }

    if ($Prompt) {
        $emulatorChoice = Read-Host "Run emulator mode? [y/N]"
        if ($emulatorChoice -match "^[Yy]") {
            $Emulator = $true
        }
    }

    if ($Emulator) {
        $env:AVANTES_EMULATOR = "1"
    } else {
        Remove-Item Env:\AVANTES_EMULATOR -ErrorAction SilentlyContinue
    }

    Write-Host "Starting Gamma-spectrometer in $EnvName"
    & $conda run -n $EnvName python (Join-Path $ProjectRoot "avantes_dual_viewer.py")

    if ($LASTEXITCODE -ne 0) {
        throw "Gamma-spectrometer exited with code $LASTEXITCODE"
    }
}
catch {
    Write-Host ""
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log file: $logPath"
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
