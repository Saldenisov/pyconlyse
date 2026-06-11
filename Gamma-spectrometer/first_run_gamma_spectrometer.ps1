param(
    [ValidateSet("pyconlyse311", "pyconlyse39", "pyconlyse313")]
    [string]$EnvName = "pyconlyse39",
    [switch]$Prompt,
    [switch]$Emulator
)

# Windows 10 first-run installer for Gamma-spectrometer.
# Installs Miniconda if missing, creates or updates conda env, then starts app.

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Quote-Argument {
    param([string]$Value)
    if ($Value -match "[\s`"]") {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

if (-not (Test-Administrator)) {
    $script = $MyInvocation.MyCommand.Path
    $argsList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Quote-Argument $script),
        "-EnvName", $EnvName
    )
    if ($Prompt) {
        $argsList += "-Prompt"
    }
    if ($Emulator) {
        $argsList += "-Emulator"
    }

    try {
        $process = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argsList -Wait -PassThru
        exit $process.ExitCode
    }
    catch {
        Write-Host ""
        Write-Host "FAILED: Administrator elevation was cancelled or failed." -ForegroundColor Red
        Write-Host $_.Exception.Message
        Write-Host ""
        Read-Host "Press Enter to close"
        exit 1
    }
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$env:PYTHONNOUSERSITE = "1"

$logPath = Join-Path $ProjectRoot "first_run_gamma_spectrometer.log"
$transcriptStarted = $false

try {
    Start-Transcript -Path $logPath -Append | Out-Null
    $transcriptStarted = $true

    function Get-CondaCandidates {
        $roots = @(
            "$env:ProgramData\miniconda3",
            "$env:ProgramData\anaconda3",
            "$env:USERPROFILE\miniconda3",
            "$env:USERPROFILE\anaconda3",
            "$env:LOCALAPPDATA\miniconda3",
            "$env:LOCALAPPDATA\anaconda3"
        )

        foreach ($root in $roots) {
            Join-Path $root "Scripts\conda.exe"
            Join-Path $root "condabin\conda.bat"
        }
    }

    function Find-Conda {
        foreach ($name in @("conda.exe", "conda.bat", "conda")) {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if ($cmd) {
                return $cmd.Source
            }
        }

        foreach ($candidate in (Get-CondaCandidates)) {
            if (Test-Path $candidate) {
                return $candidate
            }
        }

        return $null
    }

    function Install-Miniconda {
        $installDir = "$env:ProgramData\miniconda3"
        foreach ($candidate in @(
            (Join-Path $installDir "Scripts\conda.exe"),
            (Join-Path $installDir "condabin\conda.bat")
        )) {
            if (Test-Path $candidate) {
                return $candidate
            }
        }

        Write-Host "Conda not found. Installing Miniconda to $installDir"
        $installer = Join-Path $env:TEMP "Miniconda3-latest-Windows-x86_64.exe"
        $url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"

        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing

        $installArgs = @(
            "/S",
            "/InstallationType=AllUsers",
            "/RegisterPython=0",
            "/AddToPath=0",
            "/D=$installDir"
        )
        $installProcess = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
        if ($installProcess.ExitCode -ne 0) {
            throw "Miniconda installer failed with exit code $($installProcess.ExitCode)"
        }

        foreach ($candidate in @(
            (Join-Path $installDir "Scripts\conda.exe"),
            (Join-Path $installDir "condabin\conda.bat")
        )) {
            if (Test-Path $candidate) {
                return $candidate
            }
        }

        throw "Miniconda install failed: conda executable not found in $installDir"
    }

    function Invoke-Conda {
        param(
            [string]$CondaExe,
            [string[]]$Arguments,
            [string]$FailureMessage
        )

        & $CondaExe @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FailureMessage (exit code $LASTEXITCODE)"
        }
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
        Write-Host "  1. pyconlyse39  - Python 3.9, recommended for Avantes SDK"
        Write-Host "  2. pyconlyse311 - Python 3.11"
        Write-Host "  3. pyconlyse313 - Python 3.13, modern test environment"
        $choice = Read-Host "Choice [1/2/3]"
        if ($choice -eq "2") {
            $EnvName = "pyconlyse311"
        } elseif ($choice -eq "3") {
            $EnvName = "pyconlyse313"
        } else {
            $EnvName = "pyconlyse39"
        }
    }

    switch ($EnvName) {
        "pyconlyse39" { $envFile = Join-Path $ProjectRoot "environment-py39.yml" }
        "pyconlyse313" { $envFile = Join-Path $ProjectRoot "environment-py313.yml" }
        default { $envFile = Join-Path $ProjectRoot "environment-py39.yml" }
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

    if (Test-CondaEnv -CondaExe $conda -Name $EnvName) {
        Write-Host "Updating existing conda env: $EnvName"
        Invoke-Conda -CondaExe $conda -Arguments @("env", "update", "-n", $EnvName, "-f", $envFile) -FailureMessage "Conda environment update failed"
    } else {
        Write-Host "Creating conda env: $EnvName"
        Invoke-Conda -CondaExe $conda -Arguments @("env", "create", "-f", $envFile) -FailureMessage "Conda environment create failed"
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
    Invoke-Conda -CondaExe $conda -Arguments @("run", "-n", $EnvName, "python", (Join-Path $ProjectRoot "avantes_dual_viewer.py")) -FailureMessage "Gamma-spectrometer failed"
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
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
}
