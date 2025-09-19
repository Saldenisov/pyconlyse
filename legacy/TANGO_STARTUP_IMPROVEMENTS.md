# Tango Startup Improvements

## Overview

Implemented **Windows auto-startup for Tango Database and Starter** so they run as background services when Windows boots. The `main_ctrl.py` GUI detects these existing services and uses them, only starting Tango manually if services are not running or have crashed.

## Key Changes Made

### 1. Enhanced `start_infrastructure` Method
- Now calls a dedicated `_start_database_and_starter` method
- Provides better progress feedback to the user
- More robust error handling

### 2. New `_start_database_and_starter` Method
**Starts the following components in order:**
1. **Tango Database** (`start-db.bat`)
2. **Tango Starter** (`Starter.exe <hostname>`) 
3. **Astor** (`start-astor.bat`) for DeviceServer management

**Features:**
- Automatic hostname detection using `socket.gethostname()`
- Proper waiting times between component starts (5s for DB, 3s for Starter)
- Environment variable validation (`TANGO_ROOT` must be set)
- Individual process tracking for each component

### 3. Improved `stop_infrastructure` Method
- Stops components in reverse order: Astor → Starter → Database
- Graceful shutdown with fallback to force termination
- Better error handling and logging

### 4. Enhanced Status Monitoring
- New `get_status` method shows individual component status
- Added detailed status labels in the UI:
  - Database status
  - Starter status  
  - Astor status
  - Overall Tango connectivity
- Color-coded status indicators (green=running, gray=not started, red=error)

### 5. Improved UI Status Display
- More detailed status panel showing each Tango component individually
- Real-time status updates every 5 seconds
- Better visual feedback with color coding

## How It Works

### 🚀 **Auto-Startup on Application Launch:**

When you run `main_ctrl.py` (or use `start_main_ctrl_with_tango.cmd`):

1. **Application starts** - Main control interface initializes
2. **Auto-check** - Checks if Tango is already running
3. **Auto-start sequence** (if not already running):
   - **Database starts first** - Essential Tango foundation
   - **Wait 5 seconds** - Database initialization
   - **Starter launches** - DeviceServer management (`Starter.exe everest`)
   - **Wait 3 seconds** - Starter initialization  
   - **Astor starts** - DeviceServer GUI manager
4. **UI updates** - Button states and status indicators adjust automatically
5. **Auto-configure Astor** - Astor configuration runs after 15 seconds
6. **Status monitoring** - Real-time updates every 5 seconds

### 💡 **Manual Control Still Available:**

Users can still manually use the **"Start Tango"** and **"Stop Tango"** buttons if needed.

## Benefits

✅ **Proper Tango Architecture** - Database + Starter + Astor working together
✅ **DeviceServer Management** - Astor can now properly manage servers via Starter
✅ **Better Error Handling** - Individual component tracking and error reporting
✅ **User Feedback** - Clear progress indication and status display
✅ **Robust Startup** - Proper timing and dependency handling

## Environment Requirements

Ensure these environment variables are set:
- `TANGO_ROOT` - Path to Tango installation
- `TANGO_HOST` - Tango database host (e.g., "everest:10000")

## Usage

### 🎯 **Recommended: Auto-Startup (New!)**
```cmd
cd C:\dev\pyconlyse\bin
start_main_ctrl_with_tango.cmd
```
**OR directly:**
```cmd
cd C:\dev\pyconlyse\bin
python main_ctrl.py
```

**What happens automatically:**
- Validates environment variables
- Activates conda environment
- Starts main control GUI
- **Auto-starts Tango Database + Starter + Astor**
- Shows real-time status updates

### 🔧 **Manual Control (Still Available):**
1. **Start Tango Infrastructure:**
   - Click "Start Tango" button in main control (if not auto-started)
   - Watch progress dialog for each component
   - Check status panel for individual component states

2. **Manage DeviceServers:**
   - Open Astor GUI (launched automatically)
   - Configure and start DeviceServers through Astor
   - Use "DeviceServers" tab in main control for manual management

3. **Monitor Status:**
   - Status panel updates every 5 seconds
   - Individual component states shown with color coding
   - Overall connectivity status indicates Tango database accessibility

## Troubleshooting

**If Starter fails to start:**
- Check hostname resolution (`socket.gethostname()` should return your machine name)
- Ensure no Docker-related hostname conflicts in hosts file
- Verify TANGO_ROOT points to correct Tango installation

**If Database connection fails:**
- Check TANGO_HOST environment variable
- Verify Tango database is running and accessible
- Check firewall/network connectivity

**If DeviceServers don't start in Astor:**
- Ensure Starter is running (required for DeviceServer management)
- Check Astor configuration and device server definitions
- Verify Python conda environments are accessible

## Next Steps

With this implementation, you now have:
- Integrated Tango infrastructure startup (DB + Starter + Astor)
- Proper DeviceServer management through Tango's intended architecture
- Real-time monitoring and status feedback
- Robust error handling and process management

The system now follows Tango best practices where Astor manages DeviceServers through the Starter, rather than bypassing this architecture with manual batch files.