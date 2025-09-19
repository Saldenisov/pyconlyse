# PowerShell script to kill duplicate DS_Basler_camera processes
Write-Host "🛑 Stopping duplicate DS_Basler_camera processes..." -ForegroundColor Yellow
Write-Host "=" * 60

# Get all DS_Basler_camera processes
$cameraProcesses = Get-Process -Name "DS_Basler_camera" -ErrorAction SilentlyContinue

if ($cameraProcesses) {
    Write-Host "📋 Found $($cameraProcesses.Count) DS_Basler_camera process(es):" -ForegroundColor Cyan
    
    foreach ($process in $cameraProcesses) {
        Write-Host "🔸 PID: $($process.Id) | Memory: $([math]::Round($process.WorkingSet64/1MB, 2)) MB" -ForegroundColor White
    }
    
    Write-Host "`n🛑 Stopping all DS_Basler_camera processes..." -ForegroundColor Red
    
    try {
        $cameraProcesses | Stop-Process -Force
        Write-Host "✅ Successfully stopped all DS_Basler_camera processes" -ForegroundColor Green
        
        # Wait a moment for processes to fully terminate
        Start-Sleep -Seconds 2
        
        # Verify they're stopped
        $remainingProcesses = Get-Process -Name "DS_Basler_camera" -ErrorAction SilentlyContinue
        if ($remainingProcesses) {
            Write-Host "⚠️  Warning: Some processes may still be running" -ForegroundColor Yellow
            foreach ($proc in $remainingProcesses) {
                Write-Host "   Still running: PID $($proc.Id)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "✅ All DS_Basler_camera processes successfully terminated" -ForegroundColor Green
        }
        
    } catch {
        Write-Host "❌ Error stopping processes: $($_.Exception.Message)" -ForegroundColor Red
    }
    
} else {
    Write-Host "✅ No DS_Basler_camera processes found" -ForegroundColor Green
}

Write-Host "`n💡 Next steps:" -ForegroundColor Cyan
Write-Host "1. Wait 5-10 seconds for camera resources to be released" -ForegroundColor White
Write-Host "2. Restart the device server through Astor" -ForegroundColor White
Write-Host "3. Or manually start with: DS_Basler_camera.exe 1_Cam1_V0" -ForegroundColor White
Write-Host "4. Check that only ONE instance is running" -ForegroundColor White