[CmdletBinding()]
param (
    [string]$EnvironmentPath,
    [string]$PythonPath,
    [switch]$UsePortableTools,
    [switch]$Launch,
    [switch]$Demo
)

$ErrorActionPreference = 'Stop'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$toolsPath = Join-Path $PSScriptRoot '.gamma-tools'
if (-not $EnvironmentPath) {
    $EnvironmentPath = Join-Path $toolsPath 'venv311'
}
$EnvironmentPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EnvironmentPath)
$environmentPython = Join-Path $EnvironmentPath 'Scripts\python.exe'
$pythonProbe = "import struct, sys; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8"
$dependencyProbe = "from importlib.metadata import version; import h5py, numpy, scipy, pyqtgraph; from pymcr.mcr import McrAR; from msl.equipment.resources import avantes; assert version('pyMCR') == '0.3.2'"

function Invoke-Checked {
    param ([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable exited with code $LASTEXITCODE"
    }
}

function Get-PortableArchive {
    param ([string]$Uri, [string]$Name, [string]$Sha256, [string]$Destination)
    $null = New-Item -ItemType Directory -Path $toolsPath -Force
    $archive = Join-Path $toolsPath $Name
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $Sha256) {
        Write-Host "Downloading $Name"
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $Uri -OutFile $archive -UseBasicParsing
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Unexpected SHA-256 for $Name"
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $Destination -Force
}

function Find-Python {
    if ($PythonPath) {
        return (Get-Item -LiteralPath $PythonPath).FullName
    }
    if (-not $UsePortableTools) {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            try {
                $candidate = & $launcher.Source '-3.11' '-I' '-c' "$pythonProbe; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
                    return $candidate
                }
            } catch {
                Write-Verbose 'The Python launcher did not find 64-bit Python 3.11.'
            }
        }
    }
    $destination = Join-Path $toolsPath 'python-3.11.9'
    $portable = Join-Path $destination 'tools\python.exe'
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.ready'))) {
        Get-PortableArchive 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg' `
            'python-3.11.9-x64.zip' '9283876D58C017E0E846F95B490DA3BCA0FC0A6EE1134B2870677CFB7EEC3C67' $destination
        Invoke-Checked $portable @('-I', '-c', $pythonProbe)
        Set-Content -LiteralPath (Join-Path $destination '.ready') -Value 'verified'
    }
    return $portable
}

function Enable-Git {
    if (-not $UsePortableTools -and (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        return
    }
    $destination = Join-Path $toolsPath 'mingit-2.56.1'
    $bin = Join-Path $destination 'cmd'
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.ready'))) {
        Get-PortableArchive 'https://github.com/git-for-windows/git/releases/download/v2.56.1.windows.1/MinGit-2.56.1-64-bit.zip' `
            'MinGit-2.56.1-64-bit.zip' '4A92850B6E917DA4FD010669B614B55DCCF5B0EC333A534CC4BE4700DFEFDAFD' $destination
        Invoke-Checked (Join-Path $bin 'git.exe') @('--version')
        Set-Content -LiteralPath (Join-Path $destination '.ready') -Value 'verified'
    }
    $env:Path = "$bin;$env:Path"
}

if (-not (Test-Path -LiteralPath $environmentPython -PathType Leaf)) {
    $basePython = Find-Python
    Invoke-Checked $basePython @('-I', '-c', $pythonProbe)
    Write-Host "Creating the Gamma environment at $EnvironmentPath"
    Invoke-Checked $basePython @('-I', '-m', 'venv', $EnvironmentPath)
}
Invoke-Checked $environmentPython @('-I', '-c', $pythonProbe)

$stamp = Join-Path $EnvironmentPath 'gamma-requirements.sha256'
$hash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
$cached = (Test-Path -LiteralPath $stamp -PathType Leaf) -and (Get-Content -LiteralPath $stamp -Raw).Trim() -eq $hash
$valid = $false
if ($cached) {
    try {
        & $environmentPython '-I' '-c' $dependencyProbe 2>$null
        $valid = $LASTEXITCODE -eq 0
    } catch {
        Write-Verbose 'The installed packages did not pass the import check.'
    }
}
if (-not $valid) {
    Enable-Git
    Write-Host 'Installing the Gamma packages'
    $pipArguments = @('-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '-r', $requirements)
    if ($cached) {
        $pipArguments += '--force-reinstall'
    }
    Invoke-Checked $environmentPython $pipArguments
    Invoke-Checked $environmentPython @('-I', '-m', 'pip', '--isolated', 'check')
    Invoke-Checked $environmentPython @('-I', '-c', $dependencyProbe)
    Set-Content -LiteralPath $stamp -Value $hash
}
Invoke-Checked $environmentPython @('--version')
Write-Host "Gamma environment: $EnvironmentPath"
Write-Host 'Verified MCR backend: pyMCR 0.3.2 (NIST)'

if ($Launch) {
    $env:AVANTES_EMULATOR = if ($Demo) { '1' } else { '0' }
    $env:AVANTES_DEMO_KINETICS = if ($Demo) { '1' } else { '0' }
    Invoke-Checked $environmentPython @('-E', '-s', (Join-Path $PSScriptRoot 'avantes_dual_viewer.py'))
}
