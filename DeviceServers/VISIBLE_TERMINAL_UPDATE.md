# DeviceServer Visible Terminal Update

## 🎯 **Objective Completed**

Modified all DeviceServer executable and batch file wrappers to start Python device servers in **visible, non-minimized terminal windows** that can be manually monitored and closed.

## ✅ **What Was Changed**

### **C# Executable Wrappers**
- **DS_Basler_camera.exe** - Updated to launch in separate visible terminal
- **DS_Netio_pdu.exe** - Updated to launch in separate visible terminal

### **Batch File Wrappers**
- **DS_Basler_camera.bat** - Updated to use `start` command with visible window
- **DS_Netio_pdu.bat** - Updated to use `start` command with visible window

## 🔧 **Key Changes Made**

### **C# Wrappers Changes:**
1. **Changed from `/c` to `/k`** - Terminal stays open after command execution
2. **Added `UseShellExecute = true`** - Allows creating new terminal windows
3. **Set `WindowStyle = Normal`** - Ensures visible (not minimized) windows
4. **Added descriptive window titles** - Each terminal shows device server name and instance
5. **Removed process waiting** - Wrapper exits immediately after launching, doesn't block
6. **Enhanced user feedback** - Better messages about terminal control options

### **Batch File Changes:**
1. **Added `start` command** - Creates new terminal window
2. **Used `/k` flag** - Keeps terminal open for monitoring
3. **Added descriptive window titles** - Shows device server name and instance
4. **Better user instructions** - Clear guidance on how to control the device server

## 🖥️ **New Behavior**

### **Before (Old Behavior):**
- Device servers ran in hidden/minimized terminals
- Difficult to monitor output or manually stop
- Wrapper waited for device server to exit

### **After (New Behavior):**
- Device servers run in **visible, titled terminal windows**
- Easy to monitor real-time output and status
- Easy to manually stop using **Ctrl+C** or closing window
- Wrapper launches server and exits immediately
- Terminal titles clearly identify each device server instance

## 🎮 **User Control Options**

Users can now:

1. **Monitor device server output** in real-time
2. **Manually stop device servers** using:
   - `Ctrl+C` in the device server terminal
   - Closing the terminal window
   - Using Astor's device server management
3. **Identify device servers easily** by terminal window titles:
   - `DS_Basler_camera [instance_name]`
   - `DS_Netio_pdu [instance_name]`

## 📋 **Files Updated**

### **Source Code:**
- `DS_Basler_camera_wrapper.cs` - Modified launch behavior
- `DS_Netio_pdu_wrapper.cs` - Modified launch behavior

### **Executables:**
- `DS_Basler_camera_new.exe` - New version with visible terminals (7,680 bytes)
- `DS_Netio_pdu_new.exe` - New version with visible terminals (7,680 bytes)
- `DS_Basler_camera.exe` - Original version (7,168 bytes)
- `DS_Netio_pdu.exe` - Original version (7,168 bytes)

### **Batch Files:**
- `DS_Basler_camera.bat` - Updated to use visible terminals
- `DS_Netio_pdu.bat` - Updated to use visible terminals

## 🚀 **Usage Examples**

### **Starting a device server:**
```bash
# Using executable wrapper
DS_Basler_camera.exe 1_Cam1_V0

# Using batch file wrapper  
DS_Basler_camera.bat 1_Cam1_V0
```

### **Expected result:**
1. Wrapper shows startup information
2. New terminal window opens with title: `DS_Basler_camera [1_Cam1_V0]`
3. Device server runs in the visible terminal
4. Wrapper exits, leaving device server running independently

### **To stop a device server:**
- Press `Ctrl+C` in the device server terminal, or
- Close the terminal window, or  
- Use Astor to stop the device server

## 🎉 **Benefits**

- ✅ **Full visibility** - See device server output in real-time
- ✅ **Manual control** - Easy to stop device servers when needed
- ✅ **Better debugging** - Immediate access to error messages and logs
- ✅ **Astor compatibility** - Still works seamlessly with Astor
- ✅ **Clear identification** - Titled windows make it easy to identify device servers
- ✅ **Non-blocking operation** - Wrappers don't hang waiting for device servers

## 🔄 **Deployment**

To use the new visible terminal versions:

1. **Replace old executables** with the new versions:
   - Replace `DS_Basler_camera.exe` with `DS_Basler_camera_new.exe`
   - Replace `DS_Netio_pdu.exe` with `DS_Netio_pdu_new.exe`

2. **Batch files are already updated** and ready to use

3. **Refresh Astor** device server list if needed

**Note:** You can rename the `_new.exe` files to the original names after backing up the originals.

The device servers will now start in visible, manageable terminal windows! 🎊
