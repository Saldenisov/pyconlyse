#!/usr/bin/env python3
"""Debug script for DS_Basler_camera issues
This script helps diagnose why the camera device server is not responding
"""

import sys
from pathlib import Path

# Add project root to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(app_folder))


def test_imports():
    """Test if all required imports are available"""
    print("=== Testing Imports ===")

    try:
        import cv2

        print("✓ opencv-python (cv2) available")
    except ImportError as e:
        print(f"❌ opencv-python (cv2) not available: {e}")
        return False

    try:
        from pypylon import genicam, pylon

        print("✓ pypylon available")
    except ImportError as e:
        print(f"❌ pypylon not available: {e}")
        print("   Install with: pip install pypylon")
        return False

    try:
        import numpy as np

        print("✓ numpy available")
    except ImportError as e:
        print(f"❌ numpy not available: {e}")
        return False

    try:
        from DeviceServers.base.camera import DS_CAMERA_CCD

        print("✓ DS_CAMERA_CCD base class available")
    except ImportError as e:
        print(f"❌ DS_CAMERA_CCD not available: {e}")
        return False

    return True


def test_camera_hardware():
    """Test if Basler camera hardware is available"""
    print("\n=== Testing Camera Hardware ===")

    try:
        from pypylon import pylon

        # Get the transport layer factory
        tlFactory = pylon.TlFactory.GetInstance()

        # Get all available devices
        devices = tlFactory.EnumerateDevices()

        if len(devices) == 0:
            print("❌ No Basler cameras found")
            print("   Make sure:")
            print("   1. Camera is connected (USB/GigE)")
            print("   2. Camera drivers are installed")
            print("   3. Camera is powered on")
            return False

        print(f"✓ Found {len(devices)} Basler camera(s):")
        for i, device in enumerate(devices):
            print(f"   {i + 1}. Serial: {device.GetSerialNumber()}")
            print(f"      Model:  {device.GetModelName()}")
            print(f"      Interface: {device.GetInterfaceID()}")

        # Test opening first camera
        try:
            camera = pylon.InstantCamera(tlFactory.CreateDevice(devices[0]))
            camera.Open()
            print(
                f"✓ Successfully opened camera: {camera.GetDeviceInfo().GetModelName()}"
            )
            camera.Close()
            print("✓ Successfully closed camera")
        except Exception as e:
            print(f"❌ Error opening/closing camera: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ Error testing camera hardware: {e}")
        return False


def test_device_server_import():
    """Test if DS_Basler_camera can be imported and instantiated"""
    print("\n=== Testing Device Server Import ===")

    try:
        from DeviceServers.cameras.basler.DS_Basler_camera import DS_Basler_camera

        print("✓ DS_Basler_camera imported successfully")

        # Test basic class structure
        print(
            f"✓ Class methods available: {len([m for m in dir(DS_Basler_camera) if not m.startswith('_')])}"
        )

        # Check critical methods
        critical_methods = [
            "init_device",
            "find_device",
            "turn_on_local",
            "turn_off_local",
        ]
        missing_methods = []
        for method in critical_methods:
            if not hasattr(DS_Basler_camera, method):
                missing_methods.append(method)

        if missing_methods:
            print(f"❌ Missing critical methods: {missing_methods}")
            return False
        print("✓ All critical methods present")

        return True

    except ImportError as e:
        print(f"❌ Failed to import DS_Basler_camera: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing DS_Basler_camera: {e}")
        return False


def test_tango_environment():
    """Test Tango environment setup"""
    print("\n=== Testing Tango Environment ===")

    try:
        import tango

        print("✓ Tango imported successfully")
        print(f"✓ Tango version: {tango.__version__}")

        # Test database connection
        try:
            db = tango.Database()
            print("✓ Tango database connection successful")
        except Exception as e:
            print(f"❌ Tango database connection failed: {e}")
            print("   Make sure Tango database is running")
            return False

        return True

    except ImportError as e:
        print(f"❌ Tango not available: {e}")
        return False


def main():
    """Main diagnostic function"""
    print("DS_Basler_camera Diagnostic Script")
    print("=" * 50)

    # Run tests
    tests = [
        ("Imports", test_imports),
        ("Camera Hardware", test_camera_hardware),
        ("Device Server Import", test_device_server_import),
        ("Tango Environment", test_tango_environment),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False

    # Summary
    print(f"\n{'=' * 50}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'=' * 50}")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! The issue might be:")
        print("   1. Camera hardware not connected properly")
        print("   2. Device server configuration issue")
        print("   3. Instance name or properties problem")
        print("   4. Threading issue during startup")
        print("\nSuggestions:")
        print("   - Check camera instance configuration in Astor")
        print("   - Verify camera serial number matches device properties")
        print("   - Test with manual device server start")
    else:
        failed_tests = [name for name, result in results.items() if not result]
        print(f"\n❌ Failed tests: {', '.join(failed_tests)}")
        print("   Fix these issues before the device server can work properly")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
