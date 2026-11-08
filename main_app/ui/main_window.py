#!/usr/bin/env python3
"""PyConlyse Main GUI Window

Non-blocking GUI that starts immediately and handles all connections asynchronously.
"""

from sys import modules as _refactor_modules

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

# Add fixes path and suppress Taurus warnings early
fixes_path = Path(__file__).parents[2] / "fixes"
if str(fixes_path) not in sys.path:
    sys.path.append(str(fixes_path))
from taurus_warnings_fix import suppress_taurus_deprecation_warnings

# Suppress warnings as early as possible
suppress_taurus_deprecation_warnings()

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Add parent directory to path for imports
main_app_path = Path(__file__).parent.parent
sys.path.insert(0, str(main_app_path.parent))

from main_app.ui.main_window_methods_build_minimal_ui import _bind_main_window_methods_build_minimal_ui
from main_app.ui.main_window_methods_create_right_panel import _bind_main_window_methods_create_right_panel
from main_app.ui.main_window_methods_update_db_devices_status_async import _bind_main_window_methods_update_db_devices_status_async

import imageio
import numpy as np
import pyqtgraph as pg

# Additional third-party libs used for legacy features
import zmq
from main_app.core.async_manager import (
    ConnectionStatus,
    StatusUpdate,
)
from main_app.core.config import OFFLINE_MODE
from main_app.core.logging_config import setup_pyconlyse_logging
from main_app.ui.experiment_preparation import open_preparation_window

# Optional DS visualization type
try:
    from DeviceServers.shared.DS_Widget import VisType as DSVisType
except Exception:
    DSVisType = None

logger = logging.getLogger(__name__)


class ThreadSafeSignals(QObject):
    """Thread-safe signals for GUI updates."""

    # Signal for log messages: (level, message, timestamp)
    log_message = pyqtSignal(str, str, float)

    # Signal for status updates: (component, status_str, message)
    status_update = pyqtSignal(str, str, str)


class StatusIndicator(QLabel):
    """Visual status indicator widget."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.setFixedSize(150, 30)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            """
            QLabel {
                border: 2px solid #ccc;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }
        """
        )
        self.set_status(ConnectionStatus.DISCONNECTED)

    def set_status(self, status: ConnectionStatus):
        """Update the visual status."""
        if status == ConnectionStatus.CONNECTED:
            color = "#4CAF50"  # Green
            text_color = "white"
            text = "CONNECTED"
        elif status == ConnectionStatus.RUNNING:
            color = "#2196F3"  # Blue
            text_color = "white"
            text = "RUNNING"
        elif status == ConnectionStatus.STARTING:
            color = "#FF9800"  # Orange
            text_color = "white"
            text = "STARTING"
        elif status == ConnectionStatus.CONNECTING:
            color = "#FF9800"  # Orange
            text_color = "white"
            text = "CONNECTING"
        elif status == ConnectionStatus.STOPPING:
            color = "#9E9E9E"  # Grey
            text_color = "white"
            text = "STOPPING"
        elif status == ConnectionStatus.STOPPED:
            color = "#757575"  # Dark Grey
            text_color = "white"
            text = "STOPPED"
        elif status == ConnectionStatus.ERROR:
            color = "#F44336"  # Red
            text_color = "white"
            text = "ERROR"
        else:  # DISCONNECTED
            color = "#E0E0E0"  # Light Grey
            text_color = "black"
            text = "DISCONNECTED"

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                color: {text_color};
                border: 2px solid #ccc;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }}
        """
        )
        self.setText(f"{self.name.title()}\n{text}")


