#!/usr/bin/env python3
"""Diagnostic script to check Tango device server status and connectivity."""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def diagnose_device_connectivity():
    """Diagnose device server connectivity issues."""
    try:
        import time

        from tango import Database, DeviceProxy

        print("Tango Device Connectivity Diagnostics")
        print("=" * 60)

        # Connect to database
        print("📊 Database Connection Test:")
        try:
            db = Database()
            print(f"✅ Connected to Tango Database: {db.get_info()}")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return

        # Check device server status
        print("\n🔍 Device Server Status Check:")
        netio_servers = [
            "DS_Netio_pdu/1_V0",
            "DS_Netio_pdu/2_VD2",
            "DS_Netio_pdu/3_SD1",
            "DS_Netio_pdu/4_SD2",
            "DS_Netio_pdu/5_ELYSE",
        ]

        for server in netio_servers:
            try:
                # Check if server is registered and exported
                exported = db.get_device_exported(f"dserver/{server}")
                if exported:
                    print(f"✅ {server}: Registered and exported")

                    # Try to ping the server admin device
                    try:
                        admin_device = DeviceProxy(f"dserver/{server}")
                        admin_device.set_timeout_millis(3000)  # 3 second timeout
                        admin_device.ping()
                        print("   📡 Admin device ping: SUCCESS")

                        # Check server state
                        try:
                            state = admin_device.state()
                            print(f"   🔋 Server state: {state}")
                        except Exception as e:
                            print(f"   ⚠️  Server state: {e}")

                    except Exception as e:
                        print(f"   ❌ Admin device ping: {e}")

                else:
                    print(f"❌ {server}: Not exported")

            except Exception as e:
                print(f"❌ {server}: Check failed - {e}")

        # Test actual NETIO devices
        print("\n🔌 NETIO Device Connection Test:")
        netio_devices = [
            "manip/V0/PDU_VO",
            "manip/SD1/PDU_SD1",
            "manip/SD2/PDU_SD2",
            "manip/VD2/PDU_VD2",
            "manip/ELYSE/PDU_ELYSE",
        ]

        for device_name in netio_devices:
            print(f"\n📡 Testing {device_name}:")
            try:
                # Check if device is exported
                exported = db.get_device_exported(device_name)
                if not exported:
                    print("   ❌ Device not exported in database")
                    continue
                else:
                    print("   ✅ Device exported in database")

                # Try direct connection with short timeout
                device = DeviceProxy(device_name)
                device.set_timeout_millis(2000)  # 2 second timeout

                # Test ping
                try:
                    device.ping()
                    print("   ✅ Ping: SUCCESS")
                except Exception as e:
                    print(f"   ❌ Ping: {e}")
                    continue

                # Test state read
                try:
                    state = device.state()
                    print(f"   ✅ State: {state}")
                except Exception as e:
                    print(f"   ❌ State: {e}")

                # Test status read
                try:
                    status = device.status()
                    print(
                        f"   ✅ Status: {status[:100]}..."
                        if len(str(status)) > 100
                        else f"   ✅ Status: {status}"
                    )
                except Exception as e:
                    print(f"   ❌ Status: {e}")

            except Exception as e:
                print(f"   ❌ Device creation failed: {e}")

        # Check Taurus approach
        print("\n🌟 Taurus Device Test:")
        try:
            from taurus import Device

            for device_name in netio_devices[:2]:  # Test first 2 devices
                print(f"\n🔍 Taurus test for {device_name}:")
                try:
                    taurus_dev = Device(device_name)

                    # Try to read state
                    try:
                        state = (
                            taurus_dev.state if hasattr(taurus_dev, "state") else None
                        )
                        if callable(state):
                            state = state()
                        print(f"   ✅ Taurus state: {state}")
                    except Exception as e:
                        print(f"   ❌ Taurus state: {e}")

                except Exception as e:
                    print(f"   ❌ Taurus device creation: {e}")

        except ImportError:
            print("   ❌ Taurus not available")

        return True

    except ImportError as e:
        print(f"❌ Failed to import Tango: {e}")
        return False
    except Exception as e:
        print(f"❌ Diagnosis failed: {e}")
        return False


def main():
    """Main function."""
    import os

    print(f"TANGO_HOST: {os.environ.get('TANGO_HOST', 'not set')}")
    print()

    diagnose_device_connectivity()


if __name__ == "__main__":
    main()
