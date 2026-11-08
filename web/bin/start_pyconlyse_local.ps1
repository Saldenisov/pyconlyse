$ErrorActionPreference = 'Stop'
$webRoot = Split-Path -Parent $PSScriptRoot
if ($env:PYCONLYSE_PYTHON) {
    $pythonPath = $env:PYCONLYSE_PYTHON
} else {
    $pythonCandidates = @(
        (Join-Path $env:USERPROFILE '.conda\envs\pyconlyse312\python.exe'),
        (Join-Path $env:USERPROFILE 'miniconda3\envs\pyconlyse312\python.exe'),
        (Join-Path $env:USERPROFILE 'anaconda3\envs\pyconlyse312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'miniconda3\envs\pyconlyse312\python.exe'),
        'C:\ProgramData\miniconda3\envs\pyconlyse312\python.exe'
    )
    $pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $pythonPath) { throw 'Python 3.12 environment pyconlyse312 was not found.' }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Python not found: $pythonPath" }
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 5000 -ErrorAction SilentlyContinue)
if ($listeners.Count) {
    $owners = @($listeners | ForEach-Object {
        Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)"
    })
    if (($listeners | Where-Object LocalAddress -ne '0.0.0.0') -or
        ($owners | Where-Object { $_.CommandLine -notmatch 'start_local\.py' })) {
        throw 'Port 5000 is occupied by another server. Stop it before starting local Pyconlyse.'
    }
    Write-Output 'Pyconlyse is already running at http://10.20.30.202:5000'
    exit 0
}
if ($webRoot -ieq 'C:\dev\pyconlyse\web') {
    $release = Join-Path $env:ProgramData 'Pyconlyse\deployment\everest_git_release.py'
    & $pythonPath -B $release launch-local
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath (Join-Path $webRoot 'frontend\build\index.html'))) {
    throw 'Build the Pyconlyse frontend before starting the local server.'
}
$logRoot = Join-Path $env:LOCALAPPDATA 'Pyconlyse\logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
Start-Process -FilePath $pythonPath -ArgumentList '-u', 'start_local.py' `
    -WorkingDirectory $webRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logRoot 'web-local.log') `
    -RedirectStandardError (Join-Path $logRoot 'web-local-error.log')
Write-Output 'Starting Pyconlyse at http://10.20.30.202:5000'
