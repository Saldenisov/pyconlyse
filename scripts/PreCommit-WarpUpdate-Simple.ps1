# PreCommit-WarpUpdate-Simple.ps1
# Pre-commit hook that auto-updates WARP.md when needed

Write-Host "Checking WARP.md status..." -ForegroundColor Cyan

# Check if update is needed
& "$PSScriptRoot\Check-WarpFile.ps1" -CheckOnly 2>$null
$needsUpdate = $LASTEXITCODE -eq 1

if (-not $needsUpdate) {
    Write-Host "WARP.md is up to date" -ForegroundColor Green
    exit 0
}

Write-Host "WARP.md needs updating..." -ForegroundColor Yellow

# Build update context based on known issues
$context = "Update WARP.md: Remove references to deleted .cmd files and add documentation for new Python scripts like configure_astor_startup.py, DS_ARCHIVE_client.py, DS_AVANTES_SPECTRO_client.py, DS_TOPDIRECT_client.py, and set_path.py. Update the launch commands section to use direct Python script calls instead of .cmd launchers."

Write-Host "Auto-updating WARP.md with Warp AI..." -ForegroundColor Blue
Write-Host "Context: $context" -ForegroundColor Gray

# Call Warp AI to update WARP.md
warp $context

# Give it time to process
Start-Sleep -Seconds 3

# Check if WARP.md was modified
$warpStatus = git --no-pager status --porcelain WARP.md

if ($warpStatus) {
    Write-Host "WARP.md updated successfully" -ForegroundColor Green
    git add WARP.md
    Write-Host "Added WARP.md to commit" -ForegroundColor Cyan
}
else {
    Write-Host "WARP.md was not updated. Continuing with commit..." -ForegroundColor Yellow
}

# Always allow commit to proceed
exit 0