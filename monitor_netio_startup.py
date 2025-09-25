#!/usr/bin/env python3
"""Simple script to monitor NETIO device server startup status."""

import sys
import time
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_netio_status():
    """Quick check of NETIO device server status."""
    try:
        from tango import DeviceProxy

        # Quick test - just try one device with short timeout
        device_name = "manip/V0/PDU_VO"
        print(f"Testing {device_name}...", end=" ")

        try:
            device = DeviceProxy(device_name)
            device.set_timeout_millis(1000)  # 1 second timeout
            device.ping()
            print("✅ RUNNING")
            return True
        except Exception as e:
            if "CantConnectToDevice" in str(e):
                print("❌ NOT RUNNING")
            else:
                print(f"⚠️  {e}")
            return False

    except ImportError:
        print("❌ Tango not available")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Monitor device server startup."""
    print("NETIO Device Server Startup Monitor")
    print("=" * 40)
    print("Checking every 5 seconds... Press Ctrl+C to stop")
    print()

    attempt = 1
    while True:
        print(f"Attempt {attempt}: ", end="")
        running = check_netio_status()

        if running:
            print("\n🎉 NETIO device server is now responding!")
            print("You can now test with:")
            print("  poetry run python test_netio_state_taurus.py manip/V0/PDU_VO")
            break

        try:
            time.sleep(5)
            attempt += 1
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            break


if __name__ == "__main__":
    main()
