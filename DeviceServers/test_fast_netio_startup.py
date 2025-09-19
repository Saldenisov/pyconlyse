#!/usr/bin/env python3
"""Test the improved Netio startup time after timeout fix"""

import sys
import time
from pathlib import Path

# Add pyconlyse to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))


def test_fast_archive_connection():
    """Test the new timeout-based archive connection"""
    print("🚀 Testing Fast Archive Connection")
    print("=" * 40)

    start_time = time.time()

    # Import the modified DS_General class
    from DeviceServers.base.general import DS_General

    # Create a test class that inherits from DS_General
    class TestDS(DS_General):
        _version_ = "test"
        _model_ = "test"

        def init_device(self):
            # Initialize basic attributes before calling super()
            self.device_id = "test"
            self.friendly_name = "Test Device"
            self.always_on = 0
            self.archive = "manip/general/archive"  # This will timeout

            # Initialize orders and archive state before super() call
            self.orders = {}
            self.previous_archive_state = {}
            self.archive_state = {}
            self.locking_client_token = ""
            self.locked_client = False
            self._comment = "..."
            self._error = "..."
            self._n = 0
            self._status_check_fault = 0
            self.prev_state = None
            self._device_id_internal = -1
            self._uri = b""

            # Test just the archive connection part
            self._init_archive_connection(timeout_seconds=3)  # 3 second timeout

        def find_device(self):
            self._device_id_internal = 1
            self._uri = "test_uri"

        def register_variables_for_archive(self):
            pass

        def get_controller_status_local(self):
            return 0

        def turn_on_local(self):
            return 0

        def turn_off_local(self):
            return 0

    try:
        # Test creating the device server
        test_ds = TestDS()
        test_ds.init_device()

        elapsed = time.time() - start_time
        print(f"✓ Device initialization completed in {elapsed:.2f}s")
        print(f"✓ Archive state: {type(test_ds.archive).__name__}")

        if elapsed < 10:
            print("🎉 SUCCESS: Fast startup achieved!")
        else:
            print("⚠️  Still slow, but better than 17+ seconds")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ Error after {elapsed:.2f}s: {e}")


def main():
    print("🔧 Testing Fast Netio Startup")
    print("=" * 50)
    test_fast_archive_connection()


if __name__ == "__main__":
    main()
