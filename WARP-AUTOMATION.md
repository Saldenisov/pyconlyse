# WARP Auto-Update Documentation

## 🎯 Overview

Your project now has **automatic WARP.md maintenance** integrated into the git commit process. When you commit changes that affect the project structure, WARP.md will be automatically updated using Warp AI.

## ⚡ How It Works

### During Git Commit:
1. **Pre-commit hooks run** (code formatting, linting)
2. **WARP checker analyzes** your staged changes
3. **If WARP.md is outdated**: Warp AI automatically updates it
4. **Updated WARP.md** is added to your commit
5. **Commit proceeds** with both your changes and updated documentation

### What Triggers Updates:
- ✅ New Python scripts in `bin/`
- ✅ Modified Python scripts in `bin/`
- ✅ Changes to `pyproject.toml`
- ✅ Changes to `requirements.txt`
- ✅ Deleted files that were referenced in WARP.md

## 🔧 Current Setup

### Files Created:
```
scripts/
├── Check-WarpFile.ps1                    # Detects when WARP.md needs updates
├── PreCommit-WarpUpdate-Simple.ps1       # Auto-updates WARP.md during commit
├── warp-check.ps1                        # Interactive WARP maintenance
└── dev-workflow-fixed.ps1                # Complete development workflow

.pre-commit-config.yaml                   # Pre-commit hook configuration
```

### Pre-commit Configuration:
- **Black**: Code formatting
- **Ruff**: Linting and formatting
- **isort**: Import sorting
- **WARP Auto-update**: Documentation maintenance

## 🎮 Usage Examples

### Normal Development Workflow:
```powershell
# Make your changes
# ... edit files ...

# Commit (WARP.md will auto-update if needed)
git add .
git commit -m "Added new features"

# Output will show:
# - Code formatting applied
# - WARP.md auto-updated (if needed)
# - Both changes committed together
```

### Manual WARP Maintenance:
```powershell
# Check WARP status
.\scripts\Check-WarpFile.ps1 -CheckOnly

# Interactive update
.\scripts\warp-check.ps1

# Force update
.\scripts\PreCommit-WarpUpdate-Simple.ps1
```

## 📋 What Gets Auto-Updated

When your current backlog is processed, WARP.md will be updated to:

### ✅ Remove:
- References to deleted `.cmd` files
- Outdated launcher commands

### ✅ Add:
- Documentation for new Python scripts:
  - `configure_astor_startup.py`
  - `DS_ARCHIVE_client.py` 
  - `DS_AVANTES_SPECTRO_client.py`
  - `DS_TOPDIRECT_client.py`
  - `set_path.py`
  - `test_warp_update.py`

### ✅ Update:
- Launch commands section with direct Python calls
- Common commands for new scripts
- Project structure references

## 🛠️ Troubleshooting

### If Auto-Update Doesn't Work:
1. **Check Warp AI is available**:
   ```powershell
   warp --help
   ```

2. **Run manual update**:
   ```powershell
   .\scripts\warp-check.ps1
   ```

3. **Check git hooks are installed**:
   ```powershell
   poetry run pre-commit install --overwrite
   ```

### If You Want to Skip Auto-Update:
```powershell
# Skip all pre-commit hooks
git commit -m "message" --no-verify

# Or edit .pre-commit-config.yaml to disable warp-auto-update hook
```

## 📊 Benefits

### ✅ **Automatic**
- No manual WARP.md maintenance
- Documentation stays current with code

### ✅ **Smart**
- Only updates when needed
- Context-aware updates based on actual changes

### ✅ **Non-blocking**
- Commits proceed even if auto-update fails
- Fallback to manual update options

### ✅ **Transparent**
- Clear output showing what was updated
- WARP.md changes visible in commit

## 🎉 Result

Your development workflow now includes:
1. **Code quality automation** (formatting, linting)
2. **Documentation automation** (WARP.md maintenance)
3. **Git integration** (all automated via pre-commit hooks)

**No more forgetting to update WARP.md!** 🚀