#!/usr/bin/env python3
"""Integration tests for the modular main_ctrl system

Tests the integration between all components to ensure they work together correctly.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import *
from device_manager import DeviceServerManager
from infrastructure_manager import TangoInfrastructureManager
from monitoring_threads import DeviceMonitorThread, ElyseDataThread


class TestModularIntegration(unittest.TestCase):
    """Test integration between all modular components."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for testing
        self.temp_dir = Path(tempfile.mkdtemp())

        # Initialize all managers with the temp directory
        self.infra_manager = TangoInfrastructureManager(self.temp_dir)
        self.device_manager = DeviceServerManager(self.temp_dir)
        self.monitor_thread = DeviceMonitorThread([])
        self.elyse_thread = ElyseDataThread()

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temp directory
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_all_managers_use_same_bin_path(self):
        """Test that managers can be configured to use the same bin path."""
        self.assertEqual(self.infra_manager.bin_path, self.temp_dir)
        self.assertEqual(self.device_manager.bin_path, self.temp_dir)

    def test_configuration_integration(self):
        """Test that configuration values are properly used by managers."""
        # Device manager should use device server configs
        self.assertEqual(self.device_manager.device_configs, DEVICE_SERVER_CONFIGS)

        # Check that we have the expected device types
        expected_types = set(get_all_device_types())
        actual_types = set(self.device_manager.device_configs.keys())
        self.assertEqual(expected_types, actual_types)

    @patch.dict(os.environ, {"TANGO_ROOT": "/fake/tango/root"})
    def test_infrastructure_and_device_manager_coordination(self):
        """Test coordination between infrastructure and device managers."""
        # Infrastructure manager should be able to check if Tango is running
        with patch.object(self.infra_manager, "check_tango_running", return_value=True):
            self.assertTrue(self.infra_manager.check_tango_running())

        # Device manager should be able to list available types
        available_types = self.device_manager.get_available_device_types()
        self.assertIsInstance(available_types, dict)
        self.assertGreater(len(available_types), 0)

    def test_monitoring_threads_initialization(self):
        """Test that monitoring threads can be initialized without errors."""
        # Both threads should initialize properly
        self.assertFalse(self.monitor_thread.running)
        self.assertFalse(self.elyse_thread.running)

        # Should be able to start/stop threads
        self.monitor_thread.stop()
        self.elyse_thread.stop()

        self.assertFalse(self.monitor_thread.running)
        self.assertFalse(self.elyse_thread.running)

    def test_timeout_configurations_are_reasonable(self):
        """Test that timeout values from config are reasonable."""
        # All timeouts should be positive
        self.assertGreater(Timeouts.DATABASE_CONNECTION, 0)
        self.assertGreater(Timeouts.DEVICE_OPERATION, 0)
        self.assertGreater(Timeouts.DEVICE_STATE_READ, 0)
        self.assertGreater(Timeouts.SUBPROCESS_START, 0)

        # Database timeout should be reasonable (not too short, not too long)
        self.assertGreaterEqual(Timeouts.DATABASE_CONNECTION, 1.0)
        self.assertLessEqual(Timeouts.DATABASE_CONNECTION, 30.0)

    def test_zmq_configuration_consistency(self):
        """Test that ZMQ configuration is consistent."""
        # Addresses should be valid strings
        self.assertTrue(ZMQConfig.ELYSE_DATA_ADDRESS.startswith("tcp://"))
        self.assertTrue(ZMQConfig.ELYSE_DATA_FALLBACK.startswith("tcp://"))

        # Linger time should be positive
        self.assertGreater(ZMQConfig.LINGER_TIME, 0)

    def test_device_server_configuration_integrity(self):
        """Test that device server configurations are complete and valid."""
        for device_type, config in DEVICE_SERVER_CONFIGS.items():
            # Each config should have required fields
            self.assertIn("instances", config)
            self.assertIn("script", config)

            # Instances should be a non-empty list
            self.assertIsInstance(config["instances"], list)
            self.assertGreater(len(config["instances"]), 0)

            # Script should be a non-empty string
            self.assertIsInstance(config["script"], str)
            self.assertGreater(len(config["script"]), 0)

    @patch("infrastructure_manager.Database")
    @patch("device_manager.subprocess.Popen")
    @patch("device_manager.Path.exists")
    def test_end_to_end_workflow_simulation(
        self, mock_exists, mock_popen, mock_database
    ):
        """Test a simulated end-to-end workflow."""
        # Setup mocks
        mock_exists.return_value = True
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process

        mock_db = Mock()
        mock_db.get_info.return_value = None
        mock_database.return_value = mock_db

        # 1. Check if Tango is running (should work with timeout protection)
        tango_running = self.infra_manager.check_tango_running()
        self.assertTrue(tango_running)  # Should succeed due to mock

        # 2. Start a device server
        success = self.device_manager.start_deviceserver("BASLER", "V0", "FULL")
        self.assertTrue(success)

        # 3. Check that server is registered
        running_servers = self.device_manager.get_running_servers()
        self.assertIn("BASLER_V0", running_servers)

        # 4. Stop the server
        success = self.device_manager.stop_deviceserver("BASLER", "V0")
        self.assertTrue(success)

        # 5. Verify server is no longer running
        running_servers = self.device_manager.get_running_servers()
        self.assertNotIn("BASLER_V0", running_servers)

    def test_error_handling_resilience(self):
        """Test that the system handles errors gracefully."""
        # Infrastructure manager should handle missing TANGO_ROOT
        with patch.dict(os.environ, {}, clear=True):
            success = self.infra_manager.start_infrastructure()
            self.assertFalse(success)  # Should fail gracefully

        # Device manager should handle unknown device types
        success = self.device_manager.start_deviceserver("UNKNOWN_DEVICE", "V0")
        self.assertFalse(success)  # Should fail gracefully

        # Should be able to get status even when nothing is running
        status = self.infra_manager.get_status()
        self.assertIsInstance(status, dict)

        running_servers = self.device_manager.get_running_servers()
        self.assertIsInstance(running_servers, dict)

    def test_cleanup_methods(self):
        """Test that cleanup methods work properly."""
        # Add some mock servers to device manager
        mock_process = Mock()
        mock_process.poll.return_value = None
        self.device_manager.running_servers["TEST_V0"] = {
            "process": mock_process,
            "device_type": "TEST",
            "instance": "V0",
            "vis_type": "FULL",
        }

        # Cleanup should stop all servers
        self.device_manager.cleanup()

        # Verify cleanup was called
        mock_process.terminate.assert_called()

    def test_configuration_helper_functions(self):
        """Test configuration helper functions."""
        # Test getting device server config
        basler_config = get_device_server_config("BASLER")
        self.assertIn("instances", basler_config)
        self.assertIn("V0", basler_config["instances"])

        # Test getting all device types
        all_types = get_all_device_types()
        self.assertIn("BASLER", all_types)
        self.assertIn("STANDA", all_types)

        # Test getting instances for device
        basler_instances = get_instances_for_device("BASLER")
        self.assertIn("V0", basler_instances)

        # Test non-existent device
        unknown_instances = get_instances_for_device("UNKNOWN")
        self.assertEqual(unknown_instances, [])


