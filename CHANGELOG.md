# PyConlyse Project Changelog

This document consolidates major changes, refactorings, and improvements to the PyConlyse project.

---

## Project Reorganization (2025)

### Overview
Successfully completed project clean-up and modularization with a clean, modular structure that separates concerns.

### Key Changes
- ✅ Created clean `main_app/` directory with proper Python package structure
- ✅ Moved all legacy files to `legacy/` folder
- ✅ Cleaned `bin/` folder to contain only essential startup scripts
- ✅ Established clear separation between executable scripts and Python application code

### Modular Application Architecture
- **Core Module**: Central configuration management (`main_app/core/config.py`)
- **Managers Module**: Business logic components (`main_app/managers/`)
  - Infrastructure management (Tango database, starter, astor)
  - Device server lifecycle management
  - Monitoring threads
- **UI Module**: Prepared for future UI component extraction
- **Tests Module**: Comprehensive test suite

### Benefits
- Clean separation of concerns
- Improved maintainability
- Better testing infrastructure (18 comprehensive tests)
- Professional Python package structure

---

## GUI-First Non-Blocking Implementation (2025)

### Overview
Successfully implemented GUI-first architecture where the GUI starts immediately and handles all operations asynchronously.

### Key Features
✅ **GUI Starts Immediately** - Interface appears within seconds
✅ **Async Background Operations** - Non-blocking initialization and operations
✅ **Comprehensive Logging System** - Separate log files with real-time GUI viewer
✅ **Non-Blocking Architecture** - Thread-safe operations, responsive UI

### New Components
- `main_app/core/logging_config.py` - Comprehensive logging system
- `main_app/core/async_manager.py` - Async connection & operation manager
- `main_app/ui/main_window.py` - Main GUI window (non-blocking)
- `main_app/main_gui.py` - GUI-first entry point

### Logging Features
- Automatic log rotation (10MB max, 5 backups)
- Real-time GUI display with color coding
- Thread-safe logging from multiple background threads
- Separate logs for main app, infrastructure, and devices

---

## PyTango 10.0.3 Migration (2024)

### Status
✅ **Migration Status: SUCCESSFUL with minor configuration needed**

### Key Requirements
- PyTango 10.0.3 requires omniORB configuration for device server startup
- Created `OMNIORB.CFG` configuration file
- Updated command line usage to include `-ORBconfigFile` parameter

### Compatibility
- ✅ All device servers verified working
- ✅ 100% backward compatible with proper config
- ✅ All batch files compatible with updates

### Tested Device Categories
- Power Management: DS_Netio_pdu ✅
- Motion Control: DS_Standa_Motor, DS_OWIS_PS90 ✅
- Cameras: DS_Basler_camera, DS_ANDOR_CCD ✅
- Control Systems: DS_LaserPointing, DS_Experiment ✅

---

## iTest Device Server - easy-scpi Refactoring (2024)

### Overview
Successfully refactored the iTest Device Server to use **easy-scpi** (PyVISA backend) instead of raw TCP sockets.

### Key Changes
- Migrated from raw TCP socket implementation to PyVISA-based easy-scpi
- Uses `TCPIP::<host>::<port>::SOCKET` VISA resource string
- 100% API backward compatible - all existing code works unchanged

### Benefits
- **Improved Reliability**: PyVISA handles timeouts and recovery automatically
- **Industry Standards**: Uses VISA (Virtual Instrument Software Architecture)
- **Enhanced Features**: Automatic resource discovery, connection pooling
- **Future-Proof**: Easy to extend for other VISA-supported instruments

### Testing
- 30 comprehensive unit tests
- All tests pass
- Full API compatibility verified

---

## Taurus Deprecation Fixes (2024)

### Issues Addressed
1. **Taurus Deprecation Warning**: `getConfig is deprecated since 4.0`
2. **NETIO Client Launch Failure**: Device attribute access errors

### Solutions Implemented
- Created warning suppression utility (`fixes/taurus_warnings_fix.py`)
- Implemented safe device attribute accessors with error handling
- Updated NETIO and Numato GPIO widgets for graceful error handling

### Benefits
- Cleaner logs (no more deprecation warnings)
- Improved reliability (widgets no longer crash on device disconnection)
- Better user experience (clear error messages)

---

## WARP Auto-Update Documentation (2024)

### Overview
Integrated automatic WARP.md maintenance into the git commit process.

### Features
- Automatic WARP.md updates during git commits
- Smart detection of when updates are needed
- Context-aware updates based on actual changes
- Non-blocking workflow (commits proceed even if update fails)

### Triggers
- New/modified Python scripts in `bin/`
- Changes to `pyproject.toml` or `requirements.txt`
- Deleted files referenced in WARP.md

---

## File Structure Changes

### Root Directory Cleanup
- Moved legacy files to dedicated `legacy/` folder
- Cleaned `bin/` to essential startup scripts only
- Created modular `main_app/` structure
- Organized documentation into consolidated files

### Key Directories
```
pyconlyse/
├── bin/                      # Essential startup scripts
├── main_app/                 # Modular application
│   ├── core/                 # Configuration and utilities
│   ├── managers/             # Business logic
│   ├── ui/                   # User interface
│   └── tests/                # Test suite
├── DeviceServers/            # Tango device servers
├── legacy/                   # Archived legacy files
└── logs/                     # Log files
```

---

## Summary

The PyConlyse project has undergone significant improvements:

1. **Architecture**: Clean modular structure with proper separation of concerns
2. **User Experience**: GUI-first, non-blocking operations with comprehensive feedback
3. **Reliability**: Updated to latest PyTango, improved error handling
4. **Standards**: Migration to industry-standard protocols (VISA/easy-scpi)
5. **Maintainability**: Comprehensive logging, testing, and documentation
6. **Automation**: Auto-updating documentation integrated into git workflow

**The project is now ready for production use with a modern, maintainable codebase!** 🎉
