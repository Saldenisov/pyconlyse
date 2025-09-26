#!/usr/bin/env python3
"""Unit tests for main_ctrl modular components

Comprehensive test suite with mocking for external dependencies.
"""

import os
import subprocess

# Test imports
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.append(".")

from config import (
    DEVICE_SERVER_CONFIGS,
    Timeouts,
    ZMQConfig,
    get_all_device_types,
    get_device_server_config,
    get_instances_for_device,
)
from device_manager import DeviceServerManager
from infrastructure_manager import TangoInfrastructureManager
from monitoring_threads import DeviceMonitorThread, ElyseDataThread


class TestConfig(unittest.TestCase):
    """Test configuration module."""

    def test_device_server_configs_exist(self):
        """Test that device server configurations are properly defined."""
        self.assertIsInstance(DEVICE_SERVER_CONFIGS, dict)
        self.assertGreater(len(DEVICE_SERVER_CONFIGS), 0)

        # Check structure of each config
        for device_type, config in DEVICE_SERVER_CONFIGS.items():
            self.assertIn("instances", config)
            self.assertIn("script", config)
            self.assertIsInstance(config["instances"], list)
            self.assertIsInstance(config["script"], str)

    def test_get_device_server_config(self):
        """Test getting device server configuration."""
        # Test existing device type
        config = get_device_server_config("BASLER")
        self.assertIsInstance(config, dict)
        self.assertIn("instances", config)

        # Test non-existing device type
        config = get_device_server_config("NONEXISTENT")
        self.assertEqual(config, {})

    def test_get_all_device_types(self):
        """Test getting all device types."""
        types = get_all_device_types()
        self.assertIsInstance(types, list)
        self.assertIn("BASLER", types)
        self.assertIn("STANDA", types)

    def test_get_instances_for_device(self):
        """Test getting instances for a device."""
        instances = get_instances_for_device("BASLER")
        self.assertIsInstance(instances, list)
        self.assertIn("V0", instances)

        # Test non-existing device
        instances = get_instances_for_device("NONEXISTENT")
        self.assertEqual(instances, [])

    def test_timeouts_defined(self):
        """Test that timeout values are properly defined."""
        self.assertIsInstance(Timeouts.DATABASE_CONNECTION, float)
        self.assertIsInstance(Timeouts.DEVICE_OPERATION, float)
        self.assertIsInstance(Timeouts.SUBPROCESS_START, float)
        self.assertGreater(Timeouts.DATABASE_CONNECTION, 0)

    def test_zmq_config(self):
        """Test ZMQ configuration."""
        self.assertIsInstance(ZMQConfig.ELYSE_DATA_ADDRESS, str)
        self.assertIsInstance(ZMQConfig.ELYSE_DATA_FALLBACK, str)
        self.assertIsInstance(ZMQConfig.LINGER_TIME, int)


