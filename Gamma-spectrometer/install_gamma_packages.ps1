[CmdletBinding()]
param (
    [string]$EnvironmentPath,
    [string]$PythonPath,
    [switch]$UsePortableTools,
    [switch]$Launch,
    [switch]$Demo,
    [switch]$RecoverOnly
)

$ErrorActionPreference = 'Stop'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$toolsPath = Join-Path $PSScriptRoot '.gamma-tools'
if ($RecoverOnly) {
    $Launch = $true
    $mode = if ($Demo) { 'emulated' } else { 'real' }
    $recoveryPath = if ($env:AVANTES_RECOVERY_DIRECTORY) {
        $env:AVANTES_RECOVERY_DIRECTORY
    } else {
        Join-Path $PSScriptRoot "logs\recovery-$mode"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $recoveryPath 'active.json') -PathType Leaf)) {
        return
    }
    if (-not $EnvironmentPath) {
        $EnvironmentPath = Join-Path $toolsPath 'venv311'
    }
    $recoveryPython = Join-Path $EnvironmentPath 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $recoveryPython -PathType Leaf)) {
        throw "Local Gamma environment unavailable for offline recovery: $recoveryPython"
    }
    $env:AVANTES_EMULATOR = if ($Demo) { '1' } else { '0' }
    $env:AVANTES_DEMO_KINETICS = if ($Demo) { '1' } else { '0' }
    & $recoveryPython -E -s (Join-Path $PSScriptRoot 'avantes_recovery.py') --recover-only
    exit $LASTEXITCODE
}
$managedEnvironment = -not $EnvironmentPath
if ($managedEnvironment) {
    $EnvironmentPath = Join-Path $toolsPath 'venv311'
}
$EnvironmentPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EnvironmentPath)
$environmentPython = Join-Path $EnvironmentPath 'Scripts\python.exe'
$pythonProbe = "import struct, sys; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8"
$venvProbe = "$pythonProbe; assert sys.prefix != sys.base_prefix"
$dependencyProbe = "from importlib.metadata import version; from PyQt5.QtWidgets import QApplication; import h5py, numpy, scipy, pyqtgraph; from pymcr.mcr import McrAR; from msl.equipment.resources import avantes; assert version('pyMCR') == '0.3.2'"

function Invoke-Checked {
    param ([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable exited with code $LASTEXITCODE"
    }
}

function Test-NativeCommand {
    param ([string]$Executable, [string[]]$Arguments)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }
    try {
        & $Executable @Arguments *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
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
        $selected = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PythonPath)
        if (-not (Test-NativeCommand $selected @('-I', '-c', $pythonProbe))) {
            throw "PythonPath must point to a working 64-bit Python 3.11 executable: $selected"
        }
        return $selected
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
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.ready') -PathType Leaf) -or
        -not (Test-NativeCommand $portable @('-I', '-c', $pythonProbe))) {
        Get-PortableArchive 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg' `
            'python-3.11.9-x64.zip' '9283876D58C017E0E846F95B490DA3BCA0FC0A6EE1134B2870677CFB7EEC3C67' $destination
        Invoke-Checked $portable @('-I', '-c', $pythonProbe)
        Set-Content -LiteralPath (Join-Path $destination '.ready') -Value 'verified'
    }
    return $portable
}

function Enable-Git {
    $systemGit = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $UsePortableTools -and $systemGit -and (Test-NativeCommand $systemGit.Source @('--version'))) {
        return
    }
    $destination = Join-Path $toolsPath 'mingit-2.56.1'
    $bin = Join-Path $destination 'cmd'
    $portableGit = Join-Path $bin 'git.exe'
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.ready') -PathType Leaf) -or
        -not (Test-NativeCommand $portableGit @('--version'))) {
        Get-PortableArchive 'https://github.com/git-for-windows/git/releases/download/v2.56.1.windows.1/MinGit-2.56.1-64-bit.zip' `
            'MinGit-2.56.1-64-bit.zip' '4A92850B6E917DA4FD010669B614B55DCCF5B0EC333A534CC4BE4700DFEFDAFD' $destination
        Invoke-Checked $portableGit @('--version')
        Set-Content -LiteralPath (Join-Path $destination '.ready') -Value 'verified'
    }
    $env:Path = "$bin;$env:Path"
}

$reusedEnvironment = Test-NativeCommand $environmentPython @('-I', '-c', $venvProbe)
if (-not $reusedEnvironment) {
    $hasEnvironment = (Test-Path -LiteralPath $environmentPython) -or
        (Test-Path -LiteralPath (Join-Path $EnvironmentPath 'pyvenv.cfg'))
    if ($hasEnvironment -and -not $managedEnvironment) {
        throw "EnvironmentPath contains an invalid Python 3.11 (64-bit) virtual environment. Choose a new folder or repair it before retrying: $EnvironmentPath"
    }
    $basePython = Find-Python
    Invoke-Checked $basePython @('-I', '-c', $pythonProbe)
    if ($hasEnvironment) {
        $existing = Get-Item -LiteralPath $EnvironmentPath -Force
        $parent = Get-Item -LiteralPath $toolsPath -Force
        if ($existing.FullName -ne (Join-Path $parent.FullName 'venv311') -or
            $existing.Attributes -band [IO.FileAttributes]::ReparsePoint -or
            $parent.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Cannot safely preserve the invalid environment. Choose a new EnvironmentPath: $EnvironmentPath"
        }
        $backupName = 'venv311.invalid-' + [Guid]::NewGuid().ToString('N')
        Rename-Item -LiteralPath $existing.FullName -NewName $backupName
        Write-Warning "Preserved the previous environment at $(Join-Path $toolsPath $backupName)"
    }
    Write-Host "Creating the Gamma environment at $EnvironmentPath"
    Invoke-Checked $basePython @('-I', '-m', 'venv', $EnvironmentPath)
    Invoke-Checked $environmentPython @('-I', '-c', $venvProbe)
}

$stamp = Join-Path $EnvironmentPath 'gamma-requirements.sha256'
$hash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
$cached = (Test-Path -LiteralPath $stamp -PathType Leaf) -and (Get-Content -LiteralPath $stamp -Raw).Trim() -eq $hash
$valid = $reusedEnvironment -and (Test-NativeCommand $environmentPython @('-I', '-c', $dependencyProbe))
if (-not $cached -or -not $valid) {
    Enable-Git
    Write-Host 'Installing the Gamma packages'
    $pipArguments = @('-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '-r', $requirements)
    if ($reusedEnvironment -and -not $valid) {
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
    Invoke-Checked $environmentPython @('-E', '-s', (Join-Path $PSScriptRoot 'avantes_recovery.py'))
}
