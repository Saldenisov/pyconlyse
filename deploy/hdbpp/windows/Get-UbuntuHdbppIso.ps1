[CmdletBinding()]
param(
    [string]$DestinationDirectory = "E:\ELYSE-Install\Ubuntu"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$fileName = "ubuntu-24.04.4-live-server-amd64.iso"
$expectedSha256 = "e907d92eeec9df64163a7e454cbc8d7755e8ddc7ed42f99dbc80c40f1a138433"
$uri = "https://releases.ubuntu.com/24.04/$fileName"
$destination = Join-Path ([IO.Path]::GetFullPath($DestinationDirectory)) $fileName

New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null

if (Test-Path -LiteralPath $destination) {
    $actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -eq $expectedSha256) {
        Write-Host "Verified existing Ubuntu ISO: $destination"
        return
    }
    Write-Host "Existing file is incomplete or has a different checksum; resuming download."
}

$aria = Get-Command aria2c -ErrorAction SilentlyContinue
if ($aria) {
    & $aria.Source `
        --continue=true `
        --auto-file-renaming=false `
        --allow-overwrite=true `
        --split=16 `
        --max-connection-per-server=16 `
        --min-split-size=1M `
        --file-allocation=none `
        "--dir=$DestinationDirectory" `
        "--out=$fileName" `
        $uri
}
else {
    & curl.exe --fail --location --continue-at - --output $destination $uri
}
if ($LASTEXITCODE -ne 0) {
    throw "Ubuntu download failed with exit code $LASTEXITCODE. The partial file is retained for resume."
}

$actual = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expectedSha256) {
    throw "Ubuntu ISO checksum mismatch. Expected $expectedSha256 but found $actual."
}

Write-Host "Downloaded and verified: $destination"