class TestTangoInfrastructureManager(unittest.TestCase):
    """Test TangoInfrastructureManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = TangoInfrastructureManager()

    def test_initialization(self):
        """Test manager initialization."""
        self.assertEqual(self.manager.processes, {})
        self.assertFalse(self.manager.is_running)
        self.assertIsInstance(self.manager.bin_path, Path)

    @patch.dict(os.environ, {}, clear=True)
    def test_start_infrastructure_no_tango_root(self):
        """Test infrastructure start fails without TANGO_ROOT."""
        result = self.manager.start_infrastructure()
        self.assertFalse(result)

    @patch.dict(os.environ, {"TANGO_ROOT": "/fake/path"})
    @patch("infrastructure_manager.subprocess.Popen")
    def test_start_database_success(self, mock_popen):
        """Test successful database start."""
        # Mock process that stays running (TimeoutExpired on wait)
        mock_process = Mock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired([], 2)
        mock_popen.return_value = mock_process

        result = self.manager._start_database("/fake/path")
        self.assertTrue(result)
        self.assertIn("database", self.manager.processes)

        # Verify command was called correctly
        mock_popen.assert_called_once()
        args = mock_popen.call_args
        self.assertIn("start-db.bat", args[0][0][2])

    @patch.dict(os.environ, {"TANGO_ROOT": "/fake/path"})
    @patch("infrastructure_manager.subprocess.Popen")
    def test_start_database_failure(self, mock_popen):
        """Test database start failure."""
        # Mock process that exits immediately with error code
        mock_process = Mock()
        mock_process.wait.return_value = None  # Doesn't raise TimeoutExpired
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        result = self.manager._start_database("/fake/path")
        self.assertTrue(result)  # Still returns True as process started

    @patch.dict(os.environ, {"TANGO_ROOT": "/fake/path"})
    @patch("infrastructure_manager.socket.gethostname")
    @patch("infrastructure_manager.subprocess.Popen")
    def test_start_starter_success(self, mock_popen, mock_hostname):
        """Test successful starter start."""
        mock_hostname.return_value = "testhost"
        mock_process = Mock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired([], 2)
        mock_popen.return_value = mock_process

        result = self.manager._start_starter("/fake/path")
        self.assertTrue(result)
        self.assertIn("starter", self.manager.processes)

    @patch("infrastructure_manager.Database")
    def test_check_tango_running_success(self, mock_database):
        """Test successful Tango connection check."""
        mock_db = Mock()
        mock_db.get_info.return_value = None
        mock_database.return_value = mock_db

        result = self.manager.check_tango_running()
        self.assertTrue(result)

    @patch("infrastructure_manager.Database")
    def test_check_tango_running_failure(self, mock_database):
        """Test failed Tango connection check."""
        mock_database.side_effect = Exception("Connection failed")

        result = self.manager.check_tango_running()
        self.assertFalse(result)

    def test_stop_infrastructure(self):
        """Test infrastructure stop."""
        # Add mock processes
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        self.manager.processes["database"] = mock_process
        self.manager.is_running = True

        result = self.manager.stop_infrastructure()
        self.assertTrue(result)
        self.assertFalse(self.manager.is_running)
        self.assertEqual(len(self.manager.processes), 0)

        # Verify process was terminated
        mock_process.terminate.assert_called_once()

    @patch("infrastructure_manager.subprocess.run")
    def test_check_starter_running(self, mock_run):
        """Test checking if Starter is running."""
        # Mock successful tasklist output
        mock_result = Mock()
        mock_result.stdout = "Starter.exe    1234"
        mock_run.return_value = mock_result

        result = self.manager.check_starter_running()
        self.assertTrue(result)

        # Mock output without Starter
        mock_result.stdout = "notepad.exe    5678"
        result = self.manager.check_starter_running()
        self.assertFalse(result)


class TestDeviceServerManager(unittest.TestCase):
    """Test DeviceServerManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = DeviceServerManager()

    def test_initialization(self):
        """Test manager initialization."""
        self.assertEqual(self.manager.running_servers, {})
        self.assertIsInstance(self.manager.device_configs, dict)
        self.assertIsInstance(self.manager.bin_path, Path)

    def test_unknown_device_type(self):
        """Test starting unknown device type."""
        result = self.manager.start_deviceserver("UNKNOWN", "V0")
        self.assertFalse(result)

    @patch("device_manager.Path.exists")
    def test_missing_startup_script(self, mock_exists):
        """Test behavior when startup script is missing."""
        mock_exists.return_value = False

        result = self.manager.start_deviceserver("BASLER", "V0")
        self.assertFalse(result)

    @patch("device_manager.Path.exists")
    @patch("device_manager.subprocess.Popen")
    def test_start_deviceserver_success(self, mock_popen, mock_exists):
        """Test successful device server start."""
        mock_exists.return_value = True
        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = self.manager.start_deviceserver("BASLER", "V0", "FULL")
        self.assertTrue(result)

        # Check server was registered
        server_key = "BASLER_V0"
        self.assertIn(server_key, self.manager.running_servers)

        server_info = self.manager.running_servers[server_key]
        self.assertEqual(server_info["device_type"], "BASLER")
        self.assertEqual(server_info["instance"], "V0")
        self.assertEqual(server_info["vis_type"], "FULL")

    def test_stop_nonexistent_server(self):
        """Test stopping a server that doesn't exist."""
        result = self.manager.stop_deviceserver("BASLER", "V0")
        self.assertFalse(result)

    def test_stop_server_success(self):
        """Test successful server stop."""
        # Add a mock running server
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
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

    @patch("device_manager.sleep")  # Mock sleep to speed up test
    def test_restart_server(self, mock_sleep):
        """Test server restart."""
        # Add a mock running server
        mock_process = Mock()
        mock_process.poll.return_value = None
        server_key = "BASLER_V0"
        self.manager.running_servers[server_key] = {
            "process": mock_process,
            "device_type": "BASLER",
            "instance": "V0",
            "vis_type": "FULL",
        }

        with patch.object(
            self.manager, "start_deviceserver", return_value=True
        ) as mock_start:
            result = self.manager.restart_deviceserver("BASLER", "V0", "MINIMAL")
            self.assertTrue(result)
            mock_start.assert_called_once_with("BASLER", "V0", "MINIMAL")

    def test_get_running_servers(self):
        """Test getting running server status."""
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

    def test_is_server_running(self):
        """Test checking if server is running."""
        # Add mock running server
        mock_process = Mock()
        mock_process.poll.return_value = None
        self.manager.running_servers["BASLER_V0"] = {
            "process": mock_process,
            "device_type": "BASLER",
            "instance": "V0",
            "vis_type": "FULL",
        }

        self.assertTrue(self.manager.is_server_running("BASLER", "V0"))
        self.assertFalse(self.manager.is_server_running("STANDA", "V0"))

    def test_stop_all_servers(self):
        """Test stopping all servers."""
        # Add mock servers
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
        self.assertEqual(len(self.manager.running_servers), 0)


