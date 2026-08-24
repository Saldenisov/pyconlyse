#!/usr/bin/env python3
"""Patient test script that waits for NETIO device to become available."""

import sys
import time
from pathlib import Path

# Add project to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))


def test_netio_with_patience(device_name, max_attempts=10):
    """Test NETIO device with patience for startup delays."""
    print(f"Testing NETIO device: {device_name}")
    print("=" * 60)
    print("Being patient - device server may need time to fully initialize...")
    print()

    try:
        from tango import DeviceProxy
        from taurus import Device
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

    for attempt in range(1, max_attempts + 1):
        print(f"Attempt {attempt}/{max_attempts}:")

        # Try PyTango DeviceProxy first
        print("  📡 Testing PyTango connection...", end=" ")
        try:
            device = DeviceProxy(device_name)
            device.set_timeout_millis(3000)  # 3 second timeout
            device.ping()
            print("✅ SUCCESS")

            # If ping works, try reading state and status
            print("  🔍 Reading state...", end=" ")
            try:
                state = device.state()
                print(f"✅ {state}")
            except Exception as e:
                print(f"❌ {e}")

            print("  📋 Reading status...", end=" ")
            try:
                status = device.status()
                print(
                    f"✅ {status[:100]}..."
                    if len(str(status)) > 100
                    else f"✅ {status}"
                )
            except Exception as e:
                print(f"❌ {e}")

            # Try NETIO-specific attributes
            print("  🔌 NETIO attributes:")
            for attr in ["states", "names", "ids"]:
                try:
                    value = device.read_attribute(attr).value
                    print(f"    {attr}: {value}")
                except Exception as e:
                    print(f"    {attr}: ❌ {e}")

            print(f"\n🎉 SUCCESS! Device {device_name} is fully operational!")
            return True

        except Exception as e:
            if "CantConnectToDevice" in str(e):
                print("❌ Not ready yet")
            else:
                print(f"❌ {e}")

        # Try Taurus as fallback
        print("  🌟 Testing Taurus connection...", end=" ")
        try:
            taurus_dev = Device(device_name)
            state = taurus_dev.state if hasattr(taurus_dev, "state") else None
            if callable(state):
                state = state()
            print(f"✅ State: {state}")
        except Exception as e:
            print(f"❌ {e}")

        if attempt < max_attempts:
            print("  ⏳ Waiting 3 seconds before retry...\n")
            time.sleep(3)
        else:
            print(f"\n⏰ Timeout after {max_attempts} attempts")
            print(
                "The device server may need more time to initialize or there may be a configuration issue."
            )
            return False

    return False


def main():
    """Main function."""
    import os

    print(f"TANGO_HOST: {os.environ.get('TANGO_HOST', 'not set')}")
    print()

    device_name = "manip/V0/PDU_VO"
    if len(sys.argv) > 1:
        device_name = sys.argv[1]

    success = test_netio_with_patience(device_name)

    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed - device not responding yet")
        print("This might be normal if the device server just started.")


if __name__ == "__main__":
    main()
