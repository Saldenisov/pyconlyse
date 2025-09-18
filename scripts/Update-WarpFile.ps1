# Update-WarpFile.ps1
# Automated WARP file maintenance script

param(
    [switch]$CheckOnly,
    [switch]$Force
)

Write-Host "🔍 Checking for WARP file updates needed..." -ForegroundColor Cyan

$needsUpdate = $false
$changes = @()

# Check for dependency changes
$pyprojectContent = Get-Content "pyproject.toml" -Raw
$requirementsContent = if (Test-Path "requirements.txt") { Get-Content "requirements.txt" -Raw } else { "" }

# Check for new/removed executable files in bin/
$currentBinFiles = Get-ChildItem "bin\" -Filter "*.py" | Select-Object -ExpandProperty Name
$warpContent = Get-Content "WARP.md" -Raw

# Check if bin files mentioned in WARP match current structure
$mentionedBinFiles = [regex]::Matches($warpContent, 'python bin\\([^\.]+\.py)') | ForEach-Object { $_.Groups[1].Value }

$newFiles = $currentBinFiles | Where-Object { $_ -notin $mentionedBinFiles }
$removedFiles = $mentionedBinFiles | Where-Object { $_ -notin $currentBinFiles }

if ($newFiles) {
    $changes += "New executable files found: $($newFiles -join ', ')"
    $needsUpdate = $true
}

if ($removedFiles) {
    $changes += "Removed files still mentioned: $($removedFiles -join ', ')"
    $needsUpdate = $true
}

# Check for changed Python version in pyproject.toml
if ($pyprojectContent -match 'python = "([^"]+)"') {
    $currentPythonVersion = $matches[1]
    $escapedVersion = [regex]::Escape($currentPythonVersion)
    if ($warpContent -notmatch $escapedVersion) {
        $changes += "Python version in pyproject.toml ($currentPythonVersion) doesn't match WARP.md"
        $needsUpdate = $true
    }
}

# Report results
if ($needsUpdate) {
    Write-Host "⚠️  WARP.md may need updates:" -ForegroundColor Yellow
    $changes | ForEach-Object { Write-Host "  • $_" -ForegroundColor Yellow }
    
    if (-not $CheckOnly) {
        Write-Host ""
        Write-Host "💡 Consider updating WARP.md with:" -ForegroundColor Green
        Write-Host "  warp 'Please review and update WARP.md based on recent project changes'" -ForegroundColor Gray
    }
} else {
    Write-Host "✅ WARP.md appears up to date" -ForegroundColor Green
}

if ($needsUpdate) { exit 1 } else { exit 0 }
