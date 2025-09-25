#!/usr/bin/env python3
"""Script to list available devices in the Tango database."""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def list_tango_devices():
    """List all devices in the Tango database."""
    try:
        from tango import Database

        print("Connecting to Tango Database...")
        db = Database()

        print("✅ Connected to Tango Database successfully!")
        print(f"Database info: {db.get_info()}")

        # Get all servers
        print("\n📋 Available Device Servers:")
        servers = db.get_server_list()
        print(f"Total servers: {len(servers)}")
        for i, server in enumerate(servers[:20]):  # Limit to first 20
            print(f"  {i+1}. {server}")
        if len(servers) > 20:
            print(f"  ... and {len(servers) - 20} more")

        # Get devices with specific patterns
        patterns = ["*NETIO*", "*PDU*", "*manip*", "*ELYSE*"]

        for pattern in patterns:
            print(f"\n🔍 Devices matching '{pattern}':")
            try:
                devices = db.get_device_exported(pattern)
                if devices:
                    for device in devices:
                        print(f"  📡 {device}")
                else:
                    print("  (none found)")
            except Exception as e:
                print(f"  ❌ Error searching: {e}")

        # Get all exported devices (may be many)
        print("\n📊 All exported devices:")
        try:
            all_devices = db.get_device_exported("*")
            print(f"Total exported devices: {len(all_devices)}")

            # Filter for likely NETIO devices
            netio_devices = [
                d for d in all_devices if "pdu" in d.lower() or "netio" in d.lower()
            ]
            if netio_devices:
                print("🔌 Likely NETIO/PDU devices:")
                for device in netio_devices:
                    print(f"  📡 {device}")
            else:
                print("🔍 No obvious NETIO/PDU devices found")

            # Show first few devices as examples
            print("\n📝 First 10 exported devices (examples):")
            for device in all_devices[:10]:
                print(f"  📡 {device}")

        except Exception as e:
            print(f"❌ Error getting all devices: {e}")

        return True

    except ImportError as e:
        print(f"❌ Failed to import Tango: {e}")
        return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def main():
    """Main function."""
    print("Tango Database Device Lister")
    print("=" * 50)

    # Check TANGO_HOST
    import os

    tango_host = os.environ.get("TANGO_HOST", "not set")
    print(f"TANGO_HOST: {tango_host}")
    print()

    success = list_tango_devices()

    if success:
        print("\n✅ Database query successful!")
    else:
        print("\n❌ Database query failed!")


if __name__ == "__main__":
    main()
