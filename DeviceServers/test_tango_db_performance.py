#!/usr/bin/env python3
"""Test Tango Database connection performance to identify slow operations"""

import sys
import time
from pathlib import Path

# Add pyconlyse to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))


def time_operation(description, func):
    """Time a specific operation"""
    print(f"⏱️  {description}...")
    start = time.time()
    try:
        result = func()
        elapsed = time.time() - start
        print(f"✓ {description}: {elapsed:.2f}s")
        return result
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ {description}: {elapsed:.2f}s - ERROR: {e}")
        return None


def test_tango_db_operations():
    """Test various Tango Database operations"""
    print("🔍 TESTING TANGO DATABASE OPERATIONS")
    print("=" * 60)

    def import_tango():
        import tango

        return tango

    def create_database():
        import tango

        db = tango.Database()
        return db

    def query_device_servers():
        import tango

        db = tango.Database()
        servers = db.get_server_list()
        return f"Found {len(servers)} servers"

    def query_devices():
        import tango

        db = tango.Database()
        devices = db.get_device_list("*")
        return f"Found {len(devices)} devices"

    def test_device_registration():
        import tango

        db = tango.Database()
        # Test a typical device server registration query
        try:
            info = db.get_server_info("DataBaseds/2")
            return f"DB server info: {info}"
        except Exception as e:
            return f"No DataBaseds info: {e}"

    tango_mod = time_operation("Import tango", import_tango)
    if tango_mod:
        db = time_operation("Create Database object", create_database)
        if db:
            time_operation("Query server list", query_device_servers)
            time_operation("Query device list", query_devices)
            time_operation("Test device registration", test_device_registration)


def test_device_server_registration():
    """Test device server registration process (what takes time during startup)"""
    print("\n" + "=" * 60)
    print("🔍 TESTING DEVICE SERVER REGISTRATION")
    print("=" * 60)

    def test_server_registration():
        from tango.server import Device

        # This simulates what happens during DS startup
        class TestDevice(Device):
            pass

        return "Device class created"

    time_operation("Device server registration simulation", test_server_registration)


def check_tango_environment():
    """Check Tango environment variables and configuration"""
    print("\n" + "=" * 60)
    print("🔍 TANGO ENVIRONMENT CHECK")
    print("=" * 60)

    import os

    env_vars = [
        "TANGO_HOST",
        "TANGO_LOG_PATH",
        "TANGO_ROOT",
        "OMNI_ORB_CONFIG",
        "PYTHONPATH",
    ]

    for var in env_vars:
        value = os.environ.get(var, "NOT SET")
        print(f"📋 {var}: {value}")


def main():
    print("🐛 Tango Database Performance Tester")
    print(
        "TANGO_HOST:",
        sys.modules.get("os", __import__("os")).environ.get("TANGO_HOST", "NOT SET"),
    )
    print("=" * 60)

    total_start = time.time()

    check_tango_environment()
    test_tango_db_operations()
    test_device_server_registration()

    total_time = time.time() - total_start
    print("\n" + "=" * 60)
    print(f"📊 TOTAL TEST TIME: {total_time:.2f}s")

    if total_time > 8:
        print("\n🚨 SLOW TANGO CONFIGURATION DETECTED!")
        print("💡 RECOMMENDATIONS:")
        print("- Check if Tango Database server is running efficiently")
        print("- Consider using a local Tango DB for development")
        print("- Check network latency to 'everest:10000'")
        print("- Review Tango timeout configurations")
    else:
        print("\n✅ Tango DB operations are reasonably fast")
        print("🤔 The startup delay might be elsewhere")


if __name__ == "__main__":
    main()
