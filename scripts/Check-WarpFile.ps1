# Check-WarpFile.ps1
# Simple WARP file maintenance checker

param([switch]$CheckOnly)

Write-Host "Checking WARP file updates needed..." -ForegroundColor Cyan

$needsUpdate = $false
$changes = @()

# Check for new/removed executable files in bin/
$currentBinFiles = Get-ChildItem "bin\" -Filter "*.py" | Select-Object -ExpandProperty Name
$warpContent = Get-Content "WARP.md" -Raw

# Simple check for mentioned bin files
$currentBinFiles | ForEach-Object {
    if ($warpContent -notlike "*$_*") {
        $changes += "New file not mentioned: $_"
        $needsUpdate = $true
    }
}

# Check for removed cmd files still mentioned
if ($warpContent -like "*start_*.cmd*") {
    $changes += "Removed .cmd files still mentioned in WARP.md"
    $needsUpdate = $true
}

# Report results
if ($needsUpdate) {
    Write-Host "WARP.md may need updates:" -ForegroundColor Yellow
    $changes | ForEach-Object { Write-Host "  * $_" -ForegroundColor Yellow }
    
    if (-not $CheckOnly) {
        Write-Host ""
        Write-Host "Consider running:" -ForegroundColor Green
        Write-Host "  warp 'Update WARP.md based on recent project changes'" -ForegroundColor Gray
    }
    exit 1
} else {
    Write-Host "WARP.md appears up to date" -ForegroundColor Green
    exit 0
}