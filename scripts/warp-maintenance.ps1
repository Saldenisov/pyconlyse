# warp-maintenance.ps1 
# Manual workflow for WARP file maintenance

Write-Host "🚀 WARP Maintenance Workflow" -ForegroundColor Blue
Write-Host "=============================" -ForegroundColor Blue

# Step 1: Check current status
Write-Host "`n1️⃣ Checking project changes..." -ForegroundColor Green
& "$PSScriptRoot\Update-WarpFile.ps1" -CheckOnly

if ($LASTEXITCODE -eq 1) {
    Write-Host "`n2️⃣ Detected changes that may affect WARP.md" -ForegroundColor Yellow
    
    # Show recent git changes
    Write-Host "`n📋 Recent changes:" -ForegroundColor Cyan
    git --no-pager log --oneline -10 --pretty=format:"  %C(yellow)%h%Creset %s %C(green)(%cr)%Creset"
    
    Write-Host "`n`n3️⃣ Would you like to:" -ForegroundColor Green
    Write-Host "   a) Auto-update WARP.md with Warp AI" -ForegroundColor Gray
    Write-Host "   b) Review changes manually" -ForegroundColor Gray
    Write-Host "   c) Skip for now" -ForegroundColor Gray
    
    $choice = Read-Host "`nChoose (a/b/c)"
    
    switch ($choice.ToLower()) {
        "a" {
            Write-Host "`n🤖 Launching Warp AI to update WARP.md..." -ForegroundColor Blue
            warp "Please review and update WARP.md based on recent project changes. Focus on the deleted .cmd files and any new scripts."
        }
        "b" {
            Write-Host "`n📝 Opening WARP.md for manual review..." -ForegroundColor Blue
            code WARP.md
        }
        "c" {
            Write-Host "`n⏭️ Skipping WARP maintenance." -ForegroundColor Gray
        }
        default {
            Write-Host "`n❓ Invalid choice. Exiting." -ForegroundColor Red
        }
    }
} else {
    Write-Host "`n✅ WARP.md is up to date!" -ForegroundColor Green
}