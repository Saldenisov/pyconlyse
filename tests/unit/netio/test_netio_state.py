#!/usr/bin/env python3
"""Simple script to connect to any NETIO Device Server and print its state attribute value."""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent.parent.parent  # Go up from tests/unit/netio/ to project root
sys.path.insert(0, str(project_root))


def test_netio_connection(device_name):
    """Connect to NETIO device and print its state."""
    print(f"Connecting to NETIO device: {device_name}")
    print("=" * 50)

    try:
        # Import Tango
        from tango import DeviceProxy

        # Create device proxy
        device = DeviceProxy(device_name)

        # Test basic connection
        print("📡 Testing connection...")
        try:
            device.ping()
            print("✅ Device ping successful")
        except Exception as e:
            print(f"⚠️  Device ping failed: {e}")
            print("Continuing anyway...")

        # Get device state
        print("\n🔍 Reading state attribute...")
        try:
            state = device.state()
            print(f"✅ Device state: {state}")
        except Exception as e:
            print(f"❌ Failed to read state: {e}")
            return False

        # Try to get additional info
        print("\n📊 Additional device information:")
        try:
            status = device.status()
            print(f"Status: {status}")
        except Exception as e:
            print(f"Status not available: {e}")

        # Try to read NETIO-specific attributes
        print("\n🔌 NETIO-specific attributes:")
        netio_attrs = ["states", "names", "ids"]
        for attr in netio_attrs:
            try:
                value = device.read_attribute(attr).value
                print(f"  {attr}: {value}")
            except Exception as e:
                print(f"  {attr}: Not available ({e})")

        return True

    except ImportError as e:
        print(f"❌ Failed to import Tango: {e}")
        print("Make sure PyTango is installed in your environment")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def main():
    """Main function."""
    # Default NETIO devices to try (based on the layouts we created)
    default_devices = [
        "manip/V0/PDU_VO",
        "manip/SD1/PDU_SD1",
        "manip/SD2/PDU_SD2",
        "manip/VD2/PDU_VD2",
        "manip/ELYSE/PDU_ELYSE",
    ]

    print("NETIO Device Server State Test")
    print("=" * 50)

    # Check if device name provided as argument
    if len(sys.argv) > 1:
        device_name = sys.argv[1]
        success = test_netio_connection(device_name)
        if success:
            print(f"\n✅ Successfully connected to {device_name}")
        else:
            print(f"\n❌ Failed to connect to {device_name}")
    else:
        print("No device specified. Testing default NETIO devices...\n")

        success_count = 0
        for device_name in default_devices:
            print(f"\n{'='*60}")
            success = test_netio_connection(device_name)
            if success:
                success_count += 1
            print()

        print(
            f"Summary: {success_count}/{len(default_devices)} devices connected successfully"
        )

        if success_count == 0:
            print("\n💡 Tips:")
            print("1. Make sure Tango Database is running")
            print("2. Check TANGO_HOST environment variable")
            print("3. Verify NETIO Device Servers are started")
            print("4. Test with: poetry run python test_netio_state.py <device_name>")


if __name__ == "__main__":
    main()
