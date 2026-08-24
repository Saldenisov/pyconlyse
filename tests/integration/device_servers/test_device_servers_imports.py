#!/usr/bin/env python3
"""Comprehensive test suite for DeviceServers module
Tests imports, basic functionality, and identifies any issues
"""

import importlib
import sys
import traceback
import unittest
from pathlib import Path

# Add project root to path
app_folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(app_folder))


class TestDeviceServersImports(unittest.TestCase):
    """Test suite for DeviceServers imports and basic functionality"""

    def setUp(self):
        """Set up test environment"""
        self.errors = []
        self.warnings = []
        self.successful_imports = []

    def test_base_imports(self):
        """Test base device server classes can be imported"""
        print("\n=== Testing Base Device Server Imports ===")

        base_modules = [
            "DeviceServers.base.general",
            "DeviceServers.base.camera",
            "DeviceServers.base.motor",
            "DeviceServers.base.pdu",
        ]

        for module_name in base_modules:
            try:
                module = importlib.import_module(module_name)
                self.successful_imports.append(module_name)
                print(f"✓ {module_name}")
            except Exception as e:
                error_msg = f"Failed to import {module_name}: {e!s}"
                self.errors.append(error_msg)
                print(f"✗ {error_msg}")

    def test_camera_imports(self):
        """Test camera device servers can be imported"""
        print("\n=== Testing Camera Device Server Imports ===")

        camera_modules = ["DeviceServers.cameras.basler.DS_Basler_camera"]

        for module_name in camera_modules:
            try:
                module = importlib.import_module(module_name)
                self.successful_imports.append(module_name)
                print(f"✓ {module_name}")

                # Check if main class exists
                if "DS_" in module_name and "Widget" not in module_name:
                    class_name = module_name.split(".")[-1]
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        print(f"  ✓ Found class: {class_name}")

                        # Check if it has required methods
                        required_methods = ["init_device", "find_device"]
                        for method in required_methods:
                            if hasattr(cls, method):
                                print(f"    ✓ Has method: {method}")
                            else:
                                self.warnings.append(
                                    f"{class_name} missing method: {method}"
                                )

            except Exception as e:
                error_msg = f"Failed to import {module_name}: {e!s}"
                self.errors.append(error_msg)
                print(f"✗ {error_msg}")
                print(f"  Error details: {traceback.format_exc()}")

    def test_power_imports(self):
        """Test power device servers can be imported"""
        print("\n=== Testing Power Device Server Imports ===")

        power_modules = ["DeviceServers.power.netio.DS_Netio_pdu"]

        for module_name in power_modules:
            try:
                module = importlib.import_module(module_name)
                self.successful_imports.append(module_name)
                print(f"✓ {module_name}")

                # Check if main class exists
                if "DS_" in module_name and "Widget" not in module_name:
                    class_name = module_name.split(".")[-1]
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        print(f"  ✓ Found class: {class_name}")

            except Exception as e:
                error_msg = f"Failed to import {module_name}: {e!s}"
                self.errors.append(error_msg)
                print(f"✗ {error_msg}")
                print(f"  Error details: {traceback.format_exc()}")

    def test_motion_imports(self):
        """Test motion device servers can be imported"""
        print("\n=== Testing Motion Device Server Imports ===")

        motion_modules = [
            "DeviceServers.motion.owis.DS_OWIS_PS90",
            "DeviceServers.motion.standa.DS_Standa_Motor",
            "DeviceServers.motion.topdirect.DS_TopDirect_Motor",
        ]

        for module_name in motion_modules:
            try:
                module = importlib.import_module(module_name)
                self.successful_imports.append(module_name)
                print(f"✓ {module_name}")

            except Exception as e:
                error_msg = f"Failed to import {module_name}: {e!s}"
                self.errors.append(error_msg)
                print(f"✗ {error_msg}")
                # Only show details for critical failures
                if "No module named" in str(e):
                    print(f"  Missing module: {e!s}")
                else:
                    print(f"  Error details: {e!s}")

    def test_testing_imports(self):
        """Test testing device servers can be imported"""
        print("\n=== Testing Test Device Server Imports ===")

        test_modules = [
            "DeviceServers.testing.DS_Test",
        ]

        for module_name in test_modules:
            try:
                module = importlib.import_module(module_name)
                self.successful_imports.append(module_name)
                print(f"✓ {module_name}")

                # Test instantiation (without running)
                if hasattr(module, "DS_Test"):
                    print("  ✓ DS_Test class available")

            except Exception as e:
                error_msg = f"Failed to import {module_name}: {e!s}"
                self.errors.append(error_msg)
                print(f"✗ {error_msg}")

    @unittest.skip("Qt/Taurus widgets require an isolated GUI/Tango process")
    def test_shared_imports(self):
        """GUI widgets are tested separately from headless device servers."""
        print("\n=== Testing Shared Utilities Imports ===")

        shared_modules = [
            "DeviceServers.shared.DS_Widget",
        ]

        for module_name in shared_modules:
            try:
                module = importlib.import_module(module_name)
                self.successful_imports.append(module_name)
                print(f"✓ {module_name}")

            except Exception as e:
                error_msg = f"Failed to import {module_name}: {e!s}"
                self.errors.append(error_msg)
                print(f"✗ {error_msg}")

    def test_deviceservers_init(self):
        """Test main DeviceServers __init__.py"""
        print("\n=== Testing DeviceServers Main Module ===")

        try:
            import DeviceServers

            self.successful_imports.append("DeviceServers")
            print("✓ DeviceServers main module")

            # Test get_class_match function
            if hasattr(DeviceServers, "get_class_match"):
                try:
                    class_match = DeviceServers.get_class_match()
                    print(f"✓ get_class_match() returned {len(class_match)} classes")

                    for cls_name, widget_cls in class_match.items():
                        print(f"  ✓ {cls_name} -> {widget_cls.__name__}")

                except Exception as e:
                    self.warnings.append(f"get_class_match() failed: {e!s}")
                    print(f"⚠ get_class_match() failed: {e!s}")
            else:
                self.warnings.append("get_class_match function not found")

        except Exception as e:
            error_msg = f"Failed to import DeviceServers: {e!s}"
            self.errors.append(error_msg)
            print(f"✗ {error_msg}")

    def test_executable_wrappers(self):
        """Test that our executable wrappers exist"""
        print("\n=== Testing Executable Wrappers ===")

        device_servers_dir = Path(__file__).parent

        executables = [
            "DS_Basler_camera.exe",
            "DS_Netio_pdu.exe",
            "DS_Basler_camera.bat",
            "DS_Netio_pdu.bat",
        ]

        for exe_name in executables:
            exe_path = device_servers_dir / exe_name
            if exe_path.exists():
                print(f"✓ {exe_name} exists ({exe_path.stat().st_size} bytes)")
            else:
                self.warnings.append(f"Executable wrapper missing: {exe_name}")
                print(f"⚠ {exe_name} missing")

    def tearDown(self):
        """Print summary of test results"""
        print(f"\n{'=' * 60}")
        print("TEST SUMMARY")
        print(f"{'=' * 60}")

        print(f"✓ Successful imports: {len(self.successful_imports)}")
        for module in self.successful_imports:
            print(f"  - {module}")

        if self.warnings:
            print(f"\n⚠ Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print(f"\n✗ Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n🎉 All critical imports successful!")

        # Fail test if there are critical errors
        if self.errors:
            self.fail(f"Found {len(self.errors)} import errors")


def run_import_test():
    """Quick standalone import test"""
    print("Running quick DeviceServers import test...")

    critical_imports = [
        "DeviceServers.cameras.basler.DS_Basler_camera",
        "DeviceServers.power.netio.DS_Netio_pdu",
        "DeviceServers.testing.DS_Test",
    ]

    success_count = 0
    for module_name in critical_imports:
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
            success_count += 1
        except Exception as e:
            print(f"✗ {module_name}: {e!s}")

    print(
        f"\nResult: {success_count}/{len(critical_imports)} critical imports successful"
    )
    return success_count == len(critical_imports)


if __name__ == "__main__":
    print("DeviceServers Import Test Suite")
    print("=" * 50)

    # Run quick test first
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        success = run_import_test()
        sys.exit(0 if success else 1)

    # Run full test suite
    unittest.main(verbosity=2)
