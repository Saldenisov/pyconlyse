#!/usr/bin/env python3
"""Check the actual server registration status in database."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_server_registration():
    """Check detailed server registration in database."""
    try:
        from tango import Database

        db = Database()
        print("📊 Detailed NETIO Server Registration Check")
        print("=" * 60)

        # Check all NETIO-related registrations
        print("🔍 Searching for all NETIO-related entries...")

        # Get all devices
        all_devices = db.get_device_exported("*")
        netio_devices = [
            d for d in all_devices if "netio" in d.lower() or "pdu" in d.lower()
        ]

        print(f"\n📡 Found {len(netio_devices)} NETIO-related devices:")
        for device in sorted(netio_devices):
            print(f"  {device}")

        # Check server status
        print("\n🔍 Checking server instances:")
        servers = db.get_server_list()
        netio_servers = [s for s in servers if "netio" in s.lower()]

        for server in sorted(netio_servers):
            print(f"\n📋 Server: {server}")

            # Check if it's running
            try:
                exported = db.get_device_exported(f"dserver/{server}")
                if exported:
                    print(f"  ✅ Exported: {exported}")

                    # Get server info
                    try:
                        info = db.get_server_info(server)
                        print(f"  📊 Info: {info}")
                    except Exception as e:
                        print(f"  ⚠️  Info: {e}")

                    # Check what devices this server should host
                    try:
                        devices = db.get_device_name(server, "*")
                        print(f"  🔌 Should host devices: {devices}")
                    except Exception as e:
                        print(f"  ⚠️  Device list: {e}")

                else:
                    print("  ❌ Not exported")

            except Exception as e:
                print(f"  ❌ Check failed: {e}")

        # Specific check for our problem device
        problem_device = "manip/V0/PDU_VO"
        print(f"\n🎯 Specific check for {problem_device}:")

        try:
            # Check device properties
            props = db.get_device_property(problem_device, "*")
            print(f"  📝 Properties: {len(props)} found")

            # Check device class
            dev_class = db.get_device_class_name(problem_device)
            print(f"  🏷️  Device class: {dev_class}")

            # Check which server should host it
            server_name = db.get_device_server(problem_device)
            print(f"  🖥️  Should be hosted by server: {server_name}")

            # Check if that server is running
            server_exported = db.get_device_exported(f"dserver/{server_name}")
            print(f"  📡 Server exported: {'✅' if server_exported else '❌'}")

        except Exception as e:
            print(f"  ❌ Device check failed: {e}")

        return True

    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False


def main():
    """Main function."""
    import os

    print(f"TANGO_HOST: {os.environ.get('TANGO_HOST', 'not set')}\n")

    check_server_registration()


if __name__ == "__main__":
    main()
