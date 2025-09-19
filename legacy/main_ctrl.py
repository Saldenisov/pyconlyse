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

    def auto_start_tango_infrastructure(self):
        """Check if Tango is running, start only if needed (Windows service mode)"""
        try:
            self.log_message("Checking Tango infrastructure status...")
            self.status_label.setText("Checking Tango Status...")
            self.status_label.setStyleSheet(
                "QLabel { color: orange; font-weight: bold; }"
            )

            # Use a timer to check after UI is fully loaded
            def delayed_check():
                try:
                    # Check if Tango Database is running
                    tango_running = self.tango_manager.check_tango_running()

                    if tango_running:
                        # Tango is already running (likely from Windows startup service)
                        logger.info("Tango infrastructure detected as already running")
                        self.log_message(
                            "✓ Tango Database already running (Windows service)"
                        )

                        # Check if Starter is also running
                        starter_running = self._check_starter_running()
                        if starter_running:
                            self.log_message(
                                "✓ Tango Starter already running (Windows service)"
                            )
                        else:
                            self.log_message(
                                "⚠ Tango Starter not detected - may need manual start"
                            )

                        # Update UI for already running state
                        self.tango_manager.is_running = True
                        self.btn_start_tango.setEnabled(False)
                        self.btn_stop_tango.setEnabled(True)
                        self.status_label.setText("System Running (Windows Services)")
                        self.status_label.setStyleSheet(
                            "QLabel { color: green; font-weight: bold; }"
                        )

                        # Start Astor GUI if not running
                        QTimer.singleShot(
                            5000, self._start_astor_if_needed
                        )  # 5 seconds delay

                    else:
                        # Tango not running - start it
                        self.log_message(
                            "⚠ Tango not detected - starting infrastructure..."
                        )
                        success = self.tango_manager.start_infrastructure(
                            progress_callback=lambda msg: self.log_message(msg)
                        )

                        if success:
                            self.btn_start_tango.setEnabled(False)
                            self.btn_stop_tango.setEnabled(True)
                            self.status_label.setText(
                                "Tango Infrastructure Starting..."
                            )
                            self.log_message("Tango infrastructure startup initiated")

                            # Auto-configure Astor after startup
                            QTimer.singleShot(
                                15000, self.auto_configure_astor
                            )  # 15 seconds delay
                        else:
                            self.log_message("❌ Failed to start Tango infrastructure")
                            self.status_label.setText("Tango Start Failed")
                            self.status_label.setStyleSheet(
                                "QLabel { color: red; font-weight: bold; }"
                            )

                except Exception as e:
                    logger.error(f"Error during Tango check/start: {e}")
                    self.log_message(f"Error checking Tango status: {e}")
                    self.status_label.setText("Tango Check Error")
                    self.status_label.setStyleSheet(
                        "QLabel { color: red; font-weight: bold; }"
                    )

            # Delay check by 2 seconds to allow UI to fully load
            QTimer.singleShot(2000, delayed_check)

        except Exception as e:
            logger.error(f"Error in auto_start_tango_infrastructure: {e}")
            self.log_message(f"Tango check setup error: {e}")

    def _check_starter_running(self) -> bool:
        """Check if Tango Starter process is running"""
        try:
            import subprocess

            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq Starter.exe"],
                check=False,
                capture_output=True,
                text=True,
                shell=True,
            )
            return "Starter.exe" in result.stdout
        except Exception as e:
            logger.debug(f"Error checking Starter process: {e}")
            return False

    def _start_astor_if_needed(self):
        """Start Astor GUI if it's not already running"""
        try:
            import os

            tango_root = os.environ.get("TANGO_ROOT")
            if not tango_root:
                self.log_message("⚠ TANGO_ROOT not set - cannot start Astor")
                return

            # Check if Astor is already running
            result = subprocess.run(
                ["tasklist", "/fi", "imagename eq java.exe"],
                check=False,
                capture_output=True,
                text=True,
                shell=True,
            )

            if "astor" in result.stdout.lower():
                self.log_message("✓ Astor GUI already running")
                return

            # Start Astor
            self.log_message("Starting Astor GUI...")
            astor_cmd = ["cmd", "/c", f"{tango_root}\\bin\\start-astor.bat"]

            astor_process = subprocess.Popen(
                astor_cmd,
                cwd=str(self.tango_manager.bin_path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.tango_manager.processes["astor"] = astor_process
            self.log_message("✓ Astor GUI started")

        except Exception as e:
            logger.error(f"Error starting Astor: {e}")
            self.log_message(f"Error starting Astor: {e}")

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("PYCONLYSE Control Center v2.0")
        self.setWindowIcon(QIcon("icons/main_icon.png"))
        self.setMinimumSize(800, 600)

        # Main layout
        main_layout = QVBoxLayout()

        # Create toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # Create main content with splitter
        splitter = QSplitter()

        # Left panel - tabs
        tabs = self.create_tabs()
        splitter.addWidget(tabs)

        # Right panel - status and logs
        status_widget = self.create_status_panel()
        splitter.addWidget(status_widget)

        splitter.setStretchFactor(0, 3)  # Tabs get more space
        splitter.setStretchFactor(1, 1)  # Status panel gets less space

        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

    def create_toolbar(self) -> QWidget:
        """Create the main toolbar with system controls"""
        toolbar_frame = QFrame()
        toolbar_frame.setFrameStyle(QFrame.StyledPanel)
        toolbar_layout = QHBoxLayout()

        # Tango Infrastructure Controls
        tango_group = QGroupBox("Tango Infrastructure")
        tango_layout = QHBoxLayout()

        self.btn_start_tango = QPushButton("Start Tango")
        self.btn_start_tango.setIcon(QIcon("icons/DL.svg"))
        self.btn_start_tango.clicked.connect(self.start_tango_infrastructure)

        self.btn_stop_tango = QPushButton("Stop Tango")
        self.btn_stop_tango.setIcon(QIcon("icons/rect20454.png"))
        self.btn_stop_tango.clicked.connect(self.stop_tango_infrastructure)
        self.btn_stop_tango.setEnabled(False)

        self.btn_configure_astor = QPushButton("Configure Astor")
        self.btn_configure_astor.setIcon(QIcon("icons/experiment.svg"))
        self.btn_configure_astor.clicked.connect(self.configure_astor)

        tango_layout.addWidget(self.btn_start_tango)
        tango_layout.addWidget(self.btn_stop_tango)
        tango_layout.addWidget(self.btn_configure_astor)
        tango_group.setLayout(tango_layout)

        # Client Management Controls
        client_group = QGroupBox("Client Management")
        client_layout = QHBoxLayout()

        self.btn_close_all_clients = QPushButton("Close All Clients")
        self.btn_close_all_clients.setIcon(QIcon("icons/close.png"))
        self.btn_close_all_clients.clicked.connect(self.close_all_clients)

        self.btn_show_clients = QPushButton("Show Active")
        self.btn_show_clients.setIcon(QIcon("icons/info.png"))
        self.btn_show_clients.clicked.connect(self.show_active_clients)

        client_layout.addWidget(self.btn_close_all_clients)
        client_layout.addWidget(self.btn_show_clients)
        client_group.setLayout(client_layout)

        # Status indicator
        self.status_label = QLabel("System Ready")
        self.status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")

        toolbar_layout.addWidget(tango_group)
        toolbar_layout.addWidget(client_group)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.status_label)

        toolbar_frame.setLayout(toolbar_layout)
        return toolbar_frame

    def create_tabs(self) -> QTabWidget:
        """Create the main tab widget"""
        tabs = QTabWidget()

        # Clients tab
        clients_tab = self.create_clients_tab()
        tabs.addTab(clients_tab, "Device Clients")

        # Devices tab
        devices_tab = self.create_devices_tab()
        tabs.addTab(devices_tab, "Device Status")

        # ELYSE tab
        elyse_tab = self.create_elyse_tab()
        tabs.addTab(elyse_tab, "ELYSE Control")

        # DeviceServers tab (new)
        servers_tab = self.create_deviceservers_tab()
        tabs.addTab(servers_tab, "DeviceServers")

        return tabs

    def create_clients_tab(self) -> QWidget:
        """Create the device clients tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Visualization type selection
        vis_group = QGroupBox("Visualization Type")
        vis_layout = QHBoxLayout()

        for vis_type in VisType:
            rb = QtWidgets.QRadioButton(text=vis_type.value)
            if vis_type == VisType.FULL:
                rb.setChecked(True)
            rb.toggled.connect(partial(self.on_vis_type_changed, vis_type.value))
            vis_layout.addWidget(rb)

        vis_group.setLayout(vis_layout)
        layout.addWidget(vis_group)

        # Device client controls
        scroll_area = QScrollArea()
        clients_widget = QWidget()
        clients_layout = QVBoxLayout()

        # Create device client sections from ClientManager registry
        available_clients = self.client_manager.get_available_clients()
        device_types = []

        for client_type, config in available_clients.items():
            instances = list(config["layouts"].keys())
            icon = config["icon"].replace("icons/", "")  # Remove path prefix
            device_types.append((client_type, instances, icon))

        for device_type, instances, icon_name in device_types:
            section = self.create_device_client_section(
                device_type, instances, icon_name
            )
            clients_layout.addWidget(section)

        # Special controls (lights, etc.)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        clients_layout.addWidget(separator)

        lights_section = self.create_lights_section()
        clients_layout.addWidget(lights_section)

        clients_layout.addStretch()
        clients_widget.setLayout(clients_layout)
        scroll_area.setWidget(clients_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        tab.setLayout(layout)
        return tab

    def create_device_client_section(
        self, device_type: str, instances: List[str], icon_name: str
    ) -> QWidget:
        """Create a device client control section"""
        section = QFrame()
        section.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout()

        # Button
        button = TaurusCommandButton(text=device_type, parent=self)
        try:
            button.setIcon(QIcon(f"icons/{icon_name}"))
        except:
            pass  # Icon not found, continue without

        # Combo box
        combo = TaurusValueComboBox(parent=self)
        combo.addItems(instances)

        # Connect button
        button.clicked.connect(partial(self.start_client, device_type, combo))

        layout.addWidget(button)
        layout.addWidget(combo)
        layout.addStretch()

        section.setLayout(layout)
        return section

    def create_lights_section(self) -> QWidget:
        """Create the lights control section"""
        section = QFrame()
        section.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Room Controls:"))

        # Light and laser buttons
        self.btn_light_room = TaurusCommandButton(text="SM Light", parent=self)
        self.btn_light_room.setIcon(QIcon("icons/light.png"))
        self.btn_light_room.clicked.connect(partial(self.toggle_rpi_pin, 3))

        self.btn_laser = TaurusCommandButton(text="Laser", parent=self)
        self.btn_laser.setIcon(QIcon("icons/laser.svg"))
        self.btn_laser.setEnabled(False)  # Disabled by default for safety
        self.btn_laser.clicked.connect(partial(self.toggle_rpi_pin, 4))

        layout.addWidget(self.btn_light_room)
        layout.addWidget(self.btn_laser)

        # Safety note
        note_label = QLabel("Press 'q' to enable laser button")
        note_label.setStyleSheet("QLabel { color: orange; font-style: italic; }")
        layout.addWidget(note_label)

        layout.addStretch()
        section.setLayout(layout)
        return section

    def create_devices_tab(self) -> QWidget:
        """Create the devices status tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Map button
        self.btn_show_map = QPushButton("Show System Map")
        self.btn_show_map.setIcon(QIcon("icons/layout.svg"))
        self.btn_show_map.clicked.connect(self.show_system_map)
        layout.addWidget(self.btn_show_map)

        # Device status grid
        scroll_area = QScrollArea()
        self.devices_widget = QWidget()
        self.devices_layout = QGridLayout()
        self.devices_widget.setLayout(self.devices_layout)
        scroll_area.setWidget(self.devices_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        tab.setLayout(layout)
        return tab

    def create_elyse_tab(self) -> QWidget:
        """Create the ELYSE control tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        self.elyse_tabs = QTabWidget()
        layout.addWidget(self.elyse_tabs)

        tab.setLayout(layout)
        return tab

    def create_deviceservers_tab(self) -> QWidget:
        """Create the DeviceServers management tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Control buttons
        controls_layout = QHBoxLayout()

        self.btn_refresh_servers = QPushButton("Refresh Status")
        self.btn_refresh_servers.clicked.connect(self.refresh_deviceserver_status)

        self.btn_start_all_servers = QPushButton("Start All Configured")
        self.btn_start_all_servers.clicked.connect(self.start_all_deviceservers)

        self.btn_stop_all_servers = QPushButton("Stop All")
        self.btn_stop_all_servers.clicked.connect(self.stop_all_deviceservers)

        controls_layout.addWidget(self.btn_refresh_servers)
        controls_layout.addWidget(self.btn_start_all_servers)
        controls_layout.addWidget(self.btn_stop_all_servers)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # DeviceServer status area
        scroll_area = QScrollArea()
        self.servers_widget = QWidget()
        self.servers_layout = QVBoxLayout()
        self.servers_widget.setLayout(self.servers_layout)
        scroll_area.setWidget(self.servers_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)

        # Initialize server status display
        self.update_deviceserver_display()

        tab.setLayout(layout)
        return tab

    def create_status_panel(self) -> QWidget:
        """Create the status and logs panel"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Status section
        status_group = QGroupBox("System Status")
        status_layout = QVBoxLayout()

        self.tango_status_label = QLabel("Tango: Not Started")
        self.tango_db_label = QLabel("Database: Not Started")
        self.tango_starter_label = QLabel("Starter: Not Started")
        self.tango_astor_label = QLabel("Astor: Not Started")
        self.deviceservers_status_label = QLabel("DeviceServers: 0 running")

        status_layout.addWidget(self.tango_status_label)
        status_layout.addWidget(self.tango_db_label)
        status_layout.addWidget(self.tango_starter_label)
        status_layout.addWidget(self.tango_astor_label)
        status_layout.addWidget(self.deviceservers_status_label)
        status_group.setLayout(status_layout)

        # Logs section
        logs_group = QGroupBox("Activity Logs")
        logs_layout = QVBoxLayout()

        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(200)
        self.log_display.setReadOnly(True)

        logs_layout.addWidget(self.log_display)
        logs_group.setLayout(logs_layout)

        layout.addWidget(status_group)
        layout.addWidget(logs_group)
        layout.addStretch()

        panel.setLayout(layout)
        return panel

    def setup_connections(self):
        """Setup signal connections"""
        # Create status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # Update every 5 seconds

        # Connect ClientManager signals
        self.client_manager.client_launched.connect(self.on_client_launched)
        self.client_manager.client_closed.connect(self.on_client_closed)
        self.client_manager.client_error.connect(self.on_client_error)

    def start_monitoring(self):
        """Start device monitoring and data threads"""
        try:
            # Start device monitoring
            self.device_monitor_thread = DeviceMonitorThread([])
            self.device_monitor_thread.device_state_changed.connect(
                self.on_device_state_changed
            )
            self.device_monitor_thread.start()

            # Start ELYSE data thread
            self.elyse_data_thread = ElyseDataThread()
            self.elyse_data_thread.data_signal.connect(self.on_elyse_data_received)
            self.elyse_data_thread.start()

            self.populate_device_status()

        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            self.log_message(f"Warning: Monitoring not available - {e}")

    def populate_device_status(self):
        """Populate the device status display with timeout protection"""

        def _populate_devices():
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

        try:
            # Use timeout for device list retrieval
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_populate_devices)
                devices = future.result(timeout=10.0)  # 10 second timeout

            # Clear existing layout on main thread
            while self.devices_layout.count():
                child = self.devices_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Add device labels in grid on main thread
            columns = 3
            row, col = 0, 0

            for device_name in devices:
                label = MyQLabel(device_name)
                label.clicked.connect(
                    partial(self.on_device_label_clicked, device_name)
                )
                self.device_labels[device_name] = label

                self.devices_layout.addWidget(label, row, col)
                col += 1
                if col >= columns:
                    col = 0
                    row += 1

            logger.info(f"Populated device status with {len(devices)} devices")

        except concurrent.futures.TimeoutError:
            logger.warning("Device list population timed out")
            self.log_message("Warning: Device list loading timed out")
        except Exception as e:
            logger.error(f"Failed to populate device status: {e}")
            self.log_message(f"Warning: Could not load device list - {e}")

    def update_deviceserver_display(self):
        """Update the DeviceServer management display"""
        # Clear existing widgets
        while self.servers_layout.count():
            child = self.servers_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add server controls for each device type
        for device_type, config in self.device_manager.device_configs.items():
            section = self.create_deviceserver_section(device_type, config["instances"])
            self.servers_layout.addWidget(section)

    def create_deviceserver_section(
        self, device_type: str, instances: List[str]
    ) -> QWidget:
        """Create a DeviceServer control section"""
        section = QFrame()
        section.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        title = QLabel(f"{device_type} DeviceServers")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Instance controls
        for instance in instances:
            instance_layout = QHBoxLayout()

            instance_label = QLabel(f"  {instance}:")
            instance_label.setMinimumWidth(100)

            btn_start = QPushButton("Start")
            btn_start.setMaximumWidth(60)
            btn_start.clicked.connect(
                partial(self.start_deviceserver, device_type, instance)
            )

            btn_stop = QPushButton("Stop")
            btn_stop.setMaximumWidth(60)
            btn_stop.clicked.connect(
                partial(self.stop_deviceserver, device_type, instance)
            )

            btn_restart = QPushButton("Restart")
            btn_restart.setMaximumWidth(80)
            btn_restart.clicked.connect(
                partial(self.restart_deviceserver, device_type, instance)
            )

            status_label = QLabel("Unknown")
            status_label.setMinimumWidth(80)

            instance_layout.addWidget(instance_label)
            instance_layout.addWidget(btn_start)
            instance_layout.addWidget(btn_stop)
            instance_layout.addWidget(btn_restart)
            instance_layout.addWidget(status_label)
            instance_layout.addStretch()

            layout.addLayout(instance_layout)

        section.setLayout(layout)
        return section

    # Event handlers
    def start_tango_infrastructure(self):
        """Start the Tango infrastructure"""
        try:
            progress = QProgressDialog(
                "Starting Tango Infrastructure...", "Cancel", 0, 0, self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            def progress_callback(message):
                progress.setLabelText(message)
                QtWidgets.QApplication.processEvents()

            success = self.tango_manager.start_infrastructure(progress_callback)
            progress.close()

            if success:
                self.btn_start_tango.setEnabled(False)
                self.btn_stop_tango.setEnabled(True)
                self.status_label.setText("Tango Infrastructure Starting...")
                self.status_label.setStyleSheet(
                    "QLabel { color: orange; font-weight: bold; }"
                )
                self.log_message("Tango infrastructure startup initiated")

                # Auto-configure Astor after a delay
                QTimer.singleShot(10000, self.auto_configure_astor)  # 10 seconds delay
            else:
                self.show_error("Failed to start Tango infrastructure")

        except Exception as e:
            logger.error(f"Error starting Tango infrastructure: {e}")
            self.show_error(f"Error starting Tango infrastructure: {e}")

    def stop_tango_infrastructure(self):
        """Stop the Tango infrastructure"""
        try:
            success = self.tango_manager.stop_infrastructure()

            if success:
                self.btn_start_tango.setEnabled(True)
                self.btn_stop_tango.setEnabled(False)
                self.status_label.setText("System Ready")
                self.status_label.setStyleSheet(
                    "QLabel { color: green; font-weight: bold; }"
                )
                self.log_message("Tango infrastructure stopped")
            else:
                self.show_error("Failed to stop Tango infrastructure")

        except Exception as e:
            logger.error(f"Error stopping Tango infrastructure: {e}")
            self.show_error(f"Error stopping Tango infrastructure: {e}")

    def configure_astor(self):
        """Configure Astor for DeviceServer management"""
        try:
            config_script = Path(__file__).parent / "configure_astor_startup.py"
            if not config_script.exists():
                self.show_error("Astor configuration script not found!")
                return

            # Run configuration script
            process = subprocess.Popen(
                [sys.executable, str(config_script)],
                cwd=str(config_script.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()

            if process.returncode == 0:
                self.log_message("Astor configuration completed successfully")
                self.show_info(
                    "Astor configuration completed!\nDeviceServers should now be managed automatically."
                )
            else:
                self.log_message(f"Astor configuration failed: {stderr}")
                self.show_error(f"Astor configuration failed:\n{stderr}")

        except Exception as e:
            logger.error(f"Error configuring Astor: {e}")
            self.show_error(f"Error configuring Astor: {e}")

    def auto_configure_astor(self):
        """Automatically configure Astor after Tango startup"""
        self.log_message("Auto-configuring Astor...")
        self.configure_astor()

    def start_client(self, device_type: str, combo: TaurusValueComboBox):
        """Start a device client using ClientManager"""
        try:
            instance = combo.itemText(combo.currentIndex())

            # Check if client is already running
            if self.client_manager.is_client_running(device_type, instance):
                self.log_message(f"{device_type}/{instance} client is already running")
                self.show_info(
                    f"{device_type} client for {instance} is already running."
                )
                return

            # Launch the client
            success = self.client_manager.launch_client(
                device_type, instance, self.type_vis
            )

            if success:
                self.log_message(f"Started {device_type} client: {instance}")
            else:
                self.log_message(f"Failed to start {device_type} client: {instance}")
                self.show_error(f"Failed to start {device_type} client for {instance}")

        except Exception as e:
            logger.error(f"Failed to start client {device_type}: {e}")
            self.log_message(f"Error starting {device_type} client: {e}")
            self.show_error(f"Error starting {device_type} client: {e}")

    def start_deviceserver(self, device_type: str, instance: str):
        """Start a DeviceServer"""
        success = self.device_manager.start_deviceserver(
            device_type, instance, self.type_vis.value
        )
        if success:
            self.log_message(f"Started DeviceServer: {device_type}/{instance}")
        else:
            self.log_message(f"Failed to start DeviceServer: {device_type}/{instance}")
        self.refresh_deviceserver_status()

    def stop_deviceserver(self, device_type: str, instance: str):
        """Stop a DeviceServer"""
        success = self.device_manager.stop_deviceserver(device_type, instance)
        if success:
            self.log_message(f"Stopped DeviceServer: {device_type}/{instance}")
        else:
            self.log_message(f"Failed to stop DeviceServer: {device_type}/{instance}")
        self.refresh_deviceserver_status()

    def restart_deviceserver(self, device_type: str, instance: str):
        """Restart a DeviceServer"""
        success = self.device_manager.restart_deviceserver(
            device_type, instance, self.type_vis.value
        )
        if success:
            self.log_message(f"Restarted DeviceServer: {device_type}/{instance}")
        else:
            self.log_message(
                f"Failed to restart DeviceServer: {device_type}/{instance}"
            )
        self.refresh_deviceserver_status()

    def start_all_deviceservers(self):
        """Start all configured DeviceServers"""
        count = 0
        for device_type, config in self.device_manager.device_configs.items():
            for instance in config["instances"]:
                if self.device_manager.start_deviceserver(
                    device_type, instance, self.type_vis.value
                ):
                    count += 1

        self.log_message(f"Started {count} DeviceServers")
        self.refresh_deviceserver_status()

    def stop_all_deviceservers(self):
        """Stop all running DeviceServers"""
        running_servers = list(self.device_manager.running_servers.keys())
        count = 0

        for server_key in running_servers:
            server_info = self.device_manager.running_servers[server_key]
            if self.device_manager.stop_deviceserver(
                server_info["device_type"], server_info["instance"]
            ):
                count += 1

        self.log_message(f"Stopped {count} DeviceServers")
        self.refresh_deviceserver_status()

    def refresh_deviceserver_status(self):
        """Refresh the DeviceServer status display"""
        # This would update the status labels in the DeviceServer sections
        running_servers = self.device_manager.get_running_servers()
        self.deviceservers_status_label.setText(
            f"DeviceServers: {len(running_servers)} running"
        )

    def toggle_rpi_pin(self, pin: int):
        """Toggle an RPI GPIO pin with timeout protection"""

        def _toggle_pin():
            try:
                rpi_device = Device("manip/v0/rpi4_gpio_v0")
                state = rpi_device.get_pin_state(pin)
                if state != -1:
                    rpi_device.set_pin_state([pin, 1])
                    sleep(0.25)
                    rpi_device.set_pin_state([pin, 0])
                    return True
                return False
            except Exception as e:
                logger.error(f"Device operation failed for pin {pin}: {e}")
                return None

        try:
            # Use timeout for device operations
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_toggle_pin)
                result = future.result(timeout=5.0)  # 5 second timeout

            if result is True:
                self.log_message(f"Toggled RPI pin {pin}")
            elif result is False:
                self.log_message(f"Invalid RPI pin state: {pin}")
            else:
                self.log_message(f"Failed to toggle RPI pin {pin}")

        except concurrent.futures.TimeoutError:
            logger.error(f"RPI pin {pin} toggle timed out")
            self.log_message(f"RPI pin {pin} toggle timed out")
        except Exception as e:
            logger.error(f"Failed to toggle RPI pin {pin}: {e}")
            self.log_message(f"Error toggling RPI pin {pin}: {e}")

    def show_system_map(self):
        """Show the system layout map"""
        try:
            # This would implement the system map display
            # For now, just show a message
            self.show_info(
                "System map functionality will be implemented here.\nThis would show the device layout visualization."
            )

        except Exception as e:
            logger.error(f"Error showing system map: {e}")
            self.show_error(f"Error showing system map: {e}")

    def on_vis_type_changed(self, value: str):
        """Handle visualization type change"""
        self.type_vis = VisType(value)
        self.log_message(f"Visualization type changed to: {value}")

    def on_device_state_changed(self, device_name: str, state):
        """Handle device state change"""
        if device_name in self.device_labels:
            label = self.device_labels[device_name]

            if state == DevState.ON:
                label.update_style("background-color: green")
            elif state == DevState.STANDBY:
                label.update_style("background-color: yellow")
            elif state == DevState.OFF:
                label.update_style("background-color: gray")
            elif state == DevState.FAULT:
                label.update_style("background-color: red")
            else:
                label.update_style("background-color: purple")

    def on_device_label_clicked(self, device_name: str):
        """Handle device label click"""
        self.log_message(f"Device clicked: {device_name}")
        # This could show device details or focus on map

    def on_elyse_data_received(self, message: str):
        """Handle ELYSE data message"""
        try:
            # Process ELYSE data message
            # This is a simplified version of the original implementation
            self.log_message(f"ELYSE data received: {len(message)} bytes")

        except Exception as e:
            logger.error(f"Error processing ELYSE data: {e}")

    def update_status(self):
        """Update system status display"""
        try:
            # Get detailed status of all Tango components
            tango_status = self.tango_manager.get_status()
            tango_running = self.tango_manager.check_tango_running()

            # Update overall Tango status
            if tango_running:
                self.tango_status_label.setText("Tango: Connected")
                self.status_label.setText("System Running")
                self.status_label.setStyleSheet(
                    "QLabel { color: green; font-weight: bold; }"
                )
                # Update the manager's internal flag if we detect it's running
                if not self.tango_manager.is_running:
                    self.tango_manager.is_running = True
                    self.btn_start_tango.setEnabled(False)
                    self.btn_stop_tango.setEnabled(True)
            else:
                self.tango_status_label.setText("Tango: Disconnected")
                self.status_label.setText("System Ready")
                self.status_label.setStyleSheet(
                    "QLabel { color: orange; font-weight: bold; }"
                )
                # Update the manager's internal flag if we detect it's not running
                if self.tango_manager.is_running:
                    self.tango_manager.is_running = False
                    self.btn_start_tango.setEnabled(True)
                    self.btn_stop_tango.setEnabled(False)

            # Update individual component status
            db_status = tango_status.get("database", "Unknown")
            starter_status = tango_status.get("starter", "Unknown")
            astor_status = tango_status.get("astor", "Unknown")

            self.tango_db_label.setText(f"Database: {db_status}")
            self.tango_starter_label.setText(f"Starter: {starter_status}")
            self.tango_astor_label.setText(f"Astor: {astor_status}")

            # Set colors for component status
            for label, status in [
                (self.tango_db_label, db_status),
                (self.tango_starter_label, starter_status),
                (self.tango_astor_label, astor_status),
            ]:
                if "Running" in status:
                    label.setStyleSheet("QLabel { color: green; }")
                elif "Not started" in status:
                    label.setStyleSheet("QLabel { color: gray; }")
                else:
                    label.setStyleSheet("QLabel { color: red; }")

            # Update DeviceServer status
            running_count = len(self.device_manager.get_running_servers())
            self.deviceservers_status_label.setText(
                f"DeviceServers: {running_count} running"
            )

        except Exception as e:
            logger.debug(f"Status update error: {e}")

    def log_message(self, message: str):
        """Add message to log display"""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.log_display.append(formatted_message)

        # Keep only last 100 lines
        if self.log_display.document().lineCount() > 100:
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor)
            cursor.removeSelectedText()

    def show_error(self, message: str):
        """Show error message dialog"""
        QMessageBox.critical(self, "Error", message)

    def show_info(self, message: str):
        """Show info message dialog"""
        QMessageBox.information(self, "Information", message)

    def on_client_launched(self, client_type: str, instance: str):
        """Handle client launched signal"""
        self.log_message(f"Client launched: {client_type}/{instance}")

    def on_client_closed(self, client_type: str, instance: str):
        """Handle client closed signal"""
        self.log_message(f"Client closed: {client_type}/{instance}")

    def on_client_error(self, client_type: str, instance: str, error: str):
        """Handle client error signal"""
        self.log_message(f"Client error {client_type}/{instance}: {error}")

    def get_active_clients_info(self) -> str:
        """Get information about active clients"""
        active_clients = self.client_manager.get_active_clients()
        if not active_clients:
            return "No active clients"

        info_lines = []
        for key, client in active_clients.items():
            info_lines.append(
                f"- {client.client_type}/{client.instance} ({client.vis_type.value})"
            )

        return f"Active clients ({len(active_clients)}):\n" + "\n".join(info_lines)

    def close_all_clients(self):
        """Close all active clients"""
        try:
            active_count = len(self.client_manager.get_active_clients())
            if active_count > 0:
                self.client_manager.close_all_clients()
                self.log_message(f"Closed {active_count} client(s)")
            else:
                self.log_message("No active clients to close")
        except Exception as e:
            logger.error(f"Error closing clients: {e}")
            self.log_message(f"Error closing clients: {e}")

    def show_active_clients(self):
        """Show information about active clients"""
        try:
            clients_info = self.get_active_clients_info()
            self.show_info(f"Active Client Information:\n\n{clients_info}")
        except Exception as e:
            logger.error(f"Error showing active clients: {e}")
            self.show_error(f"Error showing active clients: {e}")

    def closeEvent(self, event):
        """Handle application close"""
        try:
            # Close all active clients
            self.close_all_clients()

            # Stop monitoring threads
            if self.device_monitor_thread:
                self.device_monitor_thread.stop()
                self.device_monitor_thread.wait(1000)

            if self.elyse_data_thread:
                self.elyse_data_thread.stop()
                self.elyse_data_thread.wait(1000)

            # Close ZMQ socket
            if self.zmq_socket_push:
                self.zmq_socket_push.close()
            if self.zmq_context:
                self.zmq_context.destroy()

            logger.info("Application closing")

        except Exception as e:
            logger.error(f"Error during close: {e}")

        event.accept()


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
