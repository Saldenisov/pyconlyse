#!/usr/bin/env python3
"""
Test script to demonstrate iTest config property usage.

This script shows how to set the config property in the Tango Database
for the iTest PSU device server to map slot names and set current limits.
"""

import json
import sys
from pathlib import Path

# Add the project root to path
app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

try:
    import tango
    from tango import Database
except ImportError:
    print("PyTango not installed. Install with: pip install pytango")
    sys.exit(1)

def set_itest_config(device_name: str = "elyse/pdu/itest"):
    """Set the config property for iTest device with slot mappings and limits."""
    
    # Your config with slot names and current limits
    config_data = {
        "Slot 1": ("T1-1", [-5.0, 15.0]),
        "Slot 3": ("T1-2", [-5.0, 15.0]),
        "Slot 5": ("H1", [-5.0, 15.0]),
        "Slot 6": ("V1", [-5.0, 15.0]),
        "Slot 7": ("Dip1", [-5.0, 15.0]),
        "Slot 9 (2819)": ("Dip2", [-5.0, 15.0]),
        "Slot 11 (2811)": ("Bcd1", [-5.0, 15.0]),
        "Slot 12 (2811)": ("Bcd2", [-5.0, 15.0])
    }
    
    # Convert to JSON string
    config_json = json.dumps(config_data)
    
    try:
        # Connect to Tango Database
        db = Database()
        
        # Set the config property
        db.put_device_property(device_name, {"config": [config_json]})
        
        print(f"✓ Successfully set config property for device: {device_name}")
        print(f"Config data: {config_json}")
        
        # Verify the property was set
        props = db.get_device_property(device_name, "config")
        if props["config"]:
            print(f"✓ Verified: config property is set to: {props['config'][0]}")
        else:
            print("✗ Warning: config property appears to be empty after setting")
            
    except Exception as e:
        print(f"✗ Error setting config property: {e}")
        return False
    
    return True

def get_itest_config(device_name: str = "elyse/pdu/itest"):
    """Get and display the current config property."""
    try:
        db = Database()
        props = db.get_device_property(device_name, "config")
        
        if props["config"]:
            config_str = props["config"][0]
            print(f"Current config for {device_name}:")
            print(config_str)
            
            # Parse and pretty print
            try:
                config_data = json.loads(config_str)
                print("\nParsed config:")
                for slot, (name, limits) in config_data.items():
                    print(f"  {slot} -> '{name}' (limits: {limits[0]:.1f}A to {limits[1]:.1f}A)")
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse config JSON: {e}")
                
        else:
            print(f"No config property set for {device_name}")
            
    except Exception as e:
        print(f"Error getting config property: {e}")

def test_device_connection(device_name: str = "elyse/pdu/itest"):
    """Test connection to the iTest device and display current attributes."""
    try:
        device = tango.DeviceProxy(device_name)
        
        print(f"Testing connection to {device_name}...")
        state = device.state()
        print(f"✓ Device state: {state}")
        
        # Read attributes if device is running
        if state != tango.DevState.FAULT:
            try:
                names = device.names
                print(f"Slot names: {list(names)}")
            except Exception as e:
                print(f"Could not read names: {e}")
                
            try:
                limits = device.current_limits
                print(f"Current limits: {list(limits)}")
                # Parse limits pairs
                limit_pairs = [(limits[i], limits[i+1]) for i in range(0, len(limits), 2)]
                print("Parsed limits:")
                for i, (min_val, max_val) in enumerate(limit_pairs):
                    print(f"  Slot {i+1}: {min_val:.1f}A to {max_val:.1f}A")
            except Exception as e:
                print(f"Could not read current_limits: {e}")
                
    except Exception as e:
        print(f"✗ Error connecting to device: {e}")

if __name__ == "__main__":
    device_name = "elyse/pdu/itest"
    
    print("=== iTest Config Property Test ===\n")
    
    # Get current config
    print("1. Current config:")
    get_itest_config(device_name)
    
    print("\n2. Setting new config...")
    success = set_itest_config(device_name)
    
    if success:
        print("\n3. Testing device connection...")
        test_device_connection(device_name)
        
        print("\n4. Updated config:")
        get_itest_config(device_name)
        
        print(f"""
=== Instructions ===
1. Restart the iTest device server to apply the new config
2. Launch the PyQt5 client: python DS_iTest_client.py
3. The spinbox controls will now use the limits from config:
   - T1-1, T1-2, H1, V1: -5.0A to 15.0A
   - Dip1, Dip2: -5.0A to 15.0A  
   - Bcd1, Bcd2: -5.0A to 15.0A

To restart the device server:
  python DS_itest_psu.py elyse/pdu/itest
""")