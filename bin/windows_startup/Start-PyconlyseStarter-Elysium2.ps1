# Launch Elysium2 Tango after the remote database is ready, and supervise Starter.
[CmdletBinding()]
param(
    [string]$PythonExecutable = $env:PYCONLYSE_PYTHON,
    [string]$RepositoryRoot = 'C:\dev\pyconlyse',
    [string]$StarterDirectory = 'C:\dev\pyconlyse-runtime\starter-9.1',
    [string]$TangoHost = '10.20.30.202:10000',
    [ValidateRange(1, 3600)][int]$DatabaseTimeoutSeconds = 600,
    [ValidateRange(1, 600)][int]$StarterTimeoutSeconds = 120,
    [ValidateRange(1, 600)][int]$ServersTimeoutSeconds = 180,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$starterExecutable = Join-Path $StarterDirectory 'Starter.exe'
$probe = Join-Path $RepositoryRoot 'bin\windows_startup\probe_tango_readiness.py'
$logDirectory = 'C:\temp\ds.log'
$logFile = Join-Path $logDirectory 'elysium2_starter_startup.log'
$starterDevice = 'tango/admin/elysium2'
$mutex = $null
$mutexHeld = $false

function Write-StartupLog([string]$Message) {
    $line = '[{0}] {1}' -f (Get-Date -Format o), $Message
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Get-ElysiumStarter {
    $processes = @(Get-CimInstance Win32_Process -Filter "Name='Starter.exe'" |
        Where-Object {
            $_.ExecutablePath -eq $starterExecutable -or
            $_.CommandLine -match '(^|\s)"?elysium2"?(\s|$)'
        })
    if ($processes.Count -gt 1) {
        throw "Multiple Elysium2 Starter processes: $($processes.ProcessId -join ', ')"
    }
    if ($processes.Count -eq 1) {
        if ($processes[0].ExecutablePath -ne $starterExecutable) {
            throw "Starter already running from another runtime: $($processes[0].ExecutablePath)"
        }
        return Get-Process -Id $processes[0].ProcessId -ErrorAction Stop
    }
    return $null
}

function Invoke-ReadinessProbe([string]$Mode) {
    $arguments = @($probe, $Mode)
    if ($Mode -ne '--database') { $arguments += $starterDevice }
    # Native stderr is diagnostic data; Python's exit code controls readiness.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& $PythonExecutable @arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        Write-StartupLog "PROBE_FAILED mode=$Mode exit=$exitCode $($output -join ' ')"
        return $false
    }
    return $true
}

function Wait-Readiness([string]$Mode, [int]$TimeoutSeconds, $Process = $null) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if ($null -ne $Process) {
            $Process.Refresh()
            if ($Process.HasExited) { throw "Starter exited before readiness, PID=$($Process.Id)" }
        }
        if (Invoke-ReadinessProbe $Mode) {
            Write-StartupLog "READY mode=$Mode elapsed_seconds=$([math]::Round($timer.Elapsed.TotalSeconds, 2))"
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Readiness timeout: $Mode after $TimeoutSeconds seconds"
}

try {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    if (-not $PythonExecutable) {
        $PythonExecutable = 'C:\Users\ECX-3100\.conda\envs\pyconlyse312\python.exe'
    }
    foreach ($path in @($PythonExecutable, $starterExecutable, $probe)) {
        if (-not [IO.Path]::IsPathRooted($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required startup file is unavailable: $path"
        }
    }
    $env:TANGO_HOST = $TangoHost
    $env:OMNIORB_CONFIG = Join-Path $RepositoryRoot 'OMNIORB.CFG'
    $env:PYCONLYSE = $RepositoryRoot
    $env:PYCONLYSE_ENV = 'pyconlyse312'
    $env:PYCONLYSE_PYTHON = $PythonExecutable
    $env:PYTHONNOUSERSITE = '1'
    $pythonDirectory = Split-Path -Parent $PythonExecutable
    $env:PATH = "$pythonDirectory;$pythonDirectory\Library\bin;$pythonDirectory\Scripts;$env:PATH"
    Write-StartupLog "BOOTSTRAP_STARTED verify_only=$VerifyOnly tango_host=$TangoHost"

    if (-not $VerifyOnly) {
        $mutex = New-Object Threading.Mutex($false, 'Global\PyconlyseStarterElysium2Bootstrap')
        try { $mutexHeld = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $mutexHeld = $true }
        if (-not $mutexHeld) {
            Write-StartupLog 'BOOTSTRAP_ALREADY_RUNNING'
            exit 0
        }
        $legacy = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
            Where-Object {
                $_.ExecutablePath -match 'pyconlyse39\\python.exe$' -and
                $_.CommandLine -match 'DS_(Standa_Motor|KEYSIGHT_33509B|Zaber)\.py'
            })
        if ($legacy.Count) { throw "Legacy servers still running: $($legacy.ProcessId -join ', ')" }
    }

    # Keep retries inside the supervisor: this host did not honor the task's
    # RestartOnFailure settings during the live failure test.
    while ($true) {
        try {
            Wait-Readiness '--database' $DatabaseTimeoutSeconds
            $starter = Get-ElysiumStarter
            if ($null -eq $starter) {
                if ($VerifyOnly) { throw 'Elysium2 Starter process is absent' }
                $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
                $starter = Start-Process -FilePath $starterExecutable -ArgumentList 'elysium2' `
                    -WorkingDirectory $StarterDirectory -WindowStyle Hidden -PassThru `
                    -RedirectStandardOutput (Join-Path $logDirectory "Starter_boot_$stamp.out.log") `
                    -RedirectStandardError (Join-Path $logDirectory "Starter_boot_$stamp.err.log")
                Write-StartupLog "STARTER_LAUNCHED pid=$($starter.Id)"
            } else {
                Write-StartupLog "STARTER_REUSED pid=$($starter.Id)"
            }
            Wait-Readiness '--starter' $StarterTimeoutSeconds $starter
            if (-not $VerifyOnly -and -not (Invoke-ReadinessProbe '--start-controlled')) {
                throw 'Failed to start configured automatic servers'
            }
            Wait-Readiness '--controlled-ready' $ServersTimeoutSeconds $starter
            Write-StartupLog "ELYSIUM2_STARTER_COMPLETE pid=$($starter.Id)"
            if ($VerifyOnly) { exit 0 }
            $starter.WaitForExit()
            Write-StartupLog "STARTER_STOPPED pid=$($starter.Id); retrying in 15 seconds"
        } catch {
            if ($VerifyOnly) { throw }
            Write-StartupLog "STARTUP_ATTEMPT_FAILED $($_.Exception.Message); retrying in 15 seconds"
        }
        Start-Sleep -Seconds 15
    }
} catch {
    Write-StartupLog "BOOTSTRAP_FAILED $($_.Exception.Message)"
    exit 1
} finally {
    if ($mutexHeld) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
}
