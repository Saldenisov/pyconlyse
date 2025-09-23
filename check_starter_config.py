#!/usr/bin/env python3
"""Script to check and optionally modify TANGO Starter configuration properties
to reduce ReadProcessMemory issues on Windows.
"""

import sys

# Add the pyconlyse path to find our modules
sys.path.append(r"C:\dev\pyconlyse")

try:
    import tango
    from tango import Database, DeviceProxy

    def check_starter_config():
        """Check current Starter device configuration."""
        try:
            # Connect to TANGO database
            db = Database()
            print("Connected to TANGO database successfully")

            # Get all devices of class DServer (which includes Starter)
            device_list = db.get_device_exported_for_class("DServer")
            print(f"Found {len(device_list)} DServer devices:")

            starter_devices = [dev for dev in device_list if "Starter" in dev]
            if not starter_devices:
                print("No Starter devices found in database")
                return None

            for device_name in starter_devices:
                print(f"\nAnalyzing device: {device_name}")
                try:
                    # Try to get device properties
                    prop_list = db.get_device_property_list(device_name, "*")
                    print(f"Available properties: {prop_list}")

                    # Check specific properties that might affect process monitoring
                    interesting_props = [
                        "UseEvents",
                        "fireFromDbase",
                        "serverStartupTimeout",
                        "interStartupLevelWait",
                        "AutoRestartDuration",
                    ]

                    for prop in interesting_props:
                        try:
                            value = db.get_device_property(device_name, [prop])
                            if value.get(prop):
                                print(f"  {prop} = {value[prop][0]}")
                            else:
                                print(f"  {prop} = (not set)")
                        except Exception as e:
                            print(f"  {prop} = (error: {e})")

                except Exception as e:
                    print(f"Error accessing device {device_name}: {e}")

        except Exception as e:
            print(f"Error connecting to TANGO database: {e}")
            return False

        return True

    def modify_starter_config():
        """Modify Starter configuration to reduce process monitoring aggressiveness."""
        try:
            db = Database()

            # Find Starter device for everest host
            device_list = db.get_device_exported_for_class("DServer")
            starter_devices = [
                dev for dev in device_list if "Starter" in dev and "everest" in dev
            ]

            if not starter_devices:
                print("No Starter device found for everest host")
                # Fall back to any Starter device
                starter_devices = [dev for dev in device_list if "Starter" in dev]
                if not starter_devices:
                    print("No Starter devices found at all")
                    return False

            starter_device = starter_devices[0]  # Use first one found
            print(f"Modifying configuration for: {starter_device}")

            # Properties to modify to reduce memory access issues
            new_properties = {
                "UseEvents": ["False"],  # Disable events to reduce process monitoring
                "AutoRestartDuration": ["0"],  # Disable auto-restart monitoring
                "serverStartupTimeout": [
                    "5"
                ],  # Increase timeout to reduce frequent checks
                "interStartupLevelWait": [
                    "2"
                ],  # Increase wait time between level checks
            }

            for prop_name, prop_value in new_properties.items():
                try:
                    db.put_device_property(starter_device, {prop_name: prop_value})
                    print(f"Set {prop_name} = {prop_value[0]}")
                except Exception as e:
                    print(f"Failed to set {prop_name}: {e}")

            print(
                "\nConfiguration updated. You need to restart the Starter for changes to take effect."
            )
            print(
                "To restart: Stop Starter.exe and start it again with your startup script."
            )

            return True

        except Exception as e:
            print(f"Error modifying configuration: {e}")
            return False

    if __name__ == "__main__":
        print("TANGO Starter Configuration Checker")
        print("=" * 40)

        if not check_starter_config():
            print("Could not check configuration")
            sys.exit(1)

        print("\n" + "=" * 40)
        choice = input(
            "Do you want to modify the configuration to reduce process monitoring? (y/n): "
        )

        if choice.lower() == "y":
            if modify_starter_config():
                print("\nConfiguration modification completed!")
            else:
                print("\nConfiguration modification failed!")
        else:
            print("No changes made.")

except ImportError as e:
    print(f"TANGO import failed: {e}")
    print("Make sure TANGO Python bindings are installed and accessible.")
    sys.exit(1)
