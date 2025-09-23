#!/usr/bin/env python3
"""Monitoring Threads Module

Contains monitoring threads for device state and ELYSE data with proper
timeout protection and error handling.
"""

import concurrent.futures
import logging
import traceback
from threading import Lock
from time import sleep
from typing import List

import zmq
from config import TANGO_SERVERS, Timeouts, ZMQConfig
from PyQt5.QtCore import QThread, pyqtSignal
from tango import Database
from taurus import Device
from taurus.core.tango import DevState

logger = logging.getLogger(__name__)


class DeviceMonitorThread(QThread):
    """Thread for monitoring device states with timeout protection."""

    device_state_changed = pyqtSignal(str, object)  # device_name, state

    def __init__(self, device_names: List[str] = None):
        """Initialize the device monitor thread.

        Args:
            device_names: List of device names to monitor. If None, discovers automatically.

        """
        super().__init__()
        self.device_names = device_names or []
        self.taurus_devices = {}
        self.running = False
        self._lock = Lock()

    def run(self):
        """Main monitoring loop with comprehensive timeout protection."""
        try:
            # Initialize devices with timeout protection
            devices = self._initialize_devices()

            if not devices:
                logger.warning("No devices found for monitoring")
                return

            # Create device proxies with timeout protection
            self._create_device_proxies(devices)

            self.running = True
            logger.info(
                f"Device monitoring started with {len(self.taurus_devices)} devices"
            )

            # Main monitoring loop
            while self.running:
                self._monitor_devices()
                self._interruptible_sleep(2.0)  # 2 second update interval

        except Exception as e:
            logger.error(f"Device monitoring thread error: {e}")
            logger.debug(traceback.format_exc())
        finally:
            self._cleanup()

    def _initialize_devices(self) -> List[str]:
        """Initialize device list with timeout protection.

        Returns:
            List of device names found

        """

        def _get_devices():
            try:
                db = Database()
                devices = []
                for server in TANGO_SERVERS:
                    devices.extend(list(db.get_device_exported(f"{server}*")))
                return devices
            except Exception as e:
                logger.warning(f"Could not get device list: {e}")
                return []

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_get_devices)
                devices = future.result(timeout=Timeouts.DEVICE_INIT)
                logger.info(f"Discovered {len(devices)} devices for monitoring")
                return devices
        except concurrent.futures.TimeoutError:
            logger.warning("Device initialization timed out, using empty list")
            return []
        except Exception as e:
            logger.error(f"Failed to initialize devices: {e}")
            return []

    def _create_device_proxies(self, devices: List[str]):
        """Create device proxies with error handling.

        Args:
            devices: List of device names

        """
        for dev_name in devices:
            if not self.running:  # Check for early termination
                break

            try:
                dev = Device(dev_name)
                with self._lock:
                    self.taurus_devices[dev_name] = dev
                logger.debug(f"Created device proxy for {dev_name}")
            except Exception as e:
                logger.warning(f"Could not create device proxy for {dev_name}: {e}")

    def _monitor_devices(self):
        """Monitor all devices with timeout protection."""
        # Create a copy to avoid holding lock during operations
        with self._lock:
            devices_copy = dict(self.taurus_devices)

        for dev_name, dev in devices_copy.items():
            if not self.running:
                break

            try:
                state = self._read_device_state(dev)
                self.device_state_changed.emit(dev_name, state)
            except Exception as e:
                logger.debug(f"Error reading state of {dev_name}: {e}")
                self.device_state_changed.emit(dev_name, DevState.FAULT)

            # Small delay between devices
            if self.running:
                sleep(0.1)

    def _read_device_state(self, dev: Device) -> DevState:
        """Read device state with timeout protection.

        Args:
            dev: Taurus device proxy

        Returns:
            DevState: Current device state

        """

        def _read_state():
            state_ds = dev.state
            if state_ds == 4:
                return DevState.FAULT
            return dev.State()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_read_state)
                return future.result(timeout=Timeouts.DEVICE_STATE_READ)
        except concurrent.futures.TimeoutError:
            logger.debug("State read timeout for device")
            return DevState.FAULT
        except Exception as e:
            logger.debug(f"Error reading device state: {e}")
            return DevState.FAULT

    def _interruptible_sleep(self, duration: float):
        """Sleep with ability to interrupt for early termination.

        Args:
            duration: Sleep duration in seconds

        """
        steps = int(duration * 10)  # 0.1 second steps
        for _ in range(steps):
            if not self.running:
                break
            sleep(0.1)

    def _cleanup(self):
        """Clean up resources."""
        logger.info("Device monitoring thread cleaning up")
        with self._lock:
            self.taurus_devices.clear()

    def stop(self):
        """Stop the monitoring thread gracefully."""
        self.running = False
        logger.info("Device monitoring stop requested")

    def add_device(self, device_name: str):
        """Add a device to monitor dynamically.

        Args:
            device_name: Name of device to add

        """
        try:
            dev = Device(device_name)
            with self._lock:
                self.taurus_devices[device_name] = dev
            logger.info(f"Added device {device_name} to monitoring")
        except Exception as e:
            logger.error(f"Failed to add device {device_name}: {e}")

    def remove_device(self, device_name: str):
        """Remove a device from monitoring.

        Args:
            device_name: Name of device to remove

        """
        with self._lock:
            if device_name in self.taurus_devices:
                del self.taurus_devices[device_name]
                logger.info(f"Removed device {device_name} from monitoring")


