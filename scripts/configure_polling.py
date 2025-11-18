#!/usr/bin/env python3
"""
Script to configure Tango polling for the iTest PSU device
"""

import taurus
import time

def configure_polling():
    """Configure Tango polling for attributes and commands"""
    print("=== Configuring Tango Polling ===")
    
    try:
        dev = taurus.Device('elyse/pdu/itest')
        print(f"Device: {dev}")
        print(f"Device state: {dev.state}")
        
        # Try to configure attribute polling
        print("\n1. Configuring attribute polling...")
        
        attributes_to_poll = [
            ('currents_meas', 100),     # 100ms
            ('currents_setpoint', 100), # 100ms  
            ('states', 100),            # 100ms
        ]
        
        for attr_name, period_ms in attributes_to_poll:
            try:
                print(f"   Setting {attr_name} polling to {period_ms}ms...")
                dev.poll_attribute(attr_name, period_ms)
                print(f"   ✓ {attr_name} polling configured")
            except Exception as e:
                print(f"   ✗ Failed to set {attr_name} polling: {e}")
        
        # Try to configure command polling for get_controller_status
        print("\n2. Configuring command polling...")
        try:
            print("   Setting get_controller_status command polling to 100ms...")
            dev.poll_command('get_controller_status', 100)
            print("   ✓ get_controller_status polling configured")
        except Exception as e:
            print(f"   ✗ Failed to set command polling: {e}")
        
        # Check current polling status
        print("\n3. Checking polling status...")
        try:
            polling_status = dev.polling_status()
            print(f"   Polling status: {polling_status}")
        except Exception as e:
            print(f"   Could not get polling status: {e}")
        
        # Test the polling by monitoring for a few seconds
        print("\n4. Testing polling (monitoring for 3 seconds)...")
        print("Time  | Current (mA) | Changed?")
        print("-" * 35)
        
        last_current = None
        changes = 0
        
        for i in range(10):
            currents = dev.read_attribute('currents_meas').value
            current_ma = currents[0] * 1000
            
            changed = ""
            if last_current is not None and abs(current_ma - last_current) > 0.001:
                changed = "✓ CHANGED"
                changes += 1
            
            print(f"{i*0.3:4.1f}  | {current_ma:8.3f}    | {changed}")
            last_current = current_ma
            time.sleep(0.3)
        
        print("-" * 35)
        print(f"Changes detected: {changes}")
        
        if changes > 0:
            print("✓ Polling appears to be working!")
        else:
            print("⚠️ No changes detected - polling may not be active")
            
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    configure_polling()