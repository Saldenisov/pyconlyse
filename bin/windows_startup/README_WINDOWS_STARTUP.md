# Tango Windows Auto-Startup Setup

## 🎯 **Objective**

Configure Tango Database and Starter to **automatically start when Windows boots**, so they're always running in the background. The PYCONLYSE main control GUI will detect and use these existing services, only starting them manually if they're not running or have crashed.

## 🚀 **Quick Setup (Recommended)**

### Step 1: Run the Setup Script
Open **PowerShell as Administrator** and run:

```powershell
cd C:\dev\pyconlyse\bin\windows_startup
.\setup_tango_windows_startup.ps1
```

This will:
- ✅ Create Windows Task Scheduler job
- ✅ Configure auto-start on boot (30-second delay)
- ✅ Enable automatic restart on crash (up to 3 attempts)
- ✅ Test the setup immediately

### Step 2: Test the Setup
```powershell
# Test immediately
Start-ScheduledTask -TaskName "TangoInfrastructureStartup"

# Or restart Windows and check if Tango is running
# Check: netstat -an | findstr :10000
# Check: tasklist | findstr Starter.exe
```

## 🔧 **Manual Setup Options**

### Option 1: Windows Startup Folder
Copy the startup script to Windows Startup folder:

```cmd
# Copy to current user startup
copy "C:\dev\pyconlyse\bin\windows_startup\tango_windows_startup.cmd" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"

# Or copy to all users startup (requires admin)
copy "C:\dev\pyconlyse\bin\windows_startup\tango_windows_startup.cmd" "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup\"
```

### Option 2: Manual Task Scheduler
1. Open **Task Scheduler** (taskschd.msc)
2. Create Basic Task
3. **Name:** TangoInfrastructureStartup
4. **Trigger:** When the computer starts
5. **Action:** Start a program
6. **Program:** `cmd.exe`
7. **Arguments:** `/c "C:\dev\pyconlyse\bin\windows_startup\tango_windows_startup.cmd"`
8. **Settings:** Run with highest privileges, Run whether user is logged on or not

## 📁 **File Structure**

```
C:\dev\pyconlyse\bin\windows_startup\
├── tango_windows_startup.cmd           # Main startup script
├── start_tango_db_service.cmd          # Database startup
├── start_tango_starter_service.cmd     # Starter startup  
├── setup_tango_windows_startup.ps1     # Automated setup
└── README_WINDOWS_STARTUP.md           # This file

Logs created:
├── tango_windows_startup.log           # Main log
├── tango_db_startup.log                # Database log
└── tango_starter_startup.log           # Starter log
```

## 🔍 **How It Works**

### On Windows Boot:
1. **30-second delay** after Windows starts (allows system to stabilize)
2. **Check environment** - Validates TANGO_ROOT is set
3. **Database startup:**
   - Checks if port 10000 is already in use
   - If not, starts `%TANGO_ROOT%\bin\start-db.bat`
   - Waits 10 seconds and verifies startup
4. **Starter startup:**
   - Waits for Database to be available (up to 60 seconds)
   - Checks if Starter.exe is already running
   - If not, starts `%TANGO_ROOT%\bin\Starter.exe <hostname>`
   - Verifies startup

### In main_ctrl.py:
- **Detects existing services** when GUI starts
- **Only starts manually** if services not detected
- **Uses existing services** if already running
- **Starts Astor GUI** automatically if needed

## ✅ **Verification**

### Check if Windows Startup is Working:
```cmd
# Check scheduled task
schtasks /query /tn "TangoInfrastructureStartup"

# Check if database is running
netstat -an | findstr :10000

# Check if starter is running  
tasklist | findstr Starter.exe

# Check log files
type C:\dev\pyconlyse\bin\windows_startup\tango_windows_startup.log
```

### Check main_ctrl.py Detection:
1. Start `python main_ctrl.py`
2. Look for log messages:
   - ✅ "Tango Database already running (Windows service)"
   - ✅ "Tango Starter already running (Windows service)"
   - ✅ "System Running (Windows Services)"

## 🛠 **Troubleshooting**

### Database Won't Start
- **Check TANGO_HOST:** Should be set to `everest:10000` or `<hostname>:10000`
- **Check port 10000:** `netstat -an | findstr :10000` should show listening
- **Check TANGO_ROOT:** Must point to valid Tango installation
- **Check log:** `tango_db_startup.log` for error details

### Starter Won't Start
- **Check hostname:** `hostname` command should return correct name (e.g., "everest")
- **Check database first:** Starter needs database running
- **Check processes:** `tasklist | findstr Starter.exe`
- **Check log:** `tango_starter_startup.log` for error details

### Task Scheduler Issues
```cmd
# Check task status
schtasks /query /tn "TangoInfrastructureStartup" /fo LIST /v

# Run task manually
schtasks /run /tn "TangoInfrastructureStartup"

# Delete task (if needed)
schtasks /delete /tn "TangoInfrastructureStartup" /f
```

### main_ctrl.py Still Tries to Start Tango
- **Wait 2-3 seconds** after GUI opens for detection to complete
- **Check status panel** should show individual component status
- **Check activity log** for detection messages

## 🗑 **Removal**

To remove Windows auto-startup:

```cmd
# Remove scheduled task
schtasks /delete /tn "TangoInfrastructureStartup" /f

# Or remove from startup folder
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\tango_windows_startup.cmd"
```

## 📊 **Expected Behavior**

### After Windows Boot:
- Tango Database running on port 10000
- Tango Starter.exe process running  
- Services ready for PYCONLYSE to connect

### When Starting main_ctrl.py:
- **If services running:** "✓ Already running" messages, immediate ready state
- **If services crashed:** Attempts to restart them
- **If services never started:** Starts them normally

## 🎉 **Result**

**Tango Database and Starter will automatically start every time Windows boots!**

Users can restart Windows, login, and immediately use PYCONLYSE without any manual Tango startup steps. The infrastructure is always ready! 🚀