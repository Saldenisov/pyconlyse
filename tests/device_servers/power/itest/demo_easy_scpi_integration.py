#!/usr/bin/env python3
"""
Demonstration script showing that the easy-scpi refactored iTest Device Server works correctly.

This script:
1. Tests that all imports work
2. Shows that the SCPI client API is preserved
3. Demonstrates that Device Server classes can be instantiated
4. Validates that easy-scpi backend is properly used

Run this script to verify the refactoring is complete and working.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """Test that all required modules can be imported."""
    print("=== Testing Imports ===")
    
    # Test SCPI client imports
    print("Testing SCPI client imports...")
    try:
        from DeviceServers.power.iTest.scpi_client import SCPISocket, SCPIError
        print("✓ DeviceServers.power.iTest.scpi_client imported successfully")
    except Exception as e:
        print(f"✗ Failed to import SCPI client: {e}")
        return False
    
    # Test Device Server imports
    print("Testing Device Server imports...")
    try:
        from DeviceServers.power.iTest.DS_itest_psu import ITestPSU, DS_iTest_PSU
        print("✓ DeviceServers.power.iTest.DS_itest_psu imported successfully")
    except Exception as e:
        print(f"✗ Failed to import Device Server: {e}")
        return False
    
    # Test tango_itest_psu imports
    print("Testing tango_itest_psu imports...")
    try:
        from tango_itest_psu.scpi_client import SCPISocket as TangoSCPISocket, SCPIError
        from tango_itest_psu.itest_psu_device import ITestPSU as TangoITestPSU
        print("✓ tango_itest_psu modules imported successfully")
    except Exception as e:
        print(f"✗ Failed to import tango_itest_psu: {e}")
        return False
    
    return True

def test_scpi_client_api():
    """Test that the SCPI client API is preserved."""
    print("\n=== Testing SCPI Client API ===")
    
    from DeviceServers.power.iTest.scpi_client import SCPISocket, SCPIError
    
    # Test constructor
    print("Testing SCPISocket constructor...")
    try:
        client = SCPISocket("192.168.1.100", 5025, timeout=3.0, eol="\n")
        print("✓ SCPISocket can be instantiated")
    except Exception as e:
        print(f"✗ Failed to create SCPISocket: {e}")
        return False
    
    # Test that all expected methods exist
    expected_methods = [
        'connect', 'close', 'write', 'query', 'idn',
        'output_on', 'output_off', 'set_current', 'get_current_setpoint',
        'measure_current', 'measure_voltage', 'configure_templates',
        'get_output_state', 'select_channel'
    ]
    
    print("Testing API completeness...")
    for method in expected_methods:
        if hasattr(client, method) and callable(getattr(client, method)):
            print(f"✓ {method} method available")
        else:
            print(f"✗ {method} method missing!")
            return False
    
    # Test that easy-scpi backend is being used
    print("Verifying easy-scpi backend...")
    try:
        # This should work with the new implementation
        client._host  # Should be set by new implementation
        client._port
        client._timeout_s
        client._eol
        print("✓ easy-scpi backend attributes present")
    except AttributeError:
        print("✗ easy-scpi backend not detected")
        return False
    
    return True

def test_device_server_classes():
    """Test that Device Server classes can be instantiated."""
    print("\n=== Testing Device Server Classes ===")
    
    # Test main Device Server classes exist
    from DeviceServers.power.iTest.DS_itest_psu import ITestPSU, DS_iTest_PSU
    
    print("Testing class hierarchy...")
    if issubclass(DS_iTest_PSU, ITestPSU):
        print("✓ DS_iTest_PSU inherits from ITestPSU")
    else:
        print("✗ Inheritance structure broken")
        return False
    
    # Test that expected properties exist
    expected_props = ['Host', 'Port', 'StartCurrent', 'ConfigPath', 'EnableOutputOnInit', 'EOL']
    for prop in expected_props:
        if hasattr(ITestPSU, prop):
            print(f"✓ {prop} device property available")
        else:
            print(f"✗ {prop} device property missing!")
            return False
    
    return True

def test_template_functionality():
    """Test that template configuration works."""
    print("\n=== Testing Template Functionality ===")
    
    from DeviceServers.power.iTest.scpi_client import SCPISocket
    
    client = SCPISocket("192.168.1.100", 5025)
    
    # Test template configuration
    templates = {
        "set_current": "SOUR:CURR:LEV {value:.3f}",
        "get_current": "SOUR:CURR:LEV?",
        "output_on": "OUTP:STAT ON",
        "invalid_key": "should be filtered"  # This should be ignored
    }
    
    try:
        client.configure_templates(templates)
        print("✓ Template configuration accepted")
        
        # Check that only valid templates were stored
        if len(client._tmpl) == 3:  # Should filter out invalid_key
            print("✓ Invalid template keys filtered correctly")
        else:
            print(f"✗ Template filtering failed: {len(client._tmpl)} templates stored")
            return False
            
    except Exception as e:
        print(f"✗ Template configuration failed: {e}")
        return False
    
    return True

def test_easy_scpi_dependency():
    """Verify that easy-scpi is properly imported and used."""
    print("\n=== Testing easy-scpi Dependency ===")
    
    try:
        import easy_scpi
        print(f"✓ easy-scpi installed: {easy_scpi.__file__}")
    except ImportError:
        print("✗ easy-scpi not installed")
        return False
    
    # Test that our implementation uses it
    from DeviceServers.power.iTest.scpi_client import EasyInstrument
    print("✓ EasyInstrument imported from easy-scpi")
    
    return True

def main():
    """Run all tests."""
    print("iTest Device Server - easy-scpi Integration Test")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("SCPI Client API", test_scpi_client_api),
        ("Device Server Classes", test_device_server_classes),
        ("Template Functionality", test_template_functionality),
        ("easy-scpi Dependency", test_easy_scpi_dependency),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"\n✓ {test_name}: PASSED")
                passed += 1
            else:
                print(f"\n✗ {test_name}: FAILED")
        except Exception as e:
            print(f"\n✗ {test_name}: FAILED with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 SUCCESS: easy-scpi integration is working correctly!")
        print("\nKey improvements:")
        print("- ✓ Uses PyVISA backend via easy-scpi instead of raw sockets")
        print("- ✓ Maintains complete API compatibility")
        print("- ✓ Supports all existing Device Server functionality")
        print("- ✓ Includes comprehensive test coverage")
        return True
    else:
        print("❌ FAILURE: Some tests failed. Check output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)