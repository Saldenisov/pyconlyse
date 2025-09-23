#!/usr/bin/env python3
"""PYCONLYSE Main Control Interface - Modular Version

Clean, modular main control interface with proper separation of concerns.
"""

import logging
import sys
from functools import partial
from pathlib import Path
from threading import Thread
from time import sleep

# PyQt5 imports
from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import *

# Tango/Taurus imports
from taurus.qt.qtgui.application import TaurusApplication

# Local modular imports
sys.path.append(str(Path(__file__).parent))

from ClientManager import ClientManager
from config import *
from device_manager import DeviceServerManager
from infrastructure_manager import TangoInfrastructureManager
from monitoring_threads import DeviceMonitorThread, ElyseDataThread

from DeviceServers.shared.DS_Widget import VisType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class PyConlyseMainWindow(QtWidgets.QWidget):
    """Main application window with modular components."""

    def __init__(self):
        super().__init__()

        # Initialize modular managers
        self.tango_manager = TangoInfrastructureManager()
        self.device_manager = DeviceServerManager()
        self.client_manager = ClientManager()

        # Initialize state
        self.type_vis = VisType.FULL
        self.device_labels = {}
        self.device_monitor_thread = None
        self.elyse_data_thread = None

        self.setup_ui()
        self.setup_connections()
        self.auto_start_tango()
        self.start_monitoring()

    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(UIConfig.MIN_WIDTH, UIConfig.MIN_HEIGHT)

        main_layout = QVBoxLayout()

        # Create toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # Create main content
        splitter = QSplitter()
        tabs = self.create_tabs()
        status_panel = self.create_status_panel()

        splitter.addWidget(tabs)
        splitter.addWidget(status_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def create_toolbar(self):
        """Create main toolbar."""
        toolbar_frame = QFrame()
        toolbar_frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout()

        # Tango controls
        tango_group = QGroupBox("Tango Infrastructure")
        tango_layout = QHBoxLayout()

        self.btn_start_tango = QPushButton("Start Tango")
        self.btn_start_tango.clicked.connect(self.start_tango_infrastructure)

        self.btn_stop_tango = QPushButton("Stop Tango")
        self.btn_stop_tango.clicked.connect(self.stop_tango_infrastructure)
        self.btn_stop_tango.setEnabled(False)

        tango_layout.addWidget(self.btn_start_tango)
        tango_layout.addWidget(self.btn_stop_tango)
        tango_group.setLayout(tango_layout)

        # Status label
        self.status_label = QLabel("System Ready")
        self.status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")

        layout.addWidget(tango_group)
        layout.addStretch()
        layout.addWidget(self.status_label)
        toolbar_frame.setLayout(layout)

        return toolbar_frame

    def create_tabs(self):
        """Create tab widget."""
        tabs = QTabWidget()

        # Device clients tab
        clients_tab = QWidget()
        tabs.addTab(clients_tab, "Device Clients")

        # Device servers tab
        servers_tab = self.create_deviceservers_tab()
        tabs.addTab(servers_tab, "DeviceServers")

        return tabs

    def create_deviceservers_tab(self):
        """Create device servers management tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Controls
        controls_layout = QHBoxLayout()
        self.btn_start_all = QPushButton("Start All")
        self.btn_start_all.clicked.connect(self.start_all_deviceservers)
        self.btn_stop_all = QPushButton("Stop All")
        self.btn_stop_all.clicked.connect(self.stop_all_deviceservers)

        controls_layout.addWidget(self.btn_start_all)
        controls_layout.addWidget(self.btn_stop_all)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Server controls
        scroll_area = QScrollArea()
        servers_widget = QWidget()
        self.servers_layout = QVBoxLayout()

        for device_type, config in DEVICE_SERVER_CONFIGS.items():
            section = self.create_server_section(device_type, config["instances"])
            self.servers_layout.addWidget(section)

        servers_widget.setLayout(self.servers_layout)
        scroll_area.setWidget(servers_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        tab.setLayout(layout)
        return tab

    def create_server_section(self, device_type, instances):
        """Create device server section."""
        section = QFrame()
        section.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout()

        title = QLabel(f"{device_type} Servers")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        for instance in instances:
            instance_layout = QHBoxLayout()
            instance_layout.addWidget(QLabel(f"  {instance}:"))

            btn_start = QPushButton("Start")
            btn_start.clicked.connect(
                partial(self.start_deviceserver, device_type, instance)
            )

            btn_stop = QPushButton("Stop")
            btn_stop.clicked.connect(
                partial(self.stop_deviceserver, device_type, instance)
            )

            instance_layout.addWidget(btn_start)
            instance_layout.addWidget(btn_stop)
            instance_layout.addStretch()
            layout.addLayout(instance_layout)

        section.setLayout(layout)
        return section

    def create_status_panel(self):
        """Create status panel."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Status labels
        self.tango_status = QLabel("Tango: Not Started")
        self.servers_status = QLabel("Servers: 0 running")

        layout.addWidget(QLabel("System Status:"))
        layout.addWidget(self.tango_status)
        layout.addWidget(self.servers_status)

        # Logs
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(UIConfig.LOG_DISPLAY_HEIGHT)
        self.log_display.setReadOnly(True)
        layout.addWidget(QLabel("Activity Logs:"))
        layout.addWidget(self.log_display)

        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def setup_connections(self):
        """Setup signal connections."""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(UIConfig.STATUS_UPDATE_INTERVAL)

    def auto_start_tango(self):
        """Auto-start Tango if needed."""
        QTimer.singleShot(AutoStartDelays.TANGO_CHECK, self.check_and_start_tango)

    def check_and_start_tango(self):
        """Check if Tango is running and start if needed."""
        if self.tango_manager.check_tango_running():
            self.log_message("✓ Tango already running")
            self.tango_manager.is_running = True
            self.btn_start_tango.setEnabled(False)
            self.btn_stop_tango.setEnabled(True)
        else:
            self.log_message("⚠ Tango not detected")

    def start_monitoring(self):
        """Start monitoring threads."""
        try:
            self.device_monitor_thread = DeviceMonitorThread()
            self.device_monitor_thread.device_state_changed.connect(
                self.on_device_state_changed
            )
            self.device_monitor_thread.start()

            self.elyse_data_thread = ElyseDataThread()
            self.elyse_data_thread.data_signal.connect(self.on_elyse_data_received)
            self.elyse_data_thread.start()
        except Exception as e:
            self.log_message(f"Warning: Monitoring not available - {e}")

    def start_tango_infrastructure(self):
        """Start Tango infrastructure."""
        success = self.tango_manager.start_infrastructure(self.log_message)
        if success:
            self.btn_start_tango.setEnabled(False)
            self.btn_stop_tango.setEnabled(True)
            self.log_message("Tango infrastructure started")

    def stop_tango_infrastructure(self):
        """Stop Tango infrastructure."""
        success = self.tango_manager.stop_infrastructure()
        if success:
            self.btn_start_tango.setEnabled(True)
            self.btn_stop_tango.setEnabled(False)
            self.log_message("Tango infrastructure stopped")

    def start_deviceserver(self, device_type, instance):
        """Start a device server."""
        success = self.device_manager.start_deviceserver(
            device_type, instance, self.type_vis.value
        )
        if success:
            self.log_message(f"Started {device_type}/{instance}")

    def stop_deviceserver(self, device_type, instance):
        """Stop a device server."""
        success = self.device_manager.stop_deviceserver(device_type, instance)
        if success:
            self.log_message(f"Stopped {device_type}/{instance}")

    def start_all_deviceservers(self):
        """Start all device servers."""
        count = self.device_manager.start_all_configured_servers(self.type_vis.value)
        self.log_message(f"Started {count} device servers")

    def stop_all_deviceservers(self):
        """Stop all device servers."""
        count = self.device_manager.stop_all_servers()
        self.log_message(f"Stopped {count} device servers")

    def update_status(self):
        """Update status display."""
        try:
            # Tango status
            if self.tango_manager.check_tango_running():
                self.tango_status.setText("Tango: Connected")
                self.tango_status.setStyleSheet("color: green;")
            else:
                self.tango_status.setText("Tango: Disconnected")
                self.tango_status.setStyleSheet("color: red;")

            # Server status
            running_count = len(self.device_manager.get_running_servers())
            self.servers_status.setText(f"Servers: {running_count} running")
        except Exception as e:
            logger.debug(f"Status update error: {e}")

    def log_message(self, message):
        """Add message to log display."""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")

        # Keep only last lines
        if self.log_display.document().lineCount() > MAX_LOG_LINES:
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor)
            cursor.removeSelectedText()

    def on_device_state_changed(self, device_name, state):
        """Handle device state change."""
        # This would update device status if we had device labels

    def on_elyse_data_received(self, message):
        """Handle ELYSE data."""
        logger.debug(f"ELYSE data: {len(message)} bytes")

    def closeEvent(self, event):
        """Handle application close."""
        try:
            # Stop threads
            if self.device_monitor_thread:
                self.device_monitor_thread.stop()
                self.device_monitor_thread.wait(Timeouts.THREAD_SHUTDOWN)

            if self.elyse_data_thread:
                self.elyse_data_thread.stop()
                self.elyse_data_thread.wait(Timeouts.THREAD_SHUTDOWN)

            # Cleanup managers
            self.device_manager.cleanup()

            logger.info("Application closing")
        except Exception as e:
            logger.error(f"Error during close: {e}")

        event.accept()


def main():
    """Main application entry point."""
    try:
        app = TaurusApplication(sys.argv, cmd_line_parser=None)

        # Create and show main window
        window = PyConlyseMainWindow()
        window.show()

        # Handle keyboard activation (optional)
        def activate_buttons():
            try:
                import keyboard

                while True:
                    sleep(0.15)
                    if keyboard.is_pressed("q"):
                        # Could enable laser button here
                        pass
            except:
                pass  # Keyboard module not available

        Thread(target=activate_buttons, daemon=True).start()

        logger.info(f"{APP_NAME} v{APP_VERSION} started")
        sys.exit(app.exec_())

    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