class ElyseDataThread(QThread):
    """Thread for handling ELYSE ZMQ data with robust error handling."""

    data_signal = pyqtSignal(str)

    def __init__(self, zmq_address: str = None):
        """Initialize the ELYSE data thread.

        Args:
            zmq_address: ZMQ address to bind to. Uses default if None.

        """
        super().__init__()
        self.zmq_address = zmq_address or ZMQConfig.ELYSE_DATA_ADDRESS
        self.running = False

    def run(self):
        """Main ZMQ listening loop with comprehensive error handling."""
        context = None
        socket = None

        try:
            context, socket = self._setup_zmq_socket()
            if not socket:
                return

            self.running = True
            logger.info(f"ELYSE data thread started, listening on {self.zmq_address}")

            while self.running:
                try:
                    message = socket.recv_string(flags=0)  # Uses socket timeout
                    if self.running:  # Check if we should still emit
                        self.data_signal.emit(message)
                except zmq.Again:
                    # Timeout occurred, continue loop
                    continue
                except zmq.ZMQError as e:
                    if e.errno == zmq.ETERM:
                        # Context terminated, exit cleanly
                        break
                    logger.debug(f"ZMQ error (continuing): {e}")
                    sleep(0.1)
                except Exception as e:
                    logger.error(f"Error receiving ZMQ message: {e}")
                    sleep(0.1)

        except Exception as e:
            logger.error(f"ELYSE data thread error: {e}")
            logger.debug(traceback.format_exc())
        finally:
            self._cleanup_zmq(socket, context)

    def _setup_zmq_socket(self):
        """Setup ZMQ socket with fallback options.

        Returns:
            Tuple of (context, socket) or (None, None) on failure

        """
        try:
            context = zmq.Context()
            socket = context.socket(zmq.PULL)

            # Set socket options for proper cleanup
            socket.setsockopt(zmq.LINGER, ZMQConfig.LINGER_TIME)
            socket.setsockopt(
                zmq.RCVTIMEO, int(Timeouts.ZMQ_RECEIVE * 1000)
            )  # Convert to ms

            # Try to bind to primary address
            try:
                socket.bind(self.zmq_address)
                logger.info(f"Bound to primary ZMQ address: {self.zmq_address}")
                return context, socket
            except zmq.ZMQError as e:
                logger.warning(f"Could not bind to {self.zmq_address}: {e}")

                # Try fallback address
                try:
                    socket.bind(ZMQConfig.ELYSE_DATA_FALLBACK)
                    self.zmq_address = ZMQConfig.ELYSE_DATA_FALLBACK
                    logger.info(f"Bound to fallback address: {self.zmq_address}")
                    return context, socket
                except zmq.ZMQError as e2:
                    logger.error(f"Could not bind to fallback address: {e2}")
                    socket.close()
                    context.term()
                    return None, None

        except Exception as e:
            logger.error(f"Failed to setup ZMQ socket: {e}")
            return None, None

    def _cleanup_zmq(self, socket, context):
        """Clean up ZMQ resources safely.

        Args:
            socket: ZMQ socket to close
            context: ZMQ context to terminate

        """
        if socket:
            try:
                socket.close()
            except Exception as e:
                logger.debug(f"Error closing ZMQ socket: {e}")

        if context:
            try:
                context.term()
            except Exception as e:
                logger.debug(f"Error terminating ZMQ context: {e}")

        logger.info("ELYSE data thread cleaned up")

    def stop(self):
        """Stop the data thread gracefully."""
        self.running = False
        logger.info("ELYSE data thread stop requested")

    def get_current_address(self) -> str:
        """Get the currently bound ZMQ address.

        Returns:
            Current ZMQ address

        """
        return self.zmq_address
