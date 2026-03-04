#!/usr/bin/env python
"""
Add retry parameters to OWIS PS90 device in Tango database
"""

from tango import Database

# Connect to Tango database
db = Database()

# Device name
device_name = "manip/general/DS_OWIS_PS90"

# Get current properties
current_props = db.get_device_property(device_name, ["max_retries", "retry_delay"])
print(f"Current max_retries: {current_props.get('max_retries', 'Not set')}")
print(f"Current retry_delay: {current_props.get('retry_delay', 'Not set')}")

# Update parameters
new_props = {
    "max_retries": 3,
    "retry_delay": 1.0
}
db.put_device_property(device_name, new_props)

# Verify update
updated_props = db.get_device_property(device_name, ["max_retries", "retry_delay"])
print(f"\nUpdated max_retries: {updated_props['max_retries']}")
print(f"Updated retry_delay: {updated_props['retry_delay']}")

print("\n✓ Retry parameters updated successfully!")
print("Please restart the device server for changes to take effect.")
