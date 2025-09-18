# dev-workflow.ps1
# Comprehensive development workflow automation

param(
    [Parameter(Position=0)]
    [ValidateSet("check", "format", "lint", "test", "all", "warp")]
    [string]$Action = "all",
    
    [string]$Files = "",
    [switch]$Fix
)

Write-Host "🚀 Python Development Workflow" -ForegroundColor Blue
Write-Host "===============================" -ForegroundColor Blue

function Run-Command {
    param($Command, $Description)
    Write-Host "`n🔧 $Description..." -ForegroundColor Yellow
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ $Description failed" -ForegroundColor Red
        return $false
    }
    Write-Host "✅ $Description completed" -ForegroundColor Green
    return $true
}

$filesArg = if ($Files) { "--files $Files" } else { "" }
$success = $true

switch ($Action) {
    "check" {
        Write-Host "`n📋 Running code quality checks..." -ForegroundColor Cyan
        $success = Run-Command "poetry run pre-commit run $filesArg" "Pre-commit checks"
    }
    
    "format" {
        Write-Host "`n🎨 Formatting code..." -ForegroundColor Cyan
        $success = Run-Command "poetry run black ." "Black formatting" -and $success
        $success = Run-Command "poetry run isort ." "Import sorting" -and $success
        $success = Run-Command "poetry run ruff format ." "Ruff formatting" -and $success
    }
    
    "lint" {
        Write-Host "`n🔍 Linting code..." -ForegroundColor Cyan
        $fixFlag = if ($Fix) { "--fix" } else { "" }
        $success = Run-Command "poetry run ruff check . $fixFlag" "Ruff linting" -and $success
        $success = Run-Command "poetry run mypy ." "Type checking" -and $success
        $success = Run-Command "poetry run bandit -r . -f json" "Security scan" -and $success
    }
    
    "test" {
        Write-Host "`n🧪 Running tests..." -ForegroundColor Cyan
        $success = Run-Command "python -m unittest discover utilities/mytests/test_pypylon -p '*test.py'" "Unit tests"
    }
    
    "warp" {
        Write-Host "`n📝 WARP maintenance..." -ForegroundColor Cyan
        & "$PSScriptRoot\warp-check.ps1"
    }
    
    "all" {
        Write-Host "`n🎯 Running complete workflow..." -ForegroundColor Cyan
        
        # 1. Format code
        Write-Host "`n1️⃣ Code formatting" -ForegroundColor Magenta
        $success = Run-Command "poetry run black ." "Black formatting" -and $success
        $success = Run-Command "poetry run isort ." "Import sorting" -and $success
        $success = Run-Command "poetry run ruff format ." "Ruff formatting" -and $success
        
        # 2. Lint code
        Write-Host "`n2️⃣ Code linting" -ForegroundColor Magenta
        $success = Run-Command "poetry run ruff check . --fix" "Ruff linting" -and $success
        
        # 3. Run pre-commit checks
        Write-Host "`n3️⃣ Pre-commit validation" -ForegroundColor Magenta
        $success = Run-Command "poetry run pre-commit run --all-files" "All pre-commit hooks" -and $success
        
        # 4. Check WARP file
        Write-Host "`n4️⃣ WARP maintenance" -ForegroundColor Magenta
        & "$PSScriptRoot\Check-WarpFile.ps1" -CheckOnly
    }
}

Write-Host ""
if ($success) {
    Write-Host "🎉 Workflow completed successfully!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Workflow completed with issues. Check output above." -ForegroundColor Yellow
}

Write-Host "`n💡 Usage examples:" -ForegroundColor Cyan
Write-Host "  .\scripts\dev-workflow.ps1                    # Run complete workflow" -ForegroundColor Gray
Write-Host "  .\scripts\dev-workflow.ps1 format             # Format code only" -ForegroundColor Gray
Write-Host "  .\scripts\dev-workflow.ps1 lint -Fix          # Lint and auto-fix" -ForegroundColor Gray
Write-Host "  .\scripts\dev-workflow.ps1 check -Files bin/  # Check specific files" -ForegroundColor Gray