class TestModularArchitecture(unittest.TestCase):
    """Test the modular architecture design."""

    def test_module_independence(self):
        """Test that modules can be imported independently."""
        # Each module should be importable on its own
        import config
        import device_manager
        import infrastructure_manager
        import monitoring_threads

        # Modules should have expected classes/functions
        self.assertTrue(hasattr(config, "DEVICE_SERVER_CONFIGS"))
        self.assertTrue(hasattr(infrastructure_manager, "TangoInfrastructureManager"))
        self.assertTrue(hasattr(device_manager, "DeviceServerManager"))
        self.assertTrue(hasattr(monitoring_threads, "DeviceMonitorThread"))
        self.assertTrue(hasattr(monitoring_threads, "ElyseDataThread"))

    def test_module_interfaces(self):
        """Test that modules have clean interfaces."""
        # Infrastructure manager interface
        infra_mgr = TangoInfrastructureManager()
        self.assertTrue(hasattr(infra_mgr, "start_infrastructure"))
        self.assertTrue(hasattr(infra_mgr, "stop_infrastructure"))
        self.assertTrue(hasattr(infra_mgr, "check_tango_running"))
        self.assertTrue(hasattr(infra_mgr, "get_status"))

        # Device manager interface
        device_mgr = DeviceServerManager()
        self.assertTrue(hasattr(device_mgr, "start_deviceserver"))
        self.assertTrue(hasattr(device_mgr, "stop_deviceserver"))
        self.assertTrue(hasattr(device_mgr, "restart_deviceserver"))
        self.assertTrue(hasattr(device_mgr, "get_running_servers"))

    def test_configuration_centralization(self):
        """Test that configuration is properly centralized."""
        # All configuration should come from config module
        from config import (
            APP_NAME,
            APP_VERSION,
            DEVICE_SERVER_CONFIGS,
            Timeouts,
            UIConfig,
            ZMQConfig,
        )

        # Should have all expected configuration sections
        self.assertIsInstance(DEVICE_SERVER_CONFIGS, dict)
        self.assertTrue(hasattr(Timeouts, "DATABASE_CONNECTION"))
        self.assertTrue(hasattr(ZMQConfig, "ELYSE_DATA_ADDRESS"))
        self.assertTrue(hasattr(UIConfig, "MIN_WIDTH"))
        self.assertIsInstance(APP_NAME, str)
        self.assertIsInstance(APP_VERSION, str)


if __name__ == "__main__":
    # Set up logging for tests
    import logging

    logging.basicConfig(level=logging.WARNING)

    # Run tests
    unittest.main(verbosity=2)
