param(
    [string]$TargetHost = "10.20.30.134",
    [int]$Port = 8777,
    [string]$Interface = "ELYSE",
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"

function Get-TsharkCommand {
    return Get-Command tshark -ErrorAction SilentlyContinue
}

if (-not (Get-TsharkCommand)) {
    Write-Error @"
tshark is not installed or not in PATH.

Install on Windows (PowerShell as Administrator):
  winget install --id WiresharkFoundation.Wireshark -e

Then reopen terminal and run:
  tshark -v
"@
}

if ([string]::IsNullOrWhiteSpace($Output)) {
    $captureDir = Join-Path (Get-Location) "captures"
    if (-not (Test-Path $captureDir)) {
        New-Item -ItemType Directory -Path $captureDir | Out-Null
    }
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $Output = Join-Path $captureDir ("owis_tcp_{0}_{1}_{2}.pcapng" -f $TargetHost, $Port, $ts)
}

if ([string]::IsNullOrWhiteSpace($Interface)) {
    $ifLines = & tshark -D 2>$null
    if (-not $ifLines) {
        Write-Error "Could not list interfaces via 'tshark -D'. Try running terminal as Administrator."
    }

    $selected = $ifLines | Where-Object { $_ -notmatch "Loopback" } | Select-Object -First 1
    if (-not $selected) {
        $selected = $ifLines | Select-Object -First 1
    }

    if (-not $selected) {
        Write-Error "No capture interface found."
    }

    $Interface = ($selected -split "\.")[0].Trim()
    Write-Host ("Auto-selected interface index: {0} ({1})" -f $Interface, $selected)
}

$filter = "host $TargetHost and tcp port $Port"

Write-Host "Starting OWIS capture..."
Write-Host ("  host      : {0}" -f $TargetHost)
Write-Host ("  port      : {0}" -f $Port)
Write-Host ("  interface : {0}" -f $Interface)
Write-Host ("  filter    : {0}" -f $filter)
Write-Host ("  output    : {0}" -f $Output)
Write-Host ""
Write-Host "Press Ctrl+C to stop capture."
Write-Host "If capture fails with permissions, run Warp as Administrator."

& tshark -n -i $Interface -f $filter -w $Output
