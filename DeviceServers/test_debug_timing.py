#!/usr/bin/env python3
"""Test script to demonstrate the new debug timing features"""

import sys
from pathlib import Path

# Add pyconlyse to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from DeviceServers.power.netio.DS_Netio_pdu import DS_Netio_pdu


def test_debug_commands():
    """Test the global debug timing commands"""
    print("🔧 Testing Debug Timing Commands")
    print("=" * 50)

    # Create a test DS instance
    try:
        # Mock minimal DS setup for testing commands only
        class MockDS(DS_Netio_pdu):
            def __init__(self):
                # Skip full init, just set up enough for commands
                self.device_id = "test"
                self.friendly_name = "Test Device"
                self.always_on = 0
                self.debug_init_timing = 0
                self.archive_enabled = 0

        test_ds = MockDS()

        print("✅ 1. List current global variables:")
        result = test_ds.list_global_variables()
        print(f"   {result}")

        print("\n✅ 2. Enable debug timing globally:")
        result = test_ds.set_global_variable(["DEBUG_INIT_TIMING", "true"])
        print(f"   {result}")

        print("\n✅ 3. Set debug threshold to 5ms:")
        result = test_ds.set_global_variable(["DEBUG_TIMING_THRESHOLD_MS", "5"])
        print(f"   {result}")

        print("\n✅ 4. Check updated settings:")
        result = test_ds.list_global_variables()
        print(f"   {result}")

        print("\n✅ 5. Get config file path:")
        result = test_ds.get_global_config_path()
        print(f"   Config file: {result}")

        print("\n✅ 6. Save settings to file:")
        result = test_ds.save_global_variables()
        print(f"   {result}")

        print("\n🎉 All debug timing commands work!")
        print("\n📋 Next Steps:")
        print("   1. Stop any running DS using the Control window (type STOP)")
        print("   2. Start DS_Netio_pdu again")
        print("   3. Watch for '=== INIT TIMING (ms) ===' in the DS window")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_debug_commands()
