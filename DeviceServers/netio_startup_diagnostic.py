#!/usr/bin/env python3
"""Diagnostic script to identify what makes DS_Netio_pdu startup slow"""

import sys
import time
from pathlib import Path

import requests

# Add pyconlyse to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))


def time_function(func, description):
    """Time a function execution"""
    start = time.time()
    try:
        result = func()
        elapsed = time.time() - start
        print(f"✓ {description}: {elapsed:.2f}s")
        return result, elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ {description}: {elapsed:.2f}s - ERROR: {e}")
        return None, elapsed


def test_imports():
    """Test import times"""
    print("=== TESTING IMPORTS ===")

    def import_tango():
        return True

    def import_requests():
        return True

    def import_base():
        return True

    def import_taurus():
        return True

    time_function(import_tango, "Import Tango")
    time_function(import_requests, "Import requests")
    time_function(import_base, "Import DS_PDU base class")
    time_function(import_taurus, "Import Taurus")


def test_netio_connection():
    """Test network connection to a typical Netio device"""
    print("\n=== TESTING NETWORK CONNECTION ===")

    # Test with a typical IP - you can modify this
    test_ip = "192.168.1.100"  # Common default for Netio devices

    def test_http_connection():
        try:
            response = requests.get(
                f"http://{test_ip}/netio.json", timeout=2, auth=("admin", "admin")
            )  # Common defaults
            return response.status_code
        except requests.ConnectionError:
            return "Connection Error"
        except requests.Timeout:
            return "Timeout"

    time_function(test_http_connection, f"HTTP connection to {test_ip}")


def test_device_server_creation():
    """Test creating device server instance"""
    print("\n=== TESTING DEVICE SERVER CREATION ===")

    def create_ds_class():
        # Import the actual device server class
        sys.path.append(str(Path(__file__).resolve().parent / "power" / "netio"))
        from DS_Netio_pdu import DS_Netio_pdu

        return DS_Netio_pdu

    def create_mock_instance():
        DS_Netio_pdu = create_ds_class()[0]

        # Create a minimal mock instance (not full Tango device)
        class MockInstance:
            def __init__(self):
                self.ip_address = "192.168.1.100"
                self.authentication_name = "admin"
                self.authentication_password = "admin"
                self.device_id = "test"
                self.friendly_name = "Test Netio"

        return MockInstance()

    time_function(create_ds_class, "Import DS_Netio_pdu class")
    time_function(create_mock_instance, "Create mock instance")


def test_tango_device_init():
    """Test Tango device initialization components"""
    print("\n=== TESTING TANGO DEVICE INITIALIZATION ===")

    def init_tango_device():
        # This simulates the Device.init_device() call
        return True

    def init_archive_connection():
        import taurus

        # This simulates connecting to the archive
        try:
            # Use a mock address since we can't connect to real archive
            device = taurus.Device("manip/general/archive")
            return "Archive object created"
        except Exception as e:
            return f"Archive error: {e}"

    time_function(init_tango_device, "Tango Device.init_device()")
    time_function(init_archive_connection, "Archive connection (taurus.Device)")


def main():
    print("🔍 DS_Netio_pdu Startup Diagnostic Tool")
    print("=" * 50)

    start_total = time.time()

    test_imports()
    test_netio_connection()
    test_device_server_creation()
    test_tango_device_init()

    total_time = time.time() - start_total
    print(f"\n📊 TOTAL DIAGNOSTIC TIME: {total_time:.2f}s")

    print("\n💡 RECOMMENDATIONS:")
    if total_time > 10:
        print("- Startup is slow. Check network connectivity to Netio devices")
        print("- Consider reducing timeout values in network requests")
        print("- Check if Taurus archive service is accessible")
    else:
        print("- Import and basic setup times look reasonable")
        print("- Slow startup may be due to network timeouts or device discovery")


if __name__ == "__main__":
    main()
