# warp-check.ps1 - Simple WARP maintenance

Write-Host "🚀 WARP File Maintenance" -ForegroundColor Blue

# Run the checker
& "$PSScriptRoot\Check-WarpFile.ps1" -CheckOnly

if ($LASTEXITCODE -eq 1) {
    Write-Host ""
    Write-Host "📋 Recent git changes:" -ForegroundColor Cyan
    git --no-pager log --oneline -5
    
    Write-Host ""
    $response = Read-Host "Update WARP.md now? (y/N)"
    
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host "🤖 Asking Warp AI to update WARP.md..." -ForegroundColor Green
        warp "Update WARP.md to reflect recent changes. I removed many .cmd files and added new Python scripts. Focus on updating the launch commands section."
    }
}