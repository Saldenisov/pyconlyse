#!/usr/bin/env python3
"""
Test script to monitor current readings with timestamps to verify 100ms polling
"""

import time
import taurus

def test_polling_frequency():
    """Monitor current readings to verify 100ms polling"""
    print("=== Testing 100ms Polling Frequency ===")
    
    try:
        dev = taurus.Device('elyse/pdu/itest')
        print(f"Device state: {dev.state}")
        
        print("\nMonitoring current readings for 2 seconds...")
        print("Timestamp (s)    | Slot 1 Current (mA) | Notes")
        print("-" * 55)
        
        start_time = time.time()
        last_current = None
        update_count = 0
        
        for i in range(20):  # Monitor for 2 seconds (20 x 100ms)
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Read current measurement
            currents = dev.read_attribute('currents_meas').value
            slot1_current_ma = currents[0] * 1000  # Convert to mA
            
            # Check if value changed
            notes = ""
            if last_current is not None:
                if abs(slot1_current_ma - last_current) > 0.001:  # > 1µA change
                    notes = "** UPDATED **"
                    update_count += 1
            else:
                notes = "** INITIAL **"
                update_count += 1
            
            print(f"{elapsed:8.3f}      | {slot1_current_ma:10.3f}      | {notes}")
            last_current = slot1_current_ma
            
            time.sleep(0.1)  # 100ms intervals
        
        print("-" * 55)
        print(f"Total updates observed: {update_count}")
        print(f"Expected updates (if polling works): ~20")
        print(f"Update rate: {(update_count/2.0):.1f} Hz")
        
        if update_count >= 15:
            print("✓ Polling appears to be working correctly (100ms or better)")
        elif update_count >= 5:
            print("⚠️ Polling working but slower than expected")
        else:
            print("✗ Polling not working - values are cached/stale")
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_polling_frequency()