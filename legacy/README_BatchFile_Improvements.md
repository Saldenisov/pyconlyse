# PYCONLYSE Batch File Improvements

## Overview

This document describes the proposed improvements to the PYCONLYSE startup system, transitioning from manual DeviceServer management via batch files to proper Astor-managed automatic startup.

## Current Issues

### 1. Manual DeviceServer Management
- The current `start_tango.cmd` manually starts DeviceServers using individual batch files
- This bypasses Tango's built-in management capabilities (Astor/Starter)
- Creates maintenance overhead with many duplicate batch files

### 2. Code Duplication
- 40+ similar batch files with repetitive patterns
- Hard to maintain and update
- Inconsistent error handling across files

### 3. Startup Sequence Problems
- Fixed timeouts that may not work on all systems
- No proper dependency checking
- No centralized logging

### 4. Astor Not Utilized
- Astor is started but not configured to manage DeviceServers
- DeviceServers are started manually instead of being managed by Tango infrastructure

## Proposed Solution

### New Startup Scripts

#### 1. `start_tango_improved.cmd` (Windows Batch)
- **Enhanced error handling** with environment variable validation
- **Proper logging** with timestamps to `tango_startup.log`
- **Colored output** for better user experience
- **Sequential startup** with appropriate wait times
- **Removes manual DeviceServer startup** - relies on Astor instead

#### 2. `Start-TangoInfrastructure.ps1` (PowerShell)
- **Modern PowerShell implementation** with proper error handling
- **Parameter support** for customization (wait times, skip components)
- **Database connectivity testing** to ensure proper startup
- **Process tracking** for better management
- **Comprehensive logging** with multiple levels

#### 3. `start_deviceserver.cmd` (Unified Template)
- **Single template** for all DeviceServer types
- **Centralized configuration** mapping
- **Proper parameter validation**
- **Automatic logging** with device-specific log files
- **Environment validation**

#### 4. `configure_astor_startup.py` (Python Configuration)
- **Automatic Astor configuration** from Tango database
- **DeviceServer registration** with proper startup commands
- **Configuration file generation** for manual import
- **Dry-run mode** for testing

## Migration Strategy

### Phase 1: Infrastructure Setup
1. **Deploy new startup scripts** alongside existing ones
2. **Test new scripts** in development environment
3. **Configure Astor** using the Python configuration script

### Phase 2: Astor Configuration
1. **Run configuration script**: `python configure_astor_startup.py --dry-run`
2. **Review generated configuration**
3. **Apply configuration**: `python configure_astor_startup.py`
4. **Import configuration into Astor GUI** if automatic setup fails

### Phase 3: Transition
1. **Switch to new startup script**: Use `start_tango_improved.cmd` or `Start-TangoInfrastructure.ps1`
2. **Verify DeviceServers start automatically** via Astor
3. **Monitor logs** for any issues

### Phase 4: Cleanup
1. **Archive old batch files** (don't delete immediately)
2. **Update documentation** and user guides
3. **Remove old files** after verification period

## File Structure

```
bin/
├── start_tango_improved.cmd          # New batch startup script
├── Start-TangoInfrastructure.ps1     # PowerShell startup script
├── start_deviceserver.cmd            # Unified DeviceServer template
├── configure_astor_startup.py        # Astor configuration script
├── README_BatchFile_Improvements.md  # This documentation
├── tango_startup.log                 # Startup logs
├── astor_config.log                  # Configuration logs
├── astor_device_config.txt           # Generated Astor config
└── logs/                             # DeviceServer logs
    └── deviceserver_*.log
```

## Usage Instructions

### Using the Improved Batch Script
```cmd
cd C:\dev\pyconlyse\bin
start_tango_improved.cmd
```

### Using the PowerShell Script
```powershell
cd C:\dev\pyconlyse\bin
.\Start-TangoInfrastructure.ps1

# With options
.\Start-TangoInfrastructure.ps1 -WaitTime 10 -SkipJive
```

### Configuring Astor
```cmd
# Test configuration
python configure_astor_startup.py --dry-run

# Apply configuration
python configure_astor_startup.py
```

### Manual DeviceServer Startup (if needed)
```cmd
# Using the unified template
start_deviceserver.cmd ANDOR_CCD V0 FULL
start_deviceserver.cmd BASLER Cam1 MINIMAL
```

## Benefits

### 1. Proper Tango Architecture
- **Astor manages DeviceServers** as intended by Tango design
- **Automatic restart** of failed DeviceServers
- **Centralized management** through Astor GUI

### 2. Improved Maintainability
- **Single startup script** instead of 40+ files
- **Centralized configuration** in Python script
- **Template-based** DeviceServer startup

### 3. Better Error Handling
- **Environment validation** before startup
- **Database connectivity testing**
- **Comprehensive logging** for troubleshooting

### 4. Enhanced User Experience
- **Colored output** with progress indication
- **Clear instructions** for next steps
- **Process tracking** and status reporting

## Environment Variables Required

Ensure these environment variables are set:
- `TANGO_ROOT`: Tango installation directory
- `PYCONLYSE`: PyConlyse project root directory
- `ANACONDA`: Anaconda installation directory
- `PYCONLYSE_ENV`: Conda environment name

## Troubleshooting

### Common Issues

#### 1. Environment Variables Not Set
**Error**: "Environment variable X is not defined!"
**Solution**: Set the required environment variables in your system

#### 2. Tango Database Connection Failed
**Error**: "Could not connect to Tango Database"
**Solution**: 
- Ensure Tango Database is running
- Check `TANGO_HOST` environment variable
- Verify network connectivity

#### 3. DeviceServers Not Starting in Astor
**Error**: DeviceServers show as "Not running" in Astor
**Solution**:
- Check Astor configuration with `configure_astor_startup.py --dry-run`
- Import the generated `astor_device_config.txt` manually
- Verify Python conda environment is accessible

#### 4. Conda Environment Issues
**Error**: "conda activate failed"
**Solution**:
- Ensure Anaconda is properly installed
- Check `ANACONDA` and `PYCONLYSE_ENV` environment variables
- Test conda activation manually

## Monitoring and Logs

### Log Files
- `tango_startup.log`: Infrastructure startup logs
- `astor_config.log`: Astor configuration logs
- `logs/deviceserver_*.log`: Individual DeviceServer logs

### Monitoring DeviceServer Status
1. **Astor GUI**: Visual status of all DeviceServers
2. **Main Control GUI**: Device state monitoring
3. **Jive**: Detailed Tango device inspection

## Future Enhancements

### Potential Improvements
1. **Health checking** with automatic restart
2. **Performance monitoring** integration
3. **Configuration backup** and restore
4. **Remote management** capabilities
5. **Docker containerization** support

### Migration to Python
Consider migrating the entire startup system to Python for:
- Better cross-platform compatibility
- More robust error handling
- Integration with existing Python codebase
- Advanced configuration management

## Support and Contact

For issues or questions regarding the batch file improvements:
1. Check the log files for detailed error information
2. Review this documentation for troubleshooting steps
3. Test with dry-run modes before making changes
4. Keep backups of working configurations

---
*Last updated: 2025-01-18*