class TestMonitoringThreads(unittest.TestCase):
    """Test monitoring thread classes."""

    def setUp(self):
        """Set up test fixtures."""
        self.device_monitor = DeviceMonitorThread()
        self.elyse_thread = ElyseDataThread()

    def test_device_monitor_initialization(self):
        """Test device monitor thread initialization."""
        self.assertFalse(self.device_monitor.running)
        self.assertEqual(len(self.device_monitor.taurus_devices), 0)

    @patch("monitoring_threads.Database")
    def test_device_monitor_initialize_devices(self, mock_database):
        """Test device initialization in monitor thread."""
        mock_db = Mock()
        mock_db.get_device_exported.return_value = ["device1", "device2"]
        mock_database.return_value = mock_db

        devices = self.device_monitor._initialize_devices()
        self.assertIsInstance(devices, list)
        self.assertGreater(len(devices), 0)

    @patch("monitoring_threads.Device")
    def test_device_monitor_create_proxies(self, mock_device):
        """Test device proxy creation."""
        mock_device_instance = Mock()
        mock_device.return_value = mock_device_instance

        devices = ["test/device/1", "test/device/2"]
        self.device_monitor._create_device_proxies(devices)

        self.assertEqual(len(self.device_monitor.taurus_devices), 2)

    def test_device_monitor_interruptible_sleep(self):
        """Test interruptible sleep functionality."""
        start_time = time.time()

        # Start sleep in separate thread
        def sleep_and_stop():
            time.sleep(0.1)
            self.device_monitor.running = False

        self.device_monitor.running = True
        threading.Thread(target=sleep_and_stop).start()

        self.device_monitor._interruptible_sleep(1.0)  # Should be interrupted
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 0.5)  # Should be much less than 1 second

    def test_elyse_thread_initialization(self):
        """Test ELYSE thread initialization."""
        self.assertFalse(self.elyse_thread.running)
        self.assertEqual(self.elyse_thread.zmq_address, ZMQConfig.ELYSE_DATA_ADDRESS)

    def test_elyse_thread_custom_address(self):
        """Test ELYSE thread with custom address."""
        custom_address = "tcp://localhost:9999"
        thread = ElyseDataThread(custom_address)
        self.assertEqual(thread.zmq_address, custom_address)

    @patch("monitoring_threads.zmq.Context")
    def test_elyse_thread_zmq_setup_success(self, mock_context):
        """Test successful ZMQ socket setup."""
        mock_ctx = Mock()
        mock_socket = Mock()
        mock_ctx.socket.return_value = mock_socket
        mock_context.return_value = mock_ctx

        context, socket = self.elyse_thread._setup_zmq_socket()
        self.assertIsNotNone(context)
        self.assertIsNotNone(socket)

    @patch("monitoring_threads.zmq.Context")
    def test_elyse_thread_zmq_setup_with_fallback(self, mock_context):
        """Test ZMQ socket setup with fallback address."""
        mock_ctx = Mock()
        mock_socket = Mock()
        mock_ctx.socket.return_value = mock_socket
        mock_context.return_value = mock_ctx

        # First bind fails, second succeeds
        import zmq

        mock_socket.bind.side_effect = [zmq.ZMQError("Address in use"), None]

        context, socket = self.elyse_thread._setup_zmq_socket()
        self.assertIsNotNone(context)
        self.assertIsNotNone(socket)
        self.assertEqual(self.elyse_thread.zmq_address, ZMQConfig.ELYSE_DATA_FALLBACK)

    def test_device_monitor_add_remove_device(self):
        """Test dynamic device addition and removal."""
        device_name = "test/device/dynamic"

        with patch("monitoring_threads.Device") as mock_device:
            mock_device_instance = Mock()
            mock_device.return_value = mock_device_instance

            # Add device
            self.device_monitor.add_device(device_name)
            self.assertIn(device_name, self.device_monitor.taurus_devices)

            # Remove device
            self.device_monitor.remove_device(device_name)
            self.assertNotIn(device_name, self.device_monitor.taurus_devices)

    def test_thread_stop_methods(self):
        """Test thread stop methods."""
        self.device_monitor.stop()
        self.assertFalse(self.device_monitor.running)

        self.elyse_thread.stop()
        self.assertFalse(self.elyse_thread.running)


