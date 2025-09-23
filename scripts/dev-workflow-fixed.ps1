# dev-workflow-fixed.ps1
# Comprehensive development workflow automation

param(
    [Parameter(Position=0)]
    [ValidateSet("check", "format", "lint", "test", "all", "warp")]
    [string]$Action = "all",
    
    [string]$Files = "",
    [switch]$Fix
)

Write-Host "Python Development Workflow" -ForegroundColor Blue
Write-Host "===========================" -ForegroundColor Blue

function Run-Command {
    param($Command, $Description)
    Write-Host "`n$Description..." -ForegroundColor Yellow
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "$Description failed" -ForegroundColor Red
        return $false
    }
    Write-Host "$Description completed" -ForegroundColor Green
    return $true
}

$filesArg = if ($Files) { "--files $Files" } else { "" }
$success = $true

if ($Action -eq "check") {
    Write-Host "`nRunning code quality checks..." -ForegroundColor Cyan
    $success = Run-Command "poetry run pre-commit run $filesArg" "Pre-commit checks"
}
elseif ($Action -eq "format") {
    Write-Host "`nFormatting code..." -ForegroundColor Cyan
    $success = Run-Command "poetry run black ." "Black formatting"
    if ($success) { $success = Run-Command "poetry run isort ." "Import sorting" }
    if ($success) { $success = Run-Command "poetry run ruff format ." "Ruff formatting" }
}
elseif ($Action -eq "lint") {
    Write-Host "`nLinting code..." -ForegroundColor Cyan
    $fixFlag = if ($Fix) { "--fix" } else { "" }
    $success = Run-Command "poetry run ruff check . $fixFlag" "Ruff linting"
}
elseif ($Action -eq "test") {
    Write-Host "`nRunning tests..." -ForegroundColor Cyan
    $success = Run-Command "python -m unittest discover utilities/mytests/test_pypylon -p '*test.py'" "Unit tests"
}
elseif ($Action -eq "warp") {
    Write-Host "`nWARP maintenance..." -ForegroundColor Cyan
    & "$PSScriptRoot\warp-check.ps1"
}
elseif ($Action -eq "all") {
    Write-Host "`nRunning complete workflow..." -ForegroundColor Cyan
    
    # 1. Format code
    Write-Host "`n1. Code formatting" -ForegroundColor Magenta
    $success = Run-Command "poetry run black ." "Black formatting"
    if ($success) { $success = Run-Command "poetry run isort ." "Import sorting" }
    if ($success) { $success = Run-Command "poetry run ruff format ." "Ruff formatting" }
    
    # 2. Lint code
    if ($success) {
        Write-Host "`n2. Code linting" -ForegroundColor Magenta
        $success = Run-Command "poetry run ruff check . --fix" "Ruff linting"
    }
    
    # 3. Run pre-commit checks
    if ($success) {
        Write-Host "`n3. Pre-commit validation" -ForegroundColor Magenta
        $success = Run-Command "poetry run pre-commit run --all-files" "All pre-commit hooks"
    }
    
    # 4. Check WARP file
    Write-Host "`n4. WARP maintenance" -ForegroundColor Magenta
    & "$PSScriptRoot\Check-WarpFile.ps1" -CheckOnly
}

Write-Host ""
if ($success) {
    Write-Host "Workflow completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Workflow completed with issues. Check output above." -ForegroundColor Yellow
}

Write-Host "`nUsage examples:" -ForegroundColor Cyan
Write-Host "  .\scripts\dev-workflow-fixed.ps1                    # Run complete workflow" -ForegroundColor Gray
Write-Host "  .\scripts\dev-workflow-fixed.ps1 format             # Format code only" -ForegroundColor Gray
Write-Host "  .\scripts\dev-workflow-fixed.ps1 lint -Fix          # Lint and auto-fix" -ForegroundColor Gray
Write-Host "  .\scripts\dev-workflow-fixed.ps1 check -Files bin/  # Check specific files" -ForegroundColor Gray