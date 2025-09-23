#!/usr/bin/env python3
"""Simplified tests for modular components that can run without Tango dependencies"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Mock external dependencies before importing our modules
sys.modules["tango"] = MagicMock()
sys.modules["taurus"] = MagicMock()
sys.modules["taurus.qt"] = MagicMock()
sys.modules["taurus.qt.qtgui"] = MagicMock()
sys.modules["taurus.qt.qtgui.application"] = MagicMock()
sys.modules["taurus.qt.qtgui.button"] = MagicMock()
sys.modules["taurus.qt.qtgui.input"] = MagicMock()
sys.modules["taurus.core"] = MagicMock()
sys.modules["taurus.core.tango"] = MagicMock()
sys.modules["PyQt5"] = MagicMock()
sys.modules["PyQt5.QtCore"] = MagicMock()
sys.modules["PyQt5.QtWidgets"] = MagicMock()
sys.modules["PyQt5.QtGui"] = MagicMock()
sys.modules["zmq"] = MagicMock()

# Mock DevState for monitoring tests
mock_devstate = MagicMock()
mock_devstate.ON = "ON"
mock_devstate.OFF = "OFF"
mock_devstate.FAULT = "FAULT"
mock_devstate.STANDBY = "STANDBY"
sys.modules["taurus.core.tango"].DevState = mock_devstate

# Now import our modules
from config import *
from device_manager import DeviceServerManager
from infrastructure_manager import TangoInfrastructureManager


class TestConfiguration(unittest.TestCase):
    """Test the configuration module."""

    def test_device_server_configs_structure(self):
        """Test that device server configs have proper structure."""
        self.assertIsInstance(DEVICE_SERVER_CONFIGS, dict)
        self.assertGreater(len(DEVICE_SERVER_CONFIGS), 0)

        for device_type, config in DEVICE_SERVER_CONFIGS.items():
            self.assertIn("instances", config)
            self.assertIn("script", config)
            self.assertIsInstance(config["instances"], list)
            self.assertIsInstance(config["script"], str)
            self.assertGreater(len(config["instances"]), 0)

    def test_timeout_values(self):
        """Test that timeout values are reasonable."""
        self.assertGreater(Timeouts.DATABASE_CONNECTION, 0)
        self.assertGreater(Timeouts.DEVICE_OPERATION, 0)
        self.assertLessEqual(Timeouts.DATABASE_CONNECTION, 30.0)

    def test_config_helpers(self):
        """Test configuration helper functions."""
        # Test valid device type
        config = get_device_server_config("BASLER")
        self.assertIn("instances", config)

        # Test invalid device type
        config = get_device_server_config("NONEXISTENT")
        self.assertEqual(config, {})

        # Test getting all types
        types = get_all_device_types()
        self.assertIn("BASLER", types)
        self.assertIn("STANDA", types)


class TestTangoInfrastructureManager(unittest.TestCase):
    """Test TangoInfrastructureManager with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = TangoInfrastructureManager(self.temp_dir)

    def tearDown(self):
        """Clean up."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test manager initialization."""
        self.assertEqual(self.manager.processes, {})
        self.assertFalse(self.manager.is_running)
        self.assertEqual(self.manager.bin_path, self.temp_dir)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_tango_root(self):
        """Test behavior when TANGO_ROOT is not set."""
        result = self.manager.start_infrastructure()
        self.assertFalse(result)

    @patch.dict(os.environ, {"TANGO_ROOT": "/fake/path"})
    @patch("infrastructure_manager.subprocess.Popen")
    def test_database_start_success(self, mock_popen):
        """Test successful database start."""
        import subprocess

        # Mock process that continues running
        mock_process = Mock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired([], 2)
        mock_popen.return_value = mock_process

        result = self.manager._start_database("/fake/path")
        self.assertTrue(result)
        self.assertIn("database", self.manager.processes)

    def test_get_status(self):
        """Test status reporting."""
        status = self.manager.get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("database", status)
        self.assertIn("starter", status)
        self.assertIn("astor", status)

    def test_stop_infrastructure(self):
        """Test infrastructure stop."""
        # Add mock process
        mock_process = Mock()
        mock_process.poll.return_value = None
        self.manager.processes["database"] = mock_process
        self.manager.is_running = True

        result = self.manager.stop_infrastructure()
        self.assertTrue(result)
        self.assertFalse(self.manager.is_running)
        self.assertEqual(len(self.manager.processes), 0)