class TestIntegration(unittest.TestCase):
    """Integration tests for module interactions."""

    def test_manager_initialization(self):
        """Test that all managers can be initialized together."""
        infra_mgr = TangoInfrastructureManager()
        device_mgr = DeviceServerManager()
        monitor_thread = DeviceMonitorThread()
        elyse_thread = ElyseDataThread()

        # All should initialize without errors
        self.assertIsInstance(infra_mgr, TangoInfrastructureManager)
        self.assertIsInstance(device_mgr, DeviceServerManager)
        self.assertIsInstance(monitor_thread, DeviceMonitorThread)
        self.assertIsInstance(elyse_thread, ElyseDataThread)

    def test_config_integration(self):
        """Test that configurations work with managers."""
        device_mgr = DeviceServerManager()

        # Device manager should use configurations correctly
        self.assertEqual(device_mgr.device_configs, DEVICE_SERVER_CONFIGS)

        # Should be able to get device types
        available_types = device_mgr.get_available_device_types()
        self.assertEqual(set(available_types.keys()), set(get_all_device_types()))

    @patch.dict(os.environ, {"TANGO_ROOT": "/fake/path"})
    def test_managers_use_same_bin_path(self):
        """Test that managers can use the same bin path."""
        test_path = Path("/test/bin")

        infra_mgr = TangoInfrastructureManager(test_path)
        device_mgr = DeviceServerManager(test_path)

        self.assertEqual(infra_mgr.bin_path, test_path)
        self.assertEqual(device_mgr.bin_path, test_path)


if __name__ == "__main__":
    # Configure logging for tests
    import logging

    logging.basicConfig(level=logging.WARNING)

    # Run tests
    unittest.main(verbosity=2)
