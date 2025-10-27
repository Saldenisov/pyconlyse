#!/usr/bin/env python3
"""
Configure iTest PSU Tab Layout in Tango DB

This script sets up the tab_config property for the iTest PSU device,
which defines which slots appear in each tab (V0, VD2, REF) and their default values.

Usage:
    python configure_itest_tabs.py
"""

import tango
import json

def configure_tabs(device_name, config):
    """Configure tab layout for iTest PSU device"""
    try:
        db = tango.Database()
        
        # Convert config to JSON string
        config_json = json.dumps(config)
        
        print(f"Setting tab_config for device: {device_name}")
        print(f"Configuration: {json.dumps(config, indent=2)}")
        
        # Set the property
        db.put_device_property(device_name, {"tab_config": config_json})
        
        print(f"\n✅ Successfully configured tabs for {device_name}")
        print("\nRefresh your web browser to see the changes.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    # Configuration for your iTest PSU
    DEVICE_NAME = "ELYSE/pdu/iTest"
    
    # Example configuration:
    # - V0 tab shows slots 1, 2, 3 with default currents
    # - VD2 tab shows slots 4, 5 with default currents
    # - REF tab shows slots 6, 7, 8 with default currents
    
    config = {
        "V0": {
            "slots": [1, 2, 3],
            "defaults": {
                "1": 0.5,
                "2": 1.0,
                "3": 0.75
            }
        },
        "VD2": {
            "slots": [4, 5],
            "defaults": {
                "4": 2.0,
                "5": 1.5
            }
        },
        "REF": {
            "slots": [6, 7, 8],
            "defaults": {
                "6": 0.1,
                "7": 0.2,
                "8": 0.15
            }
        }
    }
    
    print("=" * 60)
    print("iTest PSU Tab Configuration Utility")
    print("=" * 60)
    print()
    
    # Show current configuration
    try:
        db = tango.Database()
        prop_values = db.get_device_property(DEVICE_NAME, 'tab_config')
        if 'tab_config' in prop_values and prop_values['tab_config']:
            current = prop_values['tab_config'][0] if isinstance(prop_values['tab_config'], list) else prop_values['tab_config']
            if current:
                print("Current configuration:")
                print(json.dumps(json.loads(current), indent=2))
                print()
    except Exception as e:
        print(f"Note: Could not read current configuration ({e})")
        print()
    
    # Confirm before applying
    response = input(f"Apply new configuration to {DEVICE_NAME}? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        configure_tabs(DEVICE_NAME, config)
    else:
        print("Configuration cancelled.")
        print("\nTo manually configure, edit the 'config' dictionary in this script and run again.")