class TestDeviceServerManager(unittest.TestCase):
    """Test DeviceServerManager with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = DeviceServerManager(self.temp_dir)

    def tearDown(self):
        """Clean up."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test manager initialization."""
        self.assertEqual(self.manager.running_servers, {})
        self.assertEqual(self.manager.bin_path, self.temp_dir)
        self.assertEqual(self.manager.device_configs, DEVICE_SERVER_CONFIGS)

    def test_unknown_device_type(self):
        """Test starting unknown device type."""
        result = self.manager.start_deviceserver("UNKNOWN_TYPE", "V0")
        self.assertFalse(result)

    @patch("device_manager.Path.exists", return_value=False)
    def test_missing_script(self, mock_exists):
        """Test behavior when startup script is missing."""
        result = self.manager.start_deviceserver("BASLER", "V0")
        self.assertFalse(result)

    @patch("device_manager.Path.exists", return_value=True)
    @patch("device_manager.subprocess.Popen")
    def test_start_deviceserver_success(self, mock_popen, mock_exists):
        """Test successful device server start."""
        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = self.manager.start_deviceserver("BASLER", "V0", "FULL")
        self.assertTrue(result)

        # Verify server was registered
        server_key = "BASLER_V0"
        self.assertIn(server_key, self.manager.running_servers)

        server_info = self.manager.running_servers[server_key]
        self.assertEqual(server_info["device_type"], "BASLER")
        self.assertEqual(server_info["instance"], "V0")
        self.assertEqual(server_info["vis_type"], "FULL")

    def test_stop_nonexistent_server(self):
        """Test stopping server that doesn't exist."""
        result = self.manager.stop_deviceserver("BASLER", "V0")
        self.assertFalse(result)

    def test_stop_server_success(self):
        """Test successful server stop."""
        # Add mock server
        mock_process = Mock()
        mock_process.poll.return_value = None  # Running
        server_key = "BASLER_V0"
        self.manager.running_servers[server_key] = {
            "process": mock_process,
            "device_type": "BASLER",
            "instance": "V0",
            "vis_type": "FULL",
        }

        result = self.manager.stop_deviceserver("BASLER", "V0")
        self.assertTrue(result)
        self.assertNotIn(server_key, self.manager.running_servers)
        mock_process.terminate.assert_called_once()

    def test_get_running_servers(self):
        """Test getting server status."""
        # Add mock servers
        running_process = Mock()
        running_process.poll.return_value = None
        stopped_process = Mock()
        stopped_process.poll.return_value = 1

        self.manager.running_servers["BASLER_V0"] = {
            "process": running_process,
            "device_type": "BASLER",
            "instance": "V0",
            "vis_type": "FULL",
        }
        self.manager.running_servers["STANDA_V0"] = {
            "process": stopped_process,
            "device_type": "STANDA",
            "instance": "V0",
            "vis_type": "FULL",
        }

        status = self.manager.get_running_servers()
        self.assertIn("BASLER_V0", status)
        self.assertEqual(status["BASLER_V0"]["status"], "Running")

    def test_bulk_operations(self):
        """Test bulk start/stop operations."""
        # Test start all (should return 0 since no valid scripts exist)
        with patch("device_manager.Path.exists", return_value=False):
            count = self.manager.start_all_configured_servers()
            self.assertEqual(count, 0)

        # Test stop all with mock servers
        for i, device_type in enumerate(["BASLER", "STANDA"]):
            mock_process = Mock()
            mock_process.poll.return_value = None
            server_key = f"{device_type}_V{i}"
            self.manager.running_servers[server_key] = {
                "process": mock_process,
                "device_type": device_type,
                "instance": f"V{i}",
                "vis_type": "FULL",
            }

        count = self.manager.stop_all_servers()
        self.assertEqual(count, 2)


class TestIntegration(unittest.TestCase):
    """Test integration between components."""

    def test_managers_initialization(self):
        """Test that all managers can be initialized together."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            infra_mgr = TangoInfrastructureManager(temp_dir)
            device_mgr = DeviceServerManager(temp_dir)

            # Should initialize without errors
            self.assertIsInstance(infra_mgr, TangoInfrastructureManager)
            self.assertIsInstance(device_mgr, DeviceServerManager)

            # Should use same bin path
            self.assertEqual(infra_mgr.bin_path, temp_dir)
            self.assertEqual(device_mgr.bin_path, temp_dir)

        finally:
            import shutil

            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_config_consistency(self):
        """Test configuration consistency across modules."""
        device_mgr = DeviceServerManager()

        # Device manager should use same configs
        self.assertEqual(device_mgr.device_configs, DEVICE_SERVER_CONFIGS)

        # Available types should match config
        available_types = device_mgr.get_available_device_types()
        config_types = get_all_device_types()
        self.assertEqual(set(available_types.keys()), set(config_types))


def run_test_suite():
    """Run the complete test suite."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestTangoInfrastructureManager))
    suite.addTests(loader.loadTestsFromTestCase(TestDeviceServerManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print(f"\n{'=' * 60}")
    print("TEST RESULTS SUMMARY")
    print(f"{'=' * 60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(
        f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100:.1f}%"
    )

    if result.failures:
        print("\nFAILURES:")
        for test, failure in result.failures:
            print(f"- {test}: {failure.split(chr(10))[0]}")

    if result.errors:
        print("\nERRORS:")
        for test, error in result.errors:
            print(f"- {test}: {error.split(chr(10))[0]}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_test_suite()
    sys.exit(0 if success else 1)
