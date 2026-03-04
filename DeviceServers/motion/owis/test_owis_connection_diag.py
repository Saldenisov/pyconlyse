#!/usr/bin/env python
"""
OWIS PS90 Connection Diagnostic Tool
Tests connection and basic communication with the controller
"""

import ctypes
import sys
from pathlib import Path
from time import sleep

# Configuration
DLL_PATH = r"C:\dev\pyconlyse\DeviceServers\motion\owis\drivers\ps90_64.dll"
CONTROL_UNIT_ID = 1
COM_PORT = 7
INTERFACE = 0  # USB or serial port

# Test different baudrates
BAUDRATES_TO_TEST = [115200, 19200, 9600]

def error_OWIS_ps90(code: int, type: int) -> str:
    """Decode OWIS error codes"""
    errors_connections = {
        0: "no error",
        -1: "function error",
        -3: "invalid serial com_port (com_port is not found)",
        -4: "access denied (com_port is busy)",
        -5: "no response from control unit",
        -7: "control unit with the specified serial number is not found",
        -8: "no connection to modbus/tcp",
        -9: "no connection to tcp/ip socket",
    }
    errors_functions = {
        0: "no error",
        -1: "function error",
        -2: "communication error",
        -3: "syntax error",
        -4: "axis is in wrong state",
        -9: "OWISid chip is not found",
        -10: "OWISid parameter is empty (not defined)",
    }
    if code > 0 or (code not in errors_connections and code not in errors_functions):
        return f"Unknown error code: {code}"
    if type not in [0, 1]:
        return "Wrong type of error"
    if code != 0:
        return errors_connections[code] if type == 0 else errors_functions[code]
    return "no error"

def main():
    print("=" * 70)
    print("=== OWIS PS90 Connection Diagnostic ===")
    print("=" * 70)
    print(f"DLL Path: {DLL_PATH}")
    print(f"Control Unit ID: {CONTROL_UNIT_ID}")
    print(f"COM Port: COM{COM_PORT}")
    print(f"Interface: {INTERFACE} (USB/Serial)")
    print()
    
    # Load DLL
    print("Loading OWIS DLL...")
    try:
        lib = ctypes.WinDLL(DLL_PATH)
        lib.PS90_GetPositionEx.restype = ctypes.c_double
        print("  ✓ DLL loaded successfully")
    except Exception as e:
        print(f"  ✗ Failed to load DLL: {e}")
        return
    
    print()
    
    # Test each baudrate
    for baudrate in BAUDRATES_TO_TEST:
        print("-" * 70)
        print(f"Testing baudrate: {baudrate}")
        print("-" * 70)
        
        # Disconnect if previously connected
        control_unit = ctypes.c_long(CONTROL_UNIT_ID)
        lib.PS90_Disconnect(control_unit)
        sleep(0.5)
        
        # Attempt connection
        print(f"  Connecting to COM{COM_PORT} at {baudrate} baud...")
        sleep(0.02)
        res = lib.PS90_Connect(
            ctypes.c_long(CONTROL_UNIT_ID),
            ctypes.c_long(INTERFACE),
            ctypes.c_long(COM_PORT),
            ctypes.c_long(baudrate),
            ctypes.c_long(0),
            ctypes.c_long(0),
            ctypes.c_long(0),
            ctypes.c_long(0)
        ) * -1
        
        if res != 0:
            error_msg = error_OWIS_ps90(res, 0)
            print(f"  ✗ Connection failed: {error_msg}")
            continue
        
        print(f"  ✓ Connected successfully!")
        
        # Test reading position from axis 1
        print(f"  Testing communication: Reading position of axis 1...")
        sleep(0.02)
        axis = ctypes.c_long(1)
        pos = lib.PS90_GetPositionEx(control_unit, axis)
        
        # Check for read error
        read_error = lib.PS90_GetReadError(control_unit)
        
        if read_error != 0:
            error_msg = error_OWIS_ps90(read_error, 1)
            print(f"  ✗ Read failed: {error_msg}")
            print(f"  ✗ This baudrate does NOT work")
        else:
            print(f"  ✓ Read successful: Position = {pos:.3f} mm")
            print(f"  ✓ THIS BAUDRATE WORKS!")
            
            # Test all 4 axes
            print()
            print(f"  Testing all axes:")
            for test_axis in [1, 2, 3, 4]:
                sleep(0.01)
                test_axis_c = ctypes.c_long(test_axis)
                pos = lib.PS90_GetPositionEx(control_unit, test_axis_c)
                read_error = lib.PS90_GetReadError(control_unit)
                
                if read_error != 0:
                    error_msg = error_OWIS_ps90(read_error, 1)
                    print(f"    Axis {test_axis}: ✗ {error_msg}")
                else:
                    print(f"    Axis {test_axis}: ✓ Position = {pos:.3f} mm")
            
            # Disconnect
            print()
            print(f"  Disconnecting...")
            lib.PS90_Disconnect(control_unit)
            sleep(0.5)
            
            print()
            print("=" * 70)
            print(f"✓ SUCCESS: Use baudrate {baudrate} in your configuration!")
            print("=" * 70)
            return
        
        # Disconnect
        lib.PS90_Disconnect(control_unit)
        sleep(0.5)
        print()
    
    print("=" * 70)
    print("✗ FAILED: No working baudrate found")
    print("=" * 70)
    print()
    print("Troubleshooting suggestions:")
    print("1. Power cycle the OWIS PS90 controller")
    print("2. Check USB cable connection")
    print("3. Verify COM port in Device Manager")
    print("4. Try connecting with OWISoft official software first")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
    except Exception as e:
        print(f"\n\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
