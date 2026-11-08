#!/usr/bin/env python3
"""PYCONLYSE Main Control Interface - Modular Version

Clean, modular main control interface with proper separation of concerns:
- Infrastructure management (TangoInfrastructureManager)
- Device server lifecycle (DeviceServerManager)
- Background monitoring (DeviceMonitorThread, ElyseDataThread)
- Configuration management (config module)
- Comprehensive testing

Author: PYCONLYSE Team
Version: 3.0 (Modular Refactored)
"""

from sys import modules as _refactor_modules

import concurrent.futures
import logging
import subprocess
import sys
import traceback
from functools import partial
from pathlib import Path
from threading import Lock, Thread
from time import sleep
from typing import Dict, List

# Third-party imports
import zmq

# PyQt5 imports
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Tango/Taurus imports
from tango import Database
from taurus import Device
from taurus.core.tango import DevState
from taurus.qt.qtgui.application import TaurusApplication
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.input import TaurusValueComboBox

# Local imports
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from legacy.main_control_methods_auto_start_tango_infrastructure import _bind_main_control_methods_auto_start_tango_infrastructure
from legacy.main_control_methods_create_deviceserver_section import _bind_main_control_methods_create_deviceserver_section

from ClientManager import ClientManager

from DeviceServers.shared.DS_Widget import VisType
from gui.MyWidgets import MyQLabel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("main_ctrl.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TangoInfrastructureManager:
    """Manages Tango infrastructure startup and monitoring"""

    def __init__(self):
        self.processes = {}
        self.is_running = False
        self.bin_path = Path(__file__).parent

    def start_infrastructure(self, progress_callback=None) -> bool:
        """Start the Tango infrastructure - Database AND Starter together"""
        try:
            if self.is_running:
                logger.warning("Tango infrastructure is already running")
                return True

            # Start both Database and Starter components together
            success = self._start_database_and_starter(progress_callback)
            if success:
                self.is_running = True
                logger.info(
                    "Tango infrastructure (Database + Starter) startup initiated"
                )
            return success

        except Exception as e:
            logger.error(f"Failed to start Tango infrastructure: {e}")
            return False

    def _start_database_and_starter(self, progress_callback=None) -> bool:
        """Start both Tango Database and Starter processes"""
        try:
            import os

            tango_root = os.environ.get("TANGO_ROOT")
            if not tango_root:
                logger.error("TANGO_ROOT environment variable not set!")
                return False

            # Step 1: Start Tango Database
            if progress_callback:
                progress_callback("Starting Tango Database...")

            db_cmd = ["cmd", "/c", f"{tango_root}\\bin\\start-db.bat"]
            logger.info(f"Starting Tango Database: {' '.join(db_cmd)}")

            # Use timeout for subprocess to prevent hanging
            try:
                db_process = subprocess.Popen(
                    db_cmd,
                    cwd=str(self.bin_path),
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                # Wait briefly to see if process starts successfully
                try:
                    db_process.wait(timeout=2.0)
                    # If we get here, process exited quickly (likely error)
                    if db_process.returncode != 0:
                        logger.warning(
                            f"Database process exited with code {db_process.returncode}"
                        )
                except subprocess.TimeoutExpired:
                    # Process is still running, which is expected
                    logger.info("Database process started and running")
            except Exception as e:
                logger.error(f"Failed to start database process: {e}")
                return False

            self.processes["database"] = db_process

            # Wait for database to initialize
            import time

            time.sleep(5)

            # Step 2: Start Tango Starter
            if progress_callback:
                progress_callback("Starting Tango Starter...")

            # Determine hostname (usually 'everest' for your system)
            import socket

            hostname = socket.gethostname().lower()

            starter_cmd = [f"{tango_root}\\bin\\Starter.exe", hostname]
            logger.info(f"Starting Tango Starter: {' '.join(starter_cmd)}")

            # Use timeout for starter process to prevent hanging
            try:
                starter_process = subprocess.Popen(
                    starter_cmd,
                    cwd=str(self.bin_path),
                    shell=False,  # Don't use shell for Starter.exe
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                # Wait briefly to see if process starts successfully
                try:
                    starter_process.wait(timeout=2.0)
                    # If we get here, process exited quickly (likely error)
                    if starter_process.returncode != 0:
                        logger.warning(
                            f"Starter process exited with code {starter_process.returncode}"
                        )
                except subprocess.TimeoutExpired:
                    # Process is still running, which is expected
                    logger.info("Starter process started and running")
            except Exception as e:
                logger.error(f"Failed to start starter process: {e}")
                return False

            self.processes["starter"] = starter_process

            # Optional: Start Astor for DeviceServer management
            if progress_callback:
                progress_callback("Starting Astor...")

            time.sleep(3)  # Wait a bit for Starter to initialize

            astor_cmd = ["cmd", "/c", f"{tango_root}\\bin\\start-astor.bat"]
            logger.info(f"Starting Astor: {' '.join(astor_cmd)}")

            astor_process = subprocess.Popen(
                astor_cmd,
                cwd=str(self.bin_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.processes["astor"] = astor_process

            if progress_callback:
                progress_callback("Tango infrastructure started successfully")

            logger.info("Successfully started Tango Database, Starter, and Astor")
            return True

        except Exception as e:
            logger.error(f"Failed to start database and starter: {e}")
            return False

    def stop_infrastructure(self) -> bool:
        """Stop the Tango infrastructure (Database, Starter, and Astor)"""
        try:
            stopped_components = []

            # Stop components in reverse order: Astor, Starter, then Database
            component_order = ["astor", "starter", "database"]

            for component in component_order:
                if component in self.processes:
                    process = self.processes[component]
                    if process and process.poll() is None:
                        logger.info(f"Terminating {component} process")
                        try:
                            process.terminate()
                            # Wait a bit for graceful shutdown
                            import time

                            time.sleep(2)

                            # Force kill if still running
                            if process.poll() is None:
                                logger.info(f"Force killing {component} process")
                                process.kill()

                            stopped_components.append(component)
                        except Exception as e:
                            logger.warning(f"Error stopping {component}: {e}")
                    else:
                        logger.info(f"{component} process was already stopped")

            # Clear all processes
            self.processes.clear()
            self.is_running = False

            logger.info(
                f"Tango infrastructure stopped. Components: {', '.join(stopped_components)}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to stop Tango infrastructure: {e}")
            return False

    def check_tango_running(self, timeout: float = 5.0) -> bool:
        """Check if Tango database is actually running by trying to connect with timeout"""

        def _check_db():
            try:
                # Try to create a database connection
                db = Database()
                # Try a simple database operation
                db.get_info()
                return True
            except Exception as e:
                logger.debug(f"Tango DB not accessible: {e}")
                return False

        try:
            # Use ThreadPoolExecutor with timeout to avoid blocking main thread
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_check_db)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.debug(f"Tango DB check timed out after {timeout}s")
            return False
        except Exception as e:
            logger.debug(f"Tango DB check failed: {e}")
            return False

    def get_status(self) -> Dict[str, str]:
        """Get status of infrastructure components"""
        status = {}

        # Check each component individually
        components = ["database", "starter", "astor"]

        for component in components:
            if component in self.processes:
                process = self.processes[component]
                if process:
                    if process.poll() is None:
                        status[component] = "Running"
                    else:
                        status[component] = f"Stopped (exit code: {process.poll()})"
                else:
                    status[component] = "Not started"
            else:
                status[component] = "Not started"

        # Add overall Tango connectivity status
        status["tango_connectivity"] = (
            "Connected" if self.check_tango_running() else "Disconnected"
        )

        return status


class DeviceServerManager:
    """Manages DeviceServer lifecycle (start/stop/restart)"""

    def __init__(self):
        self.device_configs = {
            "ANDOR_CCD": {"instances": ["V0"], "script": "ANDOR_CCD"},
            "BASLER": {"instances": ["V0", "Cam1", "Cam2", "Cam3"], "script": "BASLER"},
            "ARCHIVE": {"instances": ["Main"], "script": "ARCHIVE"},
            "OWIS": {"instances": ["V0", "VD2", "all"], "script": "OWIS_PS90"},
            "STANDA": {
                "instances": ["alignment", "V0", "V0_short", "ELYSE", "OPA"],
                "script": "STANDA",
            },
            "NETIO": {"instances": ["all", "V0", "VD2"], "script": "NETIO"},
            "TOPDIRECT": {"instances": ["VD2", "all"], "script": "TOPDIRECT"},
            "LASER_POINTING": {
                "instances": ["Cam1", "Cam2", "Cam3", "V0", "3P"],
                "script": "LASER_POINTING",
            },
        }
        self.running_servers = {}
        self.bin_path = Path(__file__).parent

    def start_deviceserver(
        self, device_type: str, instance: str, vis_type: str = "FULL"
    ) -> bool:
        """Start a DeviceServer using the unified script"""
        try:
            if device_type not in self.device_configs:
                logger.error(f"Unknown device type: {device_type}")
                return False

            script_path = self.bin_path / "start_deviceserver.cmd"
            if not script_path.exists():
                logger.error("DeviceServer startup script not found!")
                return False

            cmd = [str(script_path), device_type, instance, vis_type]
            logger.info(f"Starting DeviceServer: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                cwd=str(self.bin_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            server_key = f"{device_type}_{instance}"
            self.running_servers[server_key] = {
                "process": process,
                "device_type": device_type,
                "instance": instance,
                "vis_type": vis_type,
            }

            logger.info(f"DeviceServer {device_type}/{instance} started")
            return True

        except Exception as e:
            logger.error(f"Failed to start DeviceServer {device_type}/{instance}: {e}")
            return False

    def stop_deviceserver(self, device_type: str, instance: str) -> bool:
        """Stop a DeviceServer"""
        try:
            server_key = f"{device_type}_{instance}"
            if server_key in self.running_servers:
                process = self.running_servers[server_key]["process"]
                if process and process.poll() is None:
                    process.terminate()
                    logger.info(f"DeviceServer {device_type}/{instance} stopped")
                del self.running_servers[server_key]
                return True
            logger.warning(
                f"DeviceServer {device_type}/{instance} not found in running servers"
            )
            return False

        except Exception as e:
            logger.error(f"Failed to stop DeviceServer {device_type}/{instance}: {e}")
            return False

    def restart_deviceserver(
        self, device_type: str, instance: str, vis_type: str = "FULL"
    ) -> bool:
        """Restart a DeviceServer"""
        logger.info(f"Restarting DeviceServer {device_type}/{instance}")
        self.stop_deviceserver(device_type, instance)
        sleep(2)  # Wait a bit before restarting
        return self.start_deviceserver(device_type, instance, vis_type)

    def get_running_servers(self) -> Dict[str, Dict]:
        """Get status of running DeviceServers"""
        status = {}
        for server_key, server_info in self.running_servers.items():
            process = server_info["process"]
            if process:
                if process.poll() is None:
                    status[server_key] = {**server_info, "status": "Running"}
                else:
                    status[server_key] = {
                        **server_info,
                        "status": f"Stopped (exit code: {process.poll()})",
                    }
            else:
                status[server_key] = {**server_info, "status": "Not started"}
        return status


class DeviceMonitorThread(QThread):
    """Thread for monitoring device states"""

    device_state_changed = pyqtSignal(str, object)  # device_name, state

    def __init__(self, device_names: List[str]):
        super().__init__()
        self.device_names = device_names
        self.taurus_devices = {}
        self.running = False
        self._lock = Lock()

    def run(self):
        """Main monitoring loop with timeout protection"""
        try:
            # Initialize Tango devices with timeout
            def _init_devices():
                try:
                    db = Database()
                    servers = ["ELYSE", "manip"]
                    devices = []
                    for server in servers:
                        devices.extend(list(db.get_device_exported(f"{server}*")))
                    return devices
                except Exception as e:
                    logger.warning(f"Could not get device list: {e}")
                    return []

            # Use timeout for device initialization
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_init_devices)
                    devices = future.result(timeout=10.0)  # 10 second timeout
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "Device initialization timed out, continuing with empty list"
                )
                devices = []

            # Create device proxies
            for dev_name in devices:
                if not self.running:  # Check if we should stop
                    break
                try:
                    dev = Device(dev_name)
                    with self._lock:  # Minimize lock scope
                        self.taurus_devices[dev_name] = dev
                    logger.debug(f"Created device proxy for {dev_name}")
                except Exception as e:
                    logger.warning(f"Could not create device proxy for {dev_name}: {e}")

            self.running = True
            logger.info(
                f"Device monitoring started with {len(self.taurus_devices)} devices"
            )

            while self.running:
                # Create a copy of devices to avoid holding lock during operations
                with self._lock:
                    devices_copy = dict(self.taurus_devices)

                for dev_name, dev in devices_copy.items():
                    if not self.running:  # Check if we should stop
                        break

                    try:
                        # Add timeout for device state reading
                        def _read_state():
                            state_ds = dev.state
                            if state_ds == 4:
                                return DevState.FAULT
                            return dev.State()

                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=1
                        ) as executor:
                            future = executor.submit(_read_state)
                            state = future.result(
                                timeout=2.0
                            )  # 2 second timeout per device

                        self.device_state_changed.emit(dev_name, state)

                    except concurrent.futures.TimeoutError:
                        logger.debug(f"State read timeout for {dev_name}")
                        self.device_state_changed.emit(dev_name, DevState.FAULT)
                    except Exception as e:
                        logger.debug(f"Error reading state of {dev_name}: {e}")
                        self.device_state_changed.emit(dev_name, DevState.FAULT)

                    # Small delay between devices to prevent overwhelming
                    if self.running:
                        sleep(0.1)

                # Main loop delay
                for i in range(20):  # 2 second delay with interrupt checking
                    if not self.running:
                        break
                    sleep(0.1)

        except Exception as e:
            logger.error(f"Device monitoring thread error: {e}")
            logger.debug(traceback.format_exc())

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        logger.info("Device monitoring stopped")


class ElyseDataThread(QThread):
    """Thread for handling ELYSE ZMQ data"""

    data_signal = pyqtSignal(str)

    def __init__(self, zmq_address: str = "tcp://129.175.100.128:6050"):
        super().__init__()
        self.zmq_address = zmq_address
        self.running = False

    def run(self):
        """Main ZMQ listening loop with proper timeout and shutdown handling"""
        context = None
        socket = None

        try:
            context = zmq.Context()
            socket = context.socket(zmq.PULL)

            # Set socket options for proper cleanup
            socket.setsockopt(zmq.LINGER, 1000)  # 1 second linger
            socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second receive timeout

            try:
                socket.bind(self.zmq_address)
            except zmq.ZMQError as e:
                logger.warning(f"Could not bind to {self.zmq_address}: {e}")
                # Try alternative address
                alt_address = "tcp://127.0.0.1:6051"
                try:
                    socket.bind(alt_address)
                    self.zmq_address = alt_address
                    logger.info(f"Bound to alternative address: {alt_address}")
                except zmq.ZMQError as e2:
                    logger.error(f"Could not bind to alternative address: {e2}")
                    return

            self.running = True
            logger.info(f"ELYSE data thread started, listening on {self.zmq_address}")

            while self.running:
                try:
                    # Use timeout-based receive instead of NOBLOCK
                    message = socket.recv_string(
                        flags=0
                    )  # Will timeout due to RCVTIMEO
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
            # Ensure proper cleanup
            if socket:
                try:
                    socket.close()
                except:
                    pass
            if context:
                try:
                    context.term()
                except:
                    pass
            logger.info("ELYSE data thread cleaned up")

    def stop(self):
        """Stop the data thread"""
        self.running = False
        logger.info("ELYSE data thread stopped")


class PyConlyseMainWindow(QtWidgets.QWidget):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize managers
        self.tango_manager = TangoInfrastructureManager()
        self.device_manager = DeviceServerManager()
        self.client_manager = ClientManager()

        # Initialize state
        self.type_vis = VisType.FULL
        self.device_labels = {}
        self.elyse_elements = {}
        self.device_monitor_thread = None
        self.elyse_data_thread = None

        # ZMQ for ELYSE communication
        self.zmq_context = zmq.Context()
        self.zmq_socket_push = self.zmq_context.socket(zmq.PUSH)
        self.zmq_socket_push.connect("tcp://127.0.0.1:5556")

        self.setup_ui()
        self.setup_connections()

        # Auto-start Tango infrastructure (Database + Starter)
        self.auto_start_tango_infrastructure()

        self.start_monitoring()

    _main_control_methods_auto_start_tango_infrastructure = _bind_main_control_methods_auto_start_tango_infrastructure(_refactor_modules[__name__])
    auto_start_tango_infrastructure = _main_control_methods_auto_start_tango_infrastructure["auto_start_tango_infrastructure"]

    _check_starter_running = _main_control_methods_auto_start_tango_infrastructure["_check_starter_running"]

    _start_astor_if_needed = _main_control_methods_auto_start_tango_infrastructure["_start_astor_if_needed"]

    setup_ui = _main_control_methods_auto_start_tango_infrastructure["setup_ui"]

    create_toolbar = _main_control_methods_auto_start_tango_infrastructure["create_toolbar"]

    create_tabs = _main_control_methods_auto_start_tango_infrastructure["create_tabs"]

    create_clients_tab = _main_control_methods_auto_start_tango_infrastructure["create_clients_tab"]

    create_device_client_section = _main_control_methods_auto_start_tango_infrastructure["create_device_client_section"]

    create_lights_section = _main_control_methods_auto_start_tango_infrastructure["create_lights_section"]

    create_devices_tab = _main_control_methods_auto_start_tango_infrastructure["create_devices_tab"]

    create_elyse_tab = _main_control_methods_auto_start_tango_infrastructure["create_elyse_tab"]

    create_deviceservers_tab = _main_control_methods_auto_start_tango_infrastructure["create_deviceservers_tab"]

    create_status_panel = _main_control_methods_auto_start_tango_infrastructure["create_status_panel"]

    setup_connections = _main_control_methods_auto_start_tango_infrastructure["setup_connections"]

    start_monitoring = _main_control_methods_auto_start_tango_infrastructure["start_monitoring"]

    populate_device_status = _main_control_methods_auto_start_tango_infrastructure["populate_device_status"]

    update_deviceserver_display = _main_control_methods_auto_start_tango_infrastructure["update_deviceserver_display"]
    del _main_control_methods_auto_start_tango_infrastructure

    _main_control_methods_create_deviceserver_section = _bind_main_control_methods_create_deviceserver_section(_refactor_modules[__name__])
    create_deviceserver_section = _main_control_methods_create_deviceserver_section["create_deviceserver_section"]

    # Event handlers
    start_tango_infrastructure = _main_control_methods_create_deviceserver_section["start_tango_infrastructure"]

    stop_tango_infrastructure = _main_control_methods_create_deviceserver_section["stop_tango_infrastructure"]

    configure_astor = _main_control_methods_create_deviceserver_section["configure_astor"]

    auto_configure_astor = _main_control_methods_create_deviceserver_section["auto_configure_astor"]

    start_client = _main_control_methods_create_deviceserver_section["start_client"]

    start_deviceserver = _main_control_methods_create_deviceserver_section["start_deviceserver"]

    stop_deviceserver = _main_control_methods_create_deviceserver_section["stop_deviceserver"]

    restart_deviceserver = _main_control_methods_create_deviceserver_section["restart_deviceserver"]

    start_all_deviceservers = _main_control_methods_create_deviceserver_section["start_all_deviceservers"]

    stop_all_deviceservers = _main_control_methods_create_deviceserver_section["stop_all_deviceservers"]

    refresh_deviceserver_status = _main_control_methods_create_deviceserver_section["refresh_deviceserver_status"]

    toggle_rpi_pin = _main_control_methods_create_deviceserver_section["toggle_rpi_pin"]

    show_system_map = _main_control_methods_create_deviceserver_section["show_system_map"]

    on_vis_type_changed = _main_control_methods_create_deviceserver_section["on_vis_type_changed"]

    on_device_state_changed = _main_control_methods_create_deviceserver_section["on_device_state_changed"]

    on_device_label_clicked = _main_control_methods_create_deviceserver_section["on_device_label_clicked"]
        # This could show device details or focus on map

    on_elyse_data_received = _main_control_methods_create_deviceserver_section["on_elyse_data_received"]

    update_status = _main_control_methods_create_deviceserver_section["update_status"]

    log_message = _main_control_methods_create_deviceserver_section["log_message"]

    show_error = _main_control_methods_create_deviceserver_section["show_error"]

    show_info = _main_control_methods_create_deviceserver_section["show_info"]

    on_client_launched = _main_control_methods_create_deviceserver_section["on_client_launched"]

    on_client_closed = _main_control_methods_create_deviceserver_section["on_client_closed"]

    on_client_error = _main_control_methods_create_deviceserver_section["on_client_error"]

    get_active_clients_info = _main_control_methods_create_deviceserver_section["get_active_clients_info"]

    close_all_clients = _main_control_methods_create_deviceserver_section["close_all_clients"]

    show_active_clients = _main_control_methods_create_deviceserver_section["show_active_clients"]

    closeEvent = _main_control_methods_create_deviceserver_section["closeEvent"]
    del _main_control_methods_create_deviceserver_section


def main():
    """Main application entry point"""
    try:
        app = TaurusApplication(sys.argv, cmd_line_parser=None)

        # Create and show main window
        window = PyConlyseMainWindow()
        window.show()

        # Handle keyboard activation for laser button
        def activate_buttons():
            import keyboard

            while True:
                sleep(0.15)
                try:
                    if keyboard.is_pressed("q"):
                        window.btn_laser.setEnabled(True)
                    else:
                        window.btn_laser.setEnabled(False)
                except:
                    break  # Keyboard module might not be available

        # Start keyboard thread
        Thread(target=activate_buttons, daemon=True).start()

        # Start application
        logger.info("PYCONLYSE Control Center v2.0 started")
        sys.exit(app.exec_())

    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
