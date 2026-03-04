#!/usr/bin/env python
"""
Update OWIS PS90 baudrate in Tango database
Changes baudrate from 9600 to 115200
"""

from tango import Database

# Connect to Tango database
db = Database()

# Device name
device_name = "manip/general/DS_OWIS_PS90"

# Get current property
current_baudrate = db.get_device_property(device_name, "baudrate")
print(f"Current baudrate: {current_baudrate['baudrate']}")

# Update to 115200
new_baudrate = 115200
db.put_device_property(device_name, {"baudrate": new_baudrate})

# Verify update
updated_baudrate = db.get_device_property(device_name, "baudrate")
print(f"Updated baudrate: {updated_baudrate['baudrate']}")

print("\n✓ Baudrate updated successfully!")
print("Please restart the device server for changes to take effect.")
