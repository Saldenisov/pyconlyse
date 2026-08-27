@echo off
REM Display one background device-server log without owning its Python process.
setlocal EnableExtensions
set "SERVER_LOG_FILE=%~1"
if not defined SERVER_LOG_FILE (
    echo ERROR: Device-server log path is required.
    exit /b 2
)
echo Log file: %SERVER_LOG_FILE%
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "while (-not (Test-Path -LiteralPath $env:SERVER_LOG_FILE)) { Start-Sleep -Milliseconds 50 }; Get-Content -LiteralPath $env:SERVER_LOG_FILE -Tail 100 -Wait"
exit /b %errorlevel%
