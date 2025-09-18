# PreCommit-WarpUpdate.ps1
# Pre-commit hook that auto-updates WARP.md when needed

Write-Host "🔍 Checking WARP.md status..." -ForegroundColor Cyan

# Check if update is needed
& "$PSScriptRoot\Check-WarpFile.ps1" -CheckOnly 2>$null
$needsUpdate = $LASTEXITCODE -eq 1

if (-not $needsUpdate) {
    Write-Host "✅ WARP.md is up to date" -ForegroundColor Green
    exit 0
}

Write-Host "🔄 WARP.md needs updating..." -ForegroundColor Yellow

# Get context about what changed
$stagedFiles = git --no-pager diff --cached --name-only
$binFiles = $stagedFiles | Where-Object { $_ -match "^bin/.*\.py$" }
$configFiles = $stagedFiles | Where-Object { $_ -match "(pyproject\.toml|requirements\.txt)" }

# Build update context
$changes = @()
if ($binFiles) { $changes += "New/modified Python scripts: $($binFiles -join ', ')" }
if ($configFiles) { $changes += "Configuration changes: $($configFiles -join ', ')" }

$context = "Update WARP.md for the following staged changes: $($changes -join '; ')"

# Key instruction for the current known issues
$context += ". Please remove references to deleted .cmd files and add documentation for new Python scripts like configure_astor_startup.py, DS_ARCHIVE_client.py, DS_AVANTES_SPECTRO_client.py, DS_TOPDIRECT_client.py, and set_path.py. Update the launch commands section accordingly."

Write-Host "🤖 Auto-updating WARP.md..." -ForegroundColor Blue
Write-Host "Context: $context" -ForegroundColor Gray

# Call Warp AI to update WARP.md
Write-Host "🤖 Calling Warp AI..." -ForegroundColor Blue
warp $context

# Give it a moment to process
Start-Sleep -Seconds 2

# Check if WARP.md was modified
$warpModified = git --no-pager status --porcelain WARP.md

if ($warpModified) {
    Write-Host "✅ WARP.md updated successfully" -ForegroundColor Green
    git add WARP.md
    Write-Host "📝 Added WARP.md to commit" -ForegroundColor Cyan
} else {
    Write-Host "⚠️ WARP.md was not updated. Continuing with commit..." -ForegroundColor Yellow
}

exit 0  # Always allow commit to proceed
