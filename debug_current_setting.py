#!/usr/bin/env python3
"""
Debug script to test direct SCPI communication for current setting and measurement.
"""

import sys
sys.path.append("DeviceServers/power/iTest")

from scpi_client import ITestSCPI

def test_current_operations():
    """Test current setting and measurement directly via SCPI"""
    host = "10.20.30.24"
    port = 5025
    slot_id = 1
    
    print(f"=== Testing Current Operations on Slot {slot_id} ===")
    
    try:
        # Connect to device
        print(f"Connecting to {host}:{port}...")
        scpi = ITestSCPI(host, port=port, timeout=5.0)
        scpi.connect()
        print("✓ Connected successfully")
        
        # Test current measurement before setting
        print(f"\n1. Measuring initial current on slot {slot_id}:")
        initial_current = scpi.measure_current(slot_id)
        print(f"   Initial current: {initial_current:.6f}A ({initial_current*1000:.3f}mA)")
        
        # Check current output state
        print(f"\n2. Checking output state for slot {slot_id}:")
        state = scpi.get_output_state(slot_id)
        print(f"   Output state: {'ON' if state else 'OFF'}")
        
        # Set current to 10mA
        target_current = 0.010  # 10mA
        print(f"\n3. Setting current to {target_current:.3f}A ({target_current*1000:.1f}mA):")
        scpi.set_current(slot_id, target_current)
        print(f"   ✓ Current setpoint sent")
        
        # Try to read back the setpoint (may not be supported)
        print(f"\n4. Reading back current setpoint:")
        try:
            setpoint = scpi.get_current_setpoint(slot_id)
            print(f"   Current setpoint: {setpoint:.6f}A ({setpoint*1000:.3f}mA)")
        except Exception as e:
            print(f"   Setpoint readback not supported: {e}")
        
        # Measure current after setting
        print(f"\n5. Measuring current after setting:")
        measured_current = scpi.measure_current(slot_id)
        print(f"   Measured current: {measured_current:.6f}A ({measured_current*1000:.3f}mA)")
        
        # Turn output ON if it's not already ON
        if state == 0:
            print(f"\n6. Turning output ON:")
            scpi.output_on(slot_id)
            print(f"   ✓ Output turned ON")
            
            # Measure current with output ON
            print(f"\n7. Measuring current with output ON:")
            current_with_output_on = scpi.measure_current(slot_id)
            print(f"   Current with output ON: {current_with_output_on:.6f}A ({current_with_output_on*1000:.3f}mA)")
        
        # Check if there's a load connected
        print(f"\n8. Analysis:")
        if abs(measured_current) < 0.001:  # Less than 1mA
            print("   ⚠️  Very low current measured - possible causes:")
            print("      - No load connected to the output")
            print("      - Output is in current limiting mode")
            print("      - PSU requires output to be ON before sourcing current")
            print("      - PSU is in voltage mode, not current mode")
        else:
            print(f"   ✓ Significant current measured: {measured_current*1000:.3f}mA")
            
        # Try some diagnostic commands
        print(f"\n9. Additional diagnostics:")
        try:
            # Try to get instrument ID
            print("   Trying *IDN? command...")
            # This would require adding a query method to the SCPI client
        except Exception as e:
            print(f"   Diagnostic failed: {e}")
        
        scpi.close()
        print(f"\n✓ Connection closed")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_current_operations()