class LedIndicator(QLabel):
    """Small circular LED indicator for on/off states."""

    def __init__(self, diameter: int = 14):
        super().__init__()
        self._diameter = diameter
        self.setFixedSize(diameter + 4, diameter + 4)
        self.set_off()

    def _set_color(self, color: str):
        d = self._diameter
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                border-radius: {d // 2 + 2}px;
                border: 1px solid #444;
            }}
        """
        )
        self.setText("")

    def set_on(self):
        self._set_color("#2ECC71")  # green

    def set_off(self):
        self._set_color("#CCCCCC")  # grey

    def set_error(self):
        self._set_color("#E74C3C")  # red


class LogViewer(QTextEdit):
    """Log viewer widget with auto-scroll."""

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.max_lines = 1000
        self.line_count = 0

        # Setup font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.setFont(font)

        # Setup colors
        self.setStyleSheet(
            """
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #555;
                selection-background-color: #404040;
            }
        """
        )

    def add_log_entry(self, level: str, message: str, timestamp: float):
        """Add a log entry with proper formatting."""
        dt = datetime.fromtimestamp(timestamp)
        time_str = dt.strftime("%H:%M:%S")

        # Color based on log level
        if level == "DEBUG":
            color = "#808080"  # Grey
        elif level == "INFO":
            color = "#00FF00"  # Green
        elif level == "WARNING":
            color = "#FFFF00"  # Yellow
        elif level == "ERROR":
            color = "#FF0000"  # Red
        elif level == "CRITICAL":
            color = "#FF00FF"  # Magenta
        else:
            color = "#FFFFFF"  # White

        html_message = (
            f'<span style="color: {color};">[{time_str}] {level}: {message}</span><br>'
        )

        # Check if we need to remove old lines
        if self.line_count >= self.max_lines:
            # Remove first few lines to keep under limit
            cursor = self.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 100)  # Remove 100 lines
            cursor.removeSelectedText()
            self.line_count -= 100

        # Add to text edit
        self.moveCursor(self.textCursor().End)
        self.insertHtml(html_message)
        self.ensureCursorVisible()
        self.line_count += 1


class ElyseDataThread(QThread):
    """Thread handling ELYSE ZMQ data (legacy-compatible)."""

    data_signal = pyqtSignal(str)

    def __init__(self, zmq_address: str = "tcp://129.175.100.128:6050"):
        super().__init__()
        self.zmq_address = zmq_address
        self.running = False

    def run(self):
        context = None
        socket = None
        try:
            context = zmq.Context()
            socket = context.socket(zmq.PULL)
            # Proper cleanup options
            socket.setsockopt(zmq.LINGER, 1000)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            try:
                socket.bind(self.zmq_address)
            except zmq.ZMQError:
                # Fallback to local
                alt = "tcp://127.0.0.1:6051"
                try:
                    socket.bind(alt)
                    self.zmq_address = alt
                except zmq.ZMQError:
                    return
            self.running = True
            while self.running:
                try:
                    msg = socket.recv_string(flags=0)
                    if self.running:
                        self.data_signal.emit(msg)
                except zmq.Again:
                    continue
                except zmq.ZMQError as e:
                    if e.errno == zmq.ETERM:
                        break
                except Exception:
                    self.msleep(100)
        finally:
            try:
                if socket:
                    socket.close()
            except Exception:
                pass
            try:
                if context:
                    context.term()
            except Exception:
                pass

    def stop(self):
        self.running = False


class PyConlyseMainWindow(QMainWindow):
    """Main PyConlyse GUI window - starts immediately, connects asynchronously."""

    def __init__(self):
        super().__init__()

        # Initialize attributes early
        self.logger_manager = None  # Defer logging setup for speed
        self.bin_path = main_app_path.parent / "bin"
        self.async_manager = None
        self.status_indicators = {}
        self._ui_ready = False
        self._deferred_started = False

        # Legacy ELYSE control (ZMQ-driven) state
        self.elyse_tabs = None
        self._elyse_tabs_widgets: Dict[str, QWidget] = {}
        self._elyse_layouts: Dict[str, QVBoxLayout] = {}
        self._elyse_elements: Dict[str, QWidget] = {}
        self._elyse_primary = True  # avoid sending on first value change
        self._elyse_thread: ElyseDataThread | None = None

        # ZMQ push socket for sending ELYSE changes
        self._zmq_context = None
        self._zmq_push = None

        # Device Clients tab state
        self._clients_tab = None
        self._clients_sections = {}
        self._client_devices_map: Dict[str, list] = {}
        self._client_vis = getattr(DSVisType, "FULL", None)
        self._launched_widgets = []

        # Create thread-safe signals
        self.signals = ThreadSafeSignals()
        self.signals.log_message.connect(self.on_log_message_safe)
        self.signals.status_update.connect(self.on_status_update_safe)

        # Build a minimal UI immediately for fastest show
        self.build_minimal_ui()

        # Defer heavy initialization until after the first event loop tick
        QTimer.singleShot(0, self.deferred_startup)

    _main_window_methods_build_minimal_ui = _bind_main_window_methods_build_minimal_ui(_refactor_modules[__name__])
    build_minimal_ui = _main_window_methods_build_minimal_ui["build_minimal_ui"]

    setup_ui = _main_window_methods_build_minimal_ui["setup_ui"]

    create_menu_bar = _main_window_methods_build_minimal_ui["create_menu_bar"]

    create_left_panel = _main_window_methods_build_minimal_ui["create_left_panel"]

    create_overview_tab = _main_window_methods_build_minimal_ui["create_overview_tab"]

    open_experiment_preparation = _main_window_methods_build_minimal_ui["open_experiment_preparation"]

    create_devices_tab = _main_window_methods_build_minimal_ui["create_devices_tab"]

    create_device_clients_tab = _main_window_methods_build_minimal_ui["create_device_clients_tab"]

    _set_client_vis = _main_window_methods_build_minimal_ui["_set_client_vis"]

    _client_configs = _main_window_methods_build_minimal_ui["_client_configs"]

    _build_client_sections = _main_window_methods_build_minimal_ui["_build_client_sections"]

    refresh_device_clients_list_async = _main_window_methods_build_minimal_ui["refresh_device_clients_list_async"]

    _apply_clients_device_map = _main_window_methods_build_minimal_ui["_apply_clients_device_map"]

    _open_selected_client = _main_window_methods_build_minimal_ui["_open_selected_client"]

    create_deviceservers_tab = _main_window_methods_build_minimal_ui["create_deviceservers_tab"]
    del _main_window_methods_build_minimal_ui

    _main_window_methods_create_right_panel = _bind_main_window_methods_create_right_panel(_refactor_modules[__name__])
    create_right_panel = _main_window_methods_create_right_panel["create_right_panel"]

    create_status_bar = _main_window_methods_create_right_panel["create_status_bar"]

    initialize_async_manager = _main_window_methods_create_right_panel["initialize_async_manager"]

    setup_timers = _main_window_methods_create_right_panel["setup_timers"]

    on_status_update = _main_window_methods_create_right_panel["on_status_update"]
        # Updates are processed by the timer to avoid threading issues

    thread_safe_log_callback = _main_window_methods_create_right_panel["thread_safe_log_callback"]

    thread_safe_status_callback = _main_window_methods_create_right_panel["thread_safe_status_callback"]

    @pyqtSlot(str, str, float)
    def on_log_message_safe(self, level: str, message: str, timestamp: float):
        """Handle log message for GUI display (called from main thread)."""
        if not getattr(self, "_ui_ready", False) or not hasattr(self, "log_viewer"):
            return
        self.log_viewer.add_log_entry(level, message, timestamp)

    @pyqtSlot(str, str, str)
    def on_status_update_safe(self, component: str, status: str, message: str):
        """Handle status update for GUI display (called from main thread)."""
        # Update status indicator if it exists
        if component in self.status_indicators:
            try:
                from main_app.core.async_manager import ConnectionStatus

                status_enum = ConnectionStatus(status)
                self.status_indicators[component].set_status(status_enum)
            except ValueError:
                # If status string doesn't match enum, skip visual update
                status_enum = None
        else:
            status_enum = None

        # Update DB LED based on connectivity
        if component == "tango_connectivity" and hasattr(self, "db_led"):
            s = (status or "").lower()
            if "connected" in s or "running" in s:
                self.db_led.set_on()
                # Optional: refresh starters and DS status on first connect
                try:
                    self.refresh_starters()
                    self.update_deviceservers_status()
                    self.update_db_devices_status_async()
                except Exception:
                    pass
            elif "error" in s:
                self.db_led.set_error()
            else:
                self.db_led.set_off()

        # Update status bar
        if component == "system":
            self.statusBar.showMessage(message)
        elif "error" in (status or "").lower():
            self.statusBar.showMessage(f"Error: {message}")

    process_status_updates = _main_window_methods_create_right_panel["process_status_updates"]

    update_gui_state = _main_window_methods_create_right_panel["update_gui_state"]

    start_infrastructure = _main_window_methods_create_right_panel["start_infrastructure"]

    stop_infrastructure = _main_window_methods_create_right_panel["stop_infrastructure"]

    start_device_server = _main_window_methods_create_right_panel["start_device_server"]

    start_all_devices = _main_window_methods_create_right_panel["start_all_devices"]

    clear_logs = _main_window_methods_create_right_panel["clear_logs"]

    # ===== Legacy-inspired ELYSE control integration =====
    create_elyse_control_tab = _main_window_methods_create_right_panel["create_elyse_control_tab"]

    _ensure_zmq_push = _main_window_methods_create_right_panel["_ensure_zmq_push"]

    start_elyse_control = _main_window_methods_create_right_panel["start_elyse_control"]

    update_elyse_ui = _main_window_methods_create_right_panel["update_elyse_ui"]

    _add_elyse_tab = _main_window_methods_create_right_panel["_add_elyse_tab"]

    _add_elyse_element = _main_window_methods_create_right_panel["_add_elyse_element"]

    _update_elyse_element = _main_window_methods_create_right_panel["_update_elyse_element"]

    _change_elyse_sb_value = _main_window_methods_create_right_panel["_change_elyse_sb_value"]

    # ===== Legacy-inspired Map integration =====
    show_system_map = _main_window_methods_create_right_panel["show_system_map"]

    save_logs = _main_window_methods_create_right_panel["save_logs"]

    stop_all_running_devices = _main_window_methods_create_right_panel["stop_all_running_devices"]

    refresh_starters = _main_window_methods_create_right_panel["refresh_starters"]

    refresh_db_devices_list_async = _main_window_methods_create_right_panel["refresh_db_devices_list_async"]

    _rebuild_db_devices_list = _main_window_methods_create_right_panel["_rebuild_db_devices_list"]
    del _main_window_methods_create_right_panel

    _main_window_methods_update_db_devices_status_async = _bind_main_window_methods_update_db_devices_status_async(_refactor_modules[__name__])
    update_db_devices_status_async = _main_window_methods_update_db_devices_status_async["update_db_devices_status_async"]

    open_device_widget_for_name = _main_window_methods_update_db_devices_status_async["open_device_widget_for_name"]

    rebuild_deviceservers_list = _main_window_methods_update_db_devices_status_async["rebuild_deviceservers_list"]

    on_refresh_deviceservers_clicked = _main_window_methods_update_db_devices_status_async["on_refresh_deviceservers_clicked"]

    update_deviceservers_status = _main_window_methods_update_db_devices_status_async["update_deviceservers_status"]

    stop_device_server = _main_window_methods_update_db_devices_status_async["stop_device_server"]

    open_device_client = _main_window_methods_update_db_devices_status_async["open_device_client"]

    show_about = _main_window_methods_update_db_devices_status_async["show_about"]

    closeEvent = _main_window_methods_update_db_devices_status_async["closeEvent"]

    deferred_startup = _main_window_methods_update_db_devices_status_async["deferred_startup"]
    del _main_window_methods_update_db_devices_status_async


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("PyConlyse")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("PyConlyse Team")

    # Create and show main window as soon as possible
    window = PyConlyseMainWindow()
    window.show()

    # Do not log here; defer logging to deferred_startup for speed
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
