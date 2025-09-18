# Legacy Batch Files

This directory contains the original batch files that were used for PYCONLYSE system startup and DeviceServer management before the refactoring.

## Contents

### Original Startup Files
- `start_tango.cmd` - Original Tango infrastructure startup script
- `start_tango_*.cmd` - Various environment-specific startup scripts
- `main_ctrl_original.py` - Original monolithic main control interface

### DeviceServer Scripts
- `start_*.cmd` - Individual DeviceServer startup scripts
- `start_all_*.cmd` - Batch DeviceServer startup scripts

### Client Scripts
- `start_*_client.cmd` - Device client startup scripts

## Why These Were Moved

These files were moved to the legacy folder as part of the PYCONLYSE v2.0 refactoring for the following reasons:

1. **Code Duplication**: 40+ similar batch files with repetitive patterns
2. **Manual DeviceServer Management**: Scripts bypassed Tango's built-in Astor management
3. **Poor Error Handling**: No proper validation, logging, or error recovery
4. **Maintenance Overhead**: Hard to update and maintain consistency across files
5. **Improper Architecture**: Manual startup instead of using Tango's designed workflow

## New Architecture

The new system (v2.0) uses:
- **Unified startup scripts** (`start_tango_improved.cmd`, `Start-TangoInfrastructure.ps1`)
- **Template-based DeviceServer management** (`start_deviceserver.cmd`)
- **Astor-managed DeviceServers** (automatic lifecycle management)
- **Refactored GUI** (`main_ctrl.py` v2.0) with integrated Tango startup
- **Proper error handling, logging, and status monitoring**

## When to Use Legacy Files

These legacy files should only be used:
1. **For reference** when understanding the old system behavior
2. **As backup** if the new system has issues (temporary fallback)
3. **For client scripts** until they are migrated to the new architecture

## Migration Status

- ✅ **Infrastructure Startup**: Migrated to new unified scripts
- ✅ **DeviceServer Management**: Migrated to template + Astor management  
- ✅ **Main Control Interface**: Refactored with new architecture
- 🔄 **Client Scripts**: Still using legacy scripts (to be migrated later)
- ✅ **Documentation**: Updated with new workflow

## Important Notes

- **Do not modify these legacy files** - they are preserved for reference only
- **Use the new scripts in the parent `bin/` directory** for all operations
- **Report issues with new system** rather than reverting to legacy files
- **These files may be removed** in a future version once the new system is fully validated

---
*Legacy files preserved from PYCONLYSE v1.x - Last updated: 2025-01-18*