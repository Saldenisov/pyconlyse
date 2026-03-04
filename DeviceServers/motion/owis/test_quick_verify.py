#!/usr/bin/env python
"""
Quick verification that OWIS device server is working
"""

import time
from tango import DeviceProxy

DEVICE_NAME = "tango://localhost:10000/manip/general/DS_OWIS_PS90"

def main():
    print("=" * 70)
    print("=== OWIS PS90 Device Server Quick Verification ===")
    print("=" * 70)
    print(f"Device: {DEVICE_NAME}\n")
    
    # Connect
    print("1. Connecting to device server...")
    try:
        device = DeviceProxy(DEVICE_NAME)
        print(f"   ✓ Connected: {device.name()}")
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        return
    
    # Check state
    print("\n2. Checking device state...")
    try:
        state = device.state()
        status = device.status()
        print(f"   State: {state}")
        print(f"   Status: {status}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    # Read positions
    print("\n3. Reading positions of all axes...")
    for axis in [1, 2, 3, 4]:
        try:
            pos = device.read_position_axis(axis)
            print(f"   Axis {axis}: {pos:.3f} mm ✓")
        except Exception as e:
            print(f"   Axis {axis}: FAILED - {e}")
    
    # Test a small movement on axis 2
    print("\n4. Testing small movement on axis 2...")
    try:
        # Read current position
        current_pos = device.read_position_axis(2)
        print(f"   Current position: {current_pos:.3f} mm")
        
        # Move 1mm relative
        target_pos = current_pos + 1.0
        print(f"   Moving to: {target_pos:.3f} mm")
        
        result = device.move_axis([2, target_pos])
        print(f"   Command result: '{result}'")
        
        # Wait for movement
        print("   Waiting 3s for movement to complete...")
        time.sleep(3)
        
        # Read final position
        final_pos = device.read_position_axis(2)
        error = abs(final_pos - target_pos)
        print(f"   Final position: {final_pos:.3f} mm")
        print(f"   Position error: {error:.3f} mm")
        
        if error < 1.0:
            print("   ✓ Movement successful!")
        else:
            print("   ⚠ Large position error detected")
            
    except Exception as e:
        print(f"   ✗ Movement test failed: {e}")
    
    print("\n" + "=" * 70)
    print("Verification complete!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
    except Exception as e:
        print(f"\n\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
