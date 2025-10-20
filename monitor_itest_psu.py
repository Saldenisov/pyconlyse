#!/usr/bin/env python3
"""
Monitor iTest PSU Device Server state and test basic operations
"""
import time
import tango
from tango import DeviceProxy, DevState

def main():
    device_name = "ELYSE/pdu/iTest"
    
    print("=" * 60)
    print("iTest PSU Device Server Monitor")
    print("=" * 60)
    
    try:
        dev = DeviceProxy(device_name)
        print(f"✓ Connected to device: {device_name}")
    except Exception as e:
        print(f"✗ Failed to connect to device {device_name}: {e}")
        return
    
    # Monitor device state
    print("\n--- Device State Monitoring ---")
    for i in range(10):
        try:
            state = dev.state()
            state_color = {
                DevState.OFF: "🔴 OFF",
                DevState.ON: "🟢 ON", 
                DevState.INIT: "🟡 INIT",
                DevState.STANDBY: "🟡 STANDBY",
                DevState.FAULT: "🔴 FAULT",
                DevState.RUNNING: "🔵 RUNNING"
            }.get(state, f"❓ {state}")
            
            print(f"[{i+1:2d}/10] Device state: {state_color}")
            
            if state == DevState.ON:
                print("🎉 Device is GREEN (ON) - connection successful!")
                break
            elif state == DevState.FAULT:
                try:
                    error = dev.last_error
                    comment = dev.last_comment
                    print(f"    Last error: {error}")
                    print(f"    Last comment: {comment}")
                except:
                    pass
                    
        except Exception as e:
            print(f"[{i+1:2d}/10] ✗ Failed to read state: {e}")
        
        time.sleep(2)
    
    # Test basic attributes if device is ON
    try:
        state = dev.state()
        if state == DevState.ON:
            print("\n--- Testing Device Attributes ---")
            
            try:
                host = dev.host_property
                print(f"Host: {host}")
            except Exception as e:
                print(f"Failed to read host_property: {e}")
            
            try:
                names = dev.names
                print(f"Slot names: {names}")
            except Exception as e:
                print(f"Failed to read names: {e}")
                
            try:
                states = dev.states
                print(f"Slot states: {states}")
            except Exception as e:
                print(f"Failed to read states: {e}")
                
            try:
                currents = dev.currents_meas
                print(f"Measured currents: {currents}")
            except Exception as e:
                print(f"Failed to read currents_meas: {e}")
                
        else:
            print(f"\n❌ Device not ready (state: {state})")
            print("   Connection to PSU hardware likely failed")
            
    except Exception as e:
        print(f"Error during attribute testing: {e}")
    
    print("\n--- Test Complete ---")
    print("Tips to fix yellow/STANDBY state:")
    print("1. Check PSU hardware is powered on")
    print("2. Verify network connectivity to 10.20.30.24:5025")
    print("3. Check device server console logs for SCPI errors")
    print("4. Try manual SCPI connection test")

if __name__ == "__main__":
    main()