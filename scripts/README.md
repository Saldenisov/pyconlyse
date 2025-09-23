# Development Workflow Scripts

This directory contains automated scripts to maintain code quality and project documentation.

## 🔧 Setup

The scripts use Poetry for dependency management and pre-commit for automation:

```powershell
# Install development dependencies (already done if you followed setup)
poetry install

# Install pre-commit hooks
poetry run pre-commit install
```

## 📝 WARP File Maintenance

### Check WARP.md status
```powershell
.\scripts\Check-WarpFile.ps1 -CheckOnly
```

### Interactive WARP maintenance
```powershell
.\scripts\warp-check.ps1
```

## 🚀 Code Quality Workflows

### Complete workflow (format, lint, validate)
```powershell
.\scripts\dev-workflow.ps1
```

### Individual actions
```powershell
# Format code
.\scripts\dev-workflow.ps1 format

# Lint code (with auto-fix)  
.\scripts\dev-workflow.ps1 lint -Fix

# Run tests
.\scripts\dev-workflow.ps1 test

# Run pre-commit checks
.\scripts\dev-workflow.ps1 check

# WARP maintenance only
.\scripts\dev-workflow.ps1 warp
```

### Target specific files
```powershell
# Check specific files
.\scripts\dev-workflow.ps1 check -Files "bin/main_ctrl.py"

# Format specific directory
.\scripts\dev-workflow.ps1 format -Files "DeviceServers/"
```

## 🎯 Git Integration

Pre-commit hooks automatically run on every commit:

- **Code formatting** (Black, Ruff)
- **Import sorting** (isort)
- **Linting** (Ruff with auto-fix)
- **WARP file validation** (custom check)

To bypass hooks temporarily:
```powershell
git commit -m "message" --no-verify
```

## 🛠️ Tools Configured

| Tool | Purpose | Config |
|------|---------|--------|
| **Black** | Code formatting | `pyproject.toml` |
| **Ruff** | Linting & formatting | `pyproject.toml` |
| **isort** | Import sorting | `pyproject.toml` |
| **MyPy** | Type checking | `pyproject.toml` |
| **Bandit** | Security scanning | `pyproject.toml` |
| **Pre-commit** | Git hook automation | `.pre-commit-config.yaml` |

## 📋 Quick Commands

```powershell
# Daily development
.\scripts\dev-workflow.ps1

# Before committing
.\scripts\dev-workflow.ps1 check

# Weekly maintenance
.\scripts\warp-check.ps1

# Fix all linting issues
.\scripts\dev-workflow.ps1 lint -Fix
```

## 🔍 What Gets Checked

- ✅ Code formatting consistency
- ✅ Import organization
- ✅ Common Python issues (via Ruff)
- ✅ Security vulnerabilities (via Bandit)
- ✅ WARP.md alignment with project structure
- ✅ File encoding and line endings
- ✅ Basic syntax validation

This automation ensures consistent code quality across the project while reducing manual maintenance overhead.