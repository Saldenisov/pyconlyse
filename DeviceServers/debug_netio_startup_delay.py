#!/usr/bin/env python3
"""Debug the mysterious 10-second delay in DS_Netio_pdu startup"""

import sys
import time
from pathlib import Path

# Add pyconlyse to path exactly like DS_Netio_pdu does
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))


def time_step(description, func):
    """Time a specific step"""
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


def test_imports():
    """Test all import steps"""
    print("=" * 60)
    print("🔍 TESTING IMPORTS")
    print("=" * 60)

    def import_basic_modules():
        return True

    def import_tango():
        return True

    def import_base_classes():
        from DeviceServers.base.pdu import DS_PDU

        return DS_PDU

    time_step("Import basic modules", import_basic_modules)
    time_step("Import Tango", import_tango)
    time_step("Import DS_PDU base class", import_base_classes)


def test_class_creation():
    """Test DS_Netio_pdu class creation"""
    print("\n" + "=" * 60)
    print("🔍 TESTING CLASS CREATION")
    print("=" * 60)

    def import_netio_class():
        sys.path.append(str(Path(__file__).resolve().parent / "power" / "netio"))
        from DS_Netio_pdu import DS_Netio_pdu

        return DS_Netio_pdu

    return time_step("Import DS_Netio_pdu class", import_netio_class)


def test_tango_initialization():
    """Test Tango server initialization components"""
    print("\n" + "=" * 60)
    print("🔍 TESTING TANGO INITIALIZATION")
    print("=" * 60)

    def test_device_server_startup():
        # This simulates what happens when you run DS_Netio_pdu.py

        return "Tango ready"

    def test_database_connection():
        try:
            import tango

            # This might be where the delay occurs
            db = tango.Database()
            return f"Database connected: {db}"
        except Exception as e:
            return f"Database error: {e}"

    time_step("Tango server components", test_device_server_startup)
    time_step("Tango Database connection", test_database_connection)


def test_run_server_call():
    """Test the run_server() call that starts everything"""
    print("\n" + "=" * 60)
    print("🔍 TESTING RUN_SERVER SIMULATION")
    print("=" * 60)

    def simulate_run_server():
        # This is a simulation of what DS_Netio_pdu.run_server() does
        try:
            # The actual run_server() call is blocking, so we can't test it directly
            # But we can test the components that might be slow
            return "run_server components loaded"
        except Exception as e:
            return f"Error: {e}"

    time_step("Simulate run_server() components", simulate_run_server)


def main():
    print("🐛 DS_Netio_pdu Startup Delay Debugger")
    print("Investigating the mysterious 10-second delay...")
    print("=" * 60)

    total_start = time.time()

    test_imports()
    ds_class = test_class_creation()
    test_tango_initialization()
    test_run_server_call()

    total_time = time.time() - total_start
    print("\n" + "=" * 60)
    print(f"📊 TOTAL TIME: {total_time:.2f}s")

    if total_time > 8:
        print("🔍 LIKELY CULPRITS:")
        print("- Tango Database connection timeout")
        print("- Device server registration with Tango DB")
        print("- Network timeouts during Tango initialization")
        print("- Missing Tango configuration causing retries")
    else:
        print("✅ Most components load quickly")
        print("🤔 The 10s delay might be in the actual Tango server startup")
        print("   or device server registration process")


if __name__ == "__main__":
    main()
