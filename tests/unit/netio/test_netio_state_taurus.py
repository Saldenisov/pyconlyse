#!/usr/bin/env python3
"""Simple script to connect to any NETIO Device Server using Taurus and print its state.

Usage (PowerShell):
  poetry run python test_netio_state_taurus.py manip/V0/PDU_VO

Notes:
- This uses Taurus (from taurus import Device) instead of PyTango DeviceProxy.
- Ensure TANGO_HOST is set to your DB host (e.g., everest:10000).
"""

import sys
from pathlib import Path

# Ensure project root is on path if needed
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def print_netio_state_taurus(device_name: str) -> bool:
    print(f"Connecting via Taurus to: {device_name}")
    print("=" * 60)
    try:
        # Taurus Device abstraction
        from taurus import Device
    except Exception as e:
        print(f"❌ Failed to import Taurus: {e}")
        print("Install taurus in your environment (e.g., pip install taurus)")
        return False

    try:
        dev = Device(device_name)
        print("✅ Device object created successfully")

        # Try reading state via attribute API first
        state_val = None
        try:
            # Some Taurus backends expose both .state and .State()
            state_val = getattr(dev, "state", None)
            # If state is a callable (proxy to Tango), call it
            if callable(state_val):
                state_val = state_val()
        except Exception as e:
            print(f"⚠️  Direct state access failed: {e}")
            state_val = None

        if state_val is None:
            try:
                state_val = dev.State()  # fallback
            except Exception as e:
                print(f"⚠️  State() method failed: {e}")
                # For non-running servers, Taurus often returns a default state
                state_val = "Unknown (Server may not be running)"

        # Pretty print state
        try:
            # If it's an enum value, show name
            if hasattr(state_val, "name"):
                pretty = state_val.name
            else:
                pretty = str(state_val)
        except Exception:
            pretty = str(state_val)

        print(f"✅ Device state: {pretty}")

        # Explain what this means
        if "Undefined" in str(state_val) or "Unknown" in str(state_val):
            print(
                "💡 Note: 'Undefined/Unknown' typically means the device server process is not running"
            )
            print("   but the device is registered in the Tango database.")

        # Optional: show status if available (but expect it to fail)
        try:
            status = (
                dev.Status() if hasattr(dev, "Status") else getattr(dev, "status", None)
            )
            if callable(status):
                status = status()
            if status is not None:
                print("\n📋 Status:")
                print(status)
        except Exception as e:
            print(f"\n⚠️  Status not available: {e}")

        # Optional: NETIO-related attributes (expect these to fail for non-running servers)
        print("\n🔌 NETIO-related attributes (best-effort):")
        for attr in ("states", "names", "ids"):
            try:
                val = getattr(dev, attr)
                if callable(val):  # some are exposed as callables
                    val = val()
                print(f"  {attr}: {val}")
            except Exception as e:
                print(f"  {attr}: not available (server not running: {e})")

        return True

    except Exception as e:
        print(f"❌ Connection/reading failed: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run python test_netio_state_taurus.py <device_name>")
        print("Example: poetry run python test_netio_state_taurus.py manip/V0/PDU_VO")
        sys.exit(1)

    device_name = sys.argv[1]
    ok = print_netio_state_taurus(device_name)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
