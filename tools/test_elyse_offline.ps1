param(
    [string]$Python = "python",
    [string]$Python34 = "",
    [switch]$CollectOnly
)

# Software fixtures and fake loopback services only. No deployment or NI access.
$ErrorActionPreference = "Stop"
$elyseRoot = Split-Path -Parent $PSScriptRoot
$previousPythonPath = $env:PYTHONPATH
$previousNetworkGuard = $env:PYCONLYSE_DENY_NETWORK
$previousPython34 = $env:ELYSE_PYTHON34
$testExitCode = 1
Push-Location -LiteralPath $elyseRoot
try {
    $env:PYTHONPATH = @(
        $elyseRoot,
        (Join-Path $elyseRoot "legacy/xp_acq_agent"),
        (Join-Path $elyseRoot "legacy/xp_acq_agent/tests"),
        (Join-Path $elyseRoot "Supervision/python_reconstruction/src"),
        (Join-Path $elyseRoot "tests/web")
    ) -join [IO.Path]::PathSeparator
    $env:PYCONLYSE_DENY_NETWORK = "1"
    if ($Python34) {
        $env:ELYSE_PYTHON34 = (Resolve-Path -LiteralPath $Python34).Path
    }
    $selectedTests = @(
        "legacy/xp_acq_agent/tests",
        "Supervision/python_reconstruction/tests",
        "tests/unit/test_acq_runtime_health.py",
        "tests/unit/test_elyse_business_logic_contract.py"
    )
    $selectedTests += Get-ChildItem -Path @(
        "tests/web/test_elyse*.py",
        "tests/web/test_acq_telemetry_api.py",
        "tests/device_servers/control/test_elyse*.py"
    ) | ForEach-Object FullName
    $pytestOptions = @("--import-mode=importlib", "--deny-network", "-q")
    if ($CollectOnly) { $pytestOptions += "--collect-only" }
    & $Python -m pytest @pytestOptions @selectedTests
    $testExitCode = $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:PYCONLYSE_DENY_NETWORK = $previousNetworkGuard
    $env:ELYSE_PYTHON34 = $previousPython34
    Pop-Location
}
exit $testExitCode
