#!/usr/bin/env python3
"""Check and debug tab_config property in Tango DB"""

import tango
import json

DEVICE_NAME = "ELYSE/pdu/iTest"

try:
    db = tango.Database()
    
    print(f"Checking tab_config property for: {DEVICE_NAME}")
    print("=" * 60)
    
    # Read the property
    prop_values = db.get_device_property(DEVICE_NAME, 'tab_config')
    
    print(f"\nRaw property value:")
    print(f"Type: {type(prop_values)}")
    print(f"Content: {prop_values}")
    
    if 'tab_config' in prop_values:
        print(f"\ntab_config key found in result")
        print(f"Value type: {type(prop_values['tab_config'])}")
        print(f"Value: {prop_values['tab_config']}")
        
        if prop_values['tab_config']:
            # Try to get the string value
            raw_value = prop_values['tab_config']
            if isinstance(raw_value, (list, tuple)) or hasattr(raw_value, '__iter__'):
                # Multi-line property: join all lines
                try:
                    # Try to iterate and join (works for list, tuple, StdStringVector)
                    config_str = ''.join(line for line in raw_value)
                    print(f"\nMulti-line property detected, joined {len(raw_value)} lines")
                except TypeError:
                    config_str = str(raw_value)
            else:
                config_str = str(raw_value)
            
            print(f"\nExtracted string:")
            print(f"Type: {type(config_str)}")
            print(f"Length: {len(config_str) if config_str else 0}")
            print(f"Content: {config_str[:200]}..." if len(config_str) > 200 else f"Content: {config_str}")
            
            if config_str:
                # Try to parse as JSON
                try:
                    parsed = json.loads(config_str)
                    print(f"\n✅ Successfully parsed as JSON:")
                    print(json.dumps(parsed, indent=2))
                except json.JSONDecodeError as e:
                    print(f"\n❌ Failed to parse as JSON: {e}")
                    print(f"Check for syntax errors in the property value")
            else:
                print("\n⚠️ Property value is empty")
        else:
            print("\n⚠️ tab_config is empty or None")
    else:
        print("\n⚠️ tab_config key not found in property values")
        print("\nYou need to set the property. Use Jive or:")
        print(f'  db.put_device_property("{DEVICE_NAME}", {{"tab_config": "...json..."}})' )
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
