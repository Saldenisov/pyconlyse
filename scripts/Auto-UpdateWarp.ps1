# Auto-UpdateWarp.ps1
# Automatically updates WARP.md using Warp AI when changes are detected

param([switch]$Force)

Write-Host "🤖 Auto-updating WARP.md..." -ForegroundColor Blue

# First check if update is needed
& "$PSScriptRoot\Check-WarpFile.ps1" -CheckOnly
$needsUpdate = $LASTEXITCODE -eq 1

if (-not $needsUpdate -and -not $Force) {
    Write-Host "✅ WARP.md is already up to date" -ForegroundColor Green
    exit 0
}

Write-Host "🔄 Detected changes requiring WARP.md update..." -ForegroundColor Yellow

# Get recent git changes for context
$recentChanges = git --no-pager log --oneline -5 --pretty=format:"%s"
$changedFiles = git --no-pager diff --name-only HEAD~1..HEAD 2>$null
if (-not $changedFiles) {
    $changedFiles = git --no-pager diff --cached --name-only 2>$null
}

# Build context for Warp AI
$context = "Recent changes detected that affect WARP.md:"

if ($changedFiles) {
    $context += "`n`nChanged files:"
    $changedFiles | ForEach-Object { $context += "`n- $_" }
}

if ($recentChanges) {
    $context += "`n`nRecent commits:"
    $recentChanges | ForEach-Object { $context += "`n- $_" }
}

# Check for specific types of changes
$binChanges = $changedFiles | Where-Object { $_ -match "^bin/.*\.py$" }
$configChanges = $changedFiles | Where-Object { $_ -match "(pyproject\.toml|requirements\.txt)" }
$newScripts = git --no-pager diff --name-status --cached | Where-Object { $_ -match "^A.*bin/.*\.py$" }

$updatePrompt = "Please update WARP.md based on the following project changes:`n`n$context"

if ($binChanges) {
    $updatePrompt += "`n`nFocus on updating the launch commands section for any new or modified Python scripts in bin/."
}

if ($configChanges) {
    $updatePrompt += "`n`nCheck if dependency changes in pyproject.toml need to be reflected."
}

$updatePrompt += "`n`nMake sure to remove references to deleted .cmd files and add documentation for new Python scripts. Keep the existing structure and style of the WARP.md file."

Write-Host "🤖 Calling Warp AI to update WARP.md..." -ForegroundColor Cyan
Write-Host "Context: $updatePrompt" -ForegroundColor Gray

# Call Warp AI to update WARP.md
warp $updatePrompt

# Wait a moment for the update to complete
Start-Sleep -Seconds 2

# Check if WARP.md was actually updated
if (Test-Path "WARP.md") {
    $warpStatus = git status --porcelain WARP.md
    if ($warpStatus) {
        Write-Host "✅ WARP.md has been updated by Warp AI" -ForegroundColor Green
        Write-Host "📝 Changes detected in WARP.md - adding to commit" -ForegroundColor Cyan
        git add WARP.md
        exit 0
    } else {
        Write-Host "⚠️ WARP.md may not have been updated. Please check manually." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "❌ WARP.md not found" -ForegroundColor Red
    exit 1
}