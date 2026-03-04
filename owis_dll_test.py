"""
OWIS PS90 Controller - Using ps90.dll SDK
Connect via Ethernet to 10.20.30.134:8777
"""
import ctypes
from ctypes import windll, c_double, c_long, create_string_buffer
import os
import sys

# Controller settings
CONTROLLER_INDEX = 2  # Use slot 2 for second controller
IP_ADDRESS = "10.20.30.134"
PORT = 8777
NEW_SERIAL = "25010013"  # Serial from raw socket test

# Path to DLL (64-bit version)
DLL_PATH = r"C:\Program Files (x86)\OWISoft\exe\x64\Release\ps90.dll"

def load_dll():
    """Load the ps90.dll"""
    if not os.path.exists(DLL_PATH):
        print(f"ERROR: DLL not found at {DLL_PATH}")
        sys.exit(1)
    
    # Add DLL directory to PATH for dependencies
    dll_dir = os.path.dirname(DLL_PATH)
    os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
    
    try:
        dll = windll.LoadLibrary(DLL_PATH)
        print(f"Loaded DLL: {DLL_PATH}")
        return dll
    except Exception as e:
        print(f"Failed to load DLL: {e}")
        sys.exit(1)

def main():
    dll = load_dll()
    
    # Define function return types for functions returning double
    dll.PS90_GetPositionEx.restype = ctypes.c_double
    dll.PS90_GetPosF.restype = ctypes.c_double
    
    print(f"\nAttempting to connect to OWIS PS90...")
    print(f"Target: {IP_ADDRESS}:{PORT}")
    
    # Try different connection methods
    result = -1
    
    # Method 1: SimpleConnect with serial number of the NEW controller
    print(f"\n[Method 1] PS90_SimpleConnect with serial '{NEW_SERIAL}'...")
    result = dll.PS90_SimpleConnect(CONTROLLER_INDEX, NEW_SERIAL.encode('ascii'))
    print(f"  Result: {result}")
    
    if result != 0:
        # Method 2: SimpleConnect with "net" - may find the new one on slot 2
        print(f"\n[Method 2] PS90_SimpleConnect with 'net' (unit {CONTROLLER_INDEX})...")
        result = dll.PS90_SimpleConnect(CONTROLLER_INDEX, b"net")
        print(f"  Result: {result}")
    
    if result != 0:
        # Method 3: PS90_Connect with port=-1 (LAN mode per SDK)
        print(f"\n[Method 3] PS90_Connect(unit={CONTROLLER_INDEX}, iface=0, port=-1)...")
        result = dll.PS90_Connect(CONTROLLER_INDEX, 0, -1, 115200, 0, 0, 0, 0)
        print(f"  Result: {result}")
    
    if result != 0:
        # Method 4: Try net:IP format
        net_ip = f"net:{IP_ADDRESS}"
        print(f"\n[Method 4] PS90_SimpleConnect with '{net_ip}'...")
        result = dll.PS90_SimpleConnect(CONTROLLER_INDEX, net_ip.encode('ascii'))
        print(f"  Result: {result}")
    
    if result != 0:
        # Method 5: Try using unit 1 with serial (in case unit 2 doesn't work)
        print(f"\n[Method 5] PS90_SimpleConnect unit=1 with serial '{NEW_SERIAL}'...")
        result = dll.PS90_SimpleConnect(1, NEW_SERIAL.encode('ascii'))
        if result == 0:
            print("  Connected on unit 1!")
    
    # Check connection
    if result == 0:
        print("\n*** CONNECTED SUCCESSFULLY! ***\n")
        
        # Get controller info
        str_buffer = create_string_buffer(64)
        
        # Get serial number
        dll.PS90_GetSerNumber(CONTROLLER_INDEX, str_buffer, 64)
        print(f"Serial Number: {str_buffer.value.decode('utf-8', errors='replace')}")
        
        # Get firmware version
        dll.PS90_GetBoardVersion(CONTROLLER_INDEX, str_buffer, 64)
        print(f"Firmware Version: {str_buffer.value.decode('utf-8', errors='replace')}")
        
        # Get error state
        error = dll.PS90_GetError(CONTROLLER_INDEX)
        print(f"Error State: {error}")
        
        # Check axis 1 state
        axis = 1
        state = dll.PS90_GetAxisState(CONTROLLER_INDEX, axis)
        print(f"\nAxis {axis} State: {state}")
        
        position = dll.PS90_GetPositionEx(CONTROLLER_INDEX, axis)
        print(f"Axis {axis} Position: {position}")
        
        # Disconnect
        dll.PS90_Disconnect(CONTROLLER_INDEX)
        print("\nDisconnected.")
        
    else:
        print(f"\n*** CONNECTION FAILED (result={result}) ***")
        
        # Get error message
        str_buffer = create_string_buffer(256)
        dll.PS90_GetMessage(CONTROLLER_INDEX, str_buffer, 256)
        msg = str_buffer.value.decode('utf-8', errors='replace')
        if msg:
            print(f"Error message: {msg}")
        
        print("\nTroubleshooting:")
        print("1. Ensure controller is powered on and connected to network")
        print("2. Verify IP address 10.20.30.134 is correct (ping should work)")
        print("3. Check firewall settings for port 8777")
        print("4. Try running as Administrator")

if __name__ == "__main__":
    main()
