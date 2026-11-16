[CmdletBinding()]
param (
    [string]$EnvironmentPath = (Join-Path $PSScriptRoot '.venv'),
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$environmentPython = Join-Path $EnvironmentPath 'Scripts\python.exe'

function Invoke-Checked {
    param ([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable exited with code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $environmentPython -PathType Leaf)) {
    if ($PythonPath) {
        Invoke-Checked $PythonPath @('-I', '-m', 'venv', $EnvironmentPath)
    } else {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if (-not $launcher) {
            throw 'Install Python 3.11 with the Windows Python launcher, or pass -PythonPath.'
        }
        Invoke-Checked $launcher.Source @('-3.11', '-I', '-m', 'venv', $EnvironmentPath)
    }
}

Invoke-Checked $environmentPython @('-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '-r', $requirements)
Invoke-Checked $environmentPython @('-I', '-m', 'pip', '--isolated', 'check')
Invoke-Checked $environmentPython @('-I', '-c', "import h5py, numpy, scipy, pyqtgraph; from pymcr.mcr import McrAR; from msl.equipment.resources import avantes; print('Gamma dependencies verified')")
Write-Host "Gamma Python: $([System.IO.Path]::GetFullPath($environmentPython))"
