#!/usr/bin/env python3
"""PyConlyse Main GUI Window

Non-blocking GUI that starts immediately and handles all connections asynchronously.
"""

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

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
    QSpacerItem,
    QSizePolicy,
    QComboBox,
)

# Add parent directory to path for imports
main_app_path = Path(__file__).parent.parent
sys.path.insert(0, str(main_app_path.parent))

from main_app.core.async_manager import (
    ConnectionStatus,
    StatusUpdate,
)
from main_app.core.config import OFFLINE_MODE
from main_app.core.logging_config import setup_pyconlyse_logging

# Additional third-party libs used for legacy features
import zmq
import imageio
import numpy as np
import pyqtgraph as pg

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

    def build_minimal_ui(self):
        """Build a minimal window to appear instantly."""
        self.setWindowTitle("PyConlyse v2.0 - Control System (Starting...)")
        self.setGeometry(100, 100, 900, 600)

        # Minimal central widget
        minimal = QWidget()
        vbox = QVBoxLayout(minimal)
        label = QLabel("Starting PyConlyse... Initializing components in background.")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px; padding: 20px;")
        vbox.addStretch(1)
        vbox.addWidget(label)
        vbox.addStretch(1)
        self.setCentralWidget(minimal)

        # Minimal status bar
        self.create_status_bar()
        self.statusBar.showMessage("Starting... GUI ready; loading subsystems...")

    def setup_ui(self):
        """Setup the full user interface (deferred)."""
        self.setWindowTitle("PyConlyse v2.0 - Control System")

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar
        self.create_menu_bar()

        # Create main content area
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Controls and Status
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel - Logs
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([800, 400])

        logger.info("GUI setup completed")
        self._ui_ready = True

    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Infrastructure menu
        infra_menu = menubar.addMenu("&Infrastructure")

        start_infra_action = QAction("&Start Infrastructure", self)
        start_infra_action.triggered.connect(self.start_infrastructure)
        infra_menu.addAction(start_infra_action)

        stop_infra_action = QAction("S&top Infrastructure", self)
        stop_infra_action.triggered.connect(self.stop_infrastructure)
        infra_menu.addAction(stop_infra_action)

        # Device menu
        device_menu = menubar.addMenu("&Devices")

        start_all_action = QAction("Start &All Devices", self)
        start_all_action.triggered.connect(self.start_all_devices)
        device_menu.addAction(start_all_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_left_panel(self) -> QWidget:
        """Create the left control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Create management tabs
        self.management_tabs = QTabWidget()
        overview_tab = self.create_overview_tab()
        devices_tab = self.create_devices_tab()
        device_clients_tab = self.create_device_clients_tab()
        deviceservers_tab = self.create_deviceservers_tab()
        elyse_tab = self.create_elyse_control_tab()
        self.management_tabs.addTab(overview_tab, "Overview")
        self.management_tabs.addTab(devices_tab, "Devices (DB)")
        self.management_tabs.addTab(device_clients_tab, "Device Clients")
        self.management_tabs.addTab(deviceservers_tab, "DeviceServers")
        self.management_tabs.addTab(elyse_tab, "ELYSE Control")
        layout.addWidget(self.management_tabs)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Stretch
        layout.addStretch()
        return panel

    def create_overview_tab(self) -> QWidget:
        """Create the Overview tab: status, DB LED, starters, infra & quick device controls."""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Status indicators group
        status_group = QGroupBox("System Status")
        status_layout = QGridLayout(status_group)

        # Indicators
        self.status_indicators = {
            "system": StatusIndicator("System"),
            "database": StatusIndicator("Database"),
            "starter": StatusIndicator("Starter"),
            "tango_connectivity": StatusIndicator("Connectivity"),
        }

        row = 0
        for name, indicator in self.status_indicators.items():
            status_layout.addWidget(QLabel(f"{name.title()}:"), row, 0)
            status_layout.addWidget(indicator, row, 1)
            row += 1

        # DB LED row (tango_connectivity)
        db_led_row = QHBoxLayout()
        db_led_row.addWidget(QLabel("DB LED:"))
        self.db_led = LedIndicator()
        db_led_row.addWidget(self.db_led)
        db_led_row.addStretch()
        status_layout.addLayout(db_led_row, row, 0, 1, 2)

        v.addWidget(status_group)

        # Starters group
        starters_group = QGroupBox("Starters")
        starters_v = QVBoxLayout(starters_group)
        btn_row = QHBoxLayout()
        self.btn_refresh_starters = QPushButton("Refresh Starters")
        self.btn_refresh_starters.clicked.connect(self.refresh_starters)
        btn_row.addWidget(self.btn_refresh_starters)
        btn_row.addStretch()
        starters_v.addLayout(btn_row)

        self.starters_scroll = QScrollArea()
        self.starters_scroll.setWidgetResizable(True)
        self.starters_widget = QWidget()
        self.starters_layout = QVBoxLayout(self.starters_widget)
        self.starters_layout.addStretch()  # keep stretch at end
        self.starters_scroll.setWidget(self.starters_widget)
        starters_v.addWidget(self.starters_scroll)
        v.addWidget(starters_group)

        # Infrastructure controls
        infra_group = QGroupBox("Infrastructure Control")
        infra_layout = QVBoxLayout(infra_group)

        self.start_infra_btn = QPushButton("🚀 Start Infrastructure")
        self.start_infra_btn.clicked.connect(self.start_infrastructure)
        self.start_infra_btn.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 10px; }"
        )
        infra_layout.addWidget(self.start_infra_btn)

        self.stop_infra_btn = QPushButton("🛑 Stop Infrastructure")
        self.stop_infra_btn.clicked.connect(self.stop_infrastructure)
        self.stop_infra_btn.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 10px; }"
        )
        self.stop_infra_btn.setEnabled(False)
        infra_layout.addWidget(self.stop_infra_btn)
        v.addWidget(infra_group)

        # Quick Device controls
        device_group = QGroupBox("Quick Device Server Control")
        device_layout = QVBoxLayout(device_group)

        self.start_basler_btn = QPushButton("📷 Start BASLER Camera")
        self.start_basler_btn.clicked.connect(
            lambda: self.start_device_server("BASLER", "V0")
        )
        device_layout.addWidget(self.start_basler_btn)

        self.start_standa_btn = QPushButton("🔧 Start STANDA Stage")
        self.start_standa_btn.clicked.connect(
            lambda: self.start_device_server("STANDA", "V0")
        )
        device_layout.addWidget(self.start_standa_btn)

        self.start_all_btn = QPushButton("🚀 Start All Devices")
        self.start_all_btn.clicked.connect(self.start_all_devices)
        self.start_all_btn.setStyleSheet(
            "QPushButton { font-size: 12px; padding: 8px; background-color: #4CAF50; color: white; }"
        )
        device_layout.addWidget(self.start_all_btn)
        v.addWidget(device_group)

        v.addStretch()
        return tab

    def create_devices_tab(self) -> QWidget:
        """Create the DB devices tab that lists all devices from the Tango DB and allows opening control widgets."""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Controls
        ctrl = QHBoxLayout()
        self.btn_refresh_db_devices = QPushButton("Refresh Devices (DB)")
        self.btn_refresh_db_devices.clicked.connect(self.refresh_db_devices_list_async)
        ctrl.addWidget(self.btn_refresh_db_devices)

        self.btn_refresh_db_status = QPushButton("Refresh States")
        self.btn_refresh_db_status.clicked.connect(self.update_db_devices_status_async)
        ctrl.addWidget(self.btn_refresh_db_status)

        # Legacy map button
        self.btn_show_map = QPushButton("Show System Map")
        self.btn_show_map.clicked.connect(self.show_system_map)
        ctrl.addWidget(self.btn_show_map)

        ctrl.addStretch()
        v.addLayout(ctrl)

        # Scroll area with device rows
        self.db_devices_scroll = QScrollArea()
        self.db_devices_scroll.setWidgetResizable(True)
        self.db_devices_container = QWidget()
        self.db_devices_layout = QVBoxLayout(self.db_devices_container)
        self.db_devices_layout.addStretch()
        self.db_devices_scroll.setWidget(self.db_devices_container)
        v.addWidget(self.db_devices_scroll)

        # Map: device_name -> (led, state_label, open_btn)
        self.db_devices_widgets: Dict[str, tuple] = {}

        # Initial populate (async, so we do not block UI)
        if not OFFLINE_MODE:
            QTimer.singleShot(0, self.refresh_db_devices_list_async)

        return tab

    def create_device_clients_tab(self) -> QWidget:
        """Create a GUI similar to legacy to open control widgets for DS by type."""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Visualization type selection (if DSVisType available)
        if DSVisType is not None:
            vis_group = QGroupBox("Visualization Type")
            vis_layout = QHBoxLayout()
            for vt in DSVisType:
                rb = QPushButton(vt.value)
                rb.setCheckable(True)
                if vt == DSVisType.FULL:
                    rb.setChecked(True)
                def _mk_setter(val):
                    return lambda: self._set_client_vis(val)
                rb.clicked.connect(_mk_setter(vt))
                vis_layout.addWidget(rb)
            vis_layout.addStretch()
            vis_group.setLayout(vis_layout)
            v.addWidget(vis_group)

        # Controls row
        ctrl = QHBoxLayout()
        self.btn_refresh_clients = QPushButton("Refresh Device Lists")
        self.btn_refresh_clients.clicked.connect(self.refresh_device_clients_list_async)
        ctrl.addWidget(self.btn_refresh_clients)
        ctrl.addStretch()
        v.addLayout(ctrl)

        # Scroll area
        self.clients_scroll = QScrollArea()
        self.clients_scroll.setWidgetResizable(True)
        self._clients_tab = QWidget()
        self._clients_tab_layout = QVBoxLayout(self._clients_tab)
        self._clients_tab_layout.addStretch()
        self.clients_scroll.setWidget(self._clients_tab)
        v.addWidget(self.clients_scroll)

        # Build sections
        self._build_client_sections()

        # Initial populate
        QTimer.singleShot(0, self.refresh_device_clients_list_async)

        return tab

    def _set_client_vis(self, val):
        try:
            self._client_vis = val
        except Exception:
            self._client_vis = getattr(DSVisType, "FULL", None)

    def _client_configs(self):
        """Return list of client configurations: (key, display, keywords, launcher_fn_name, icon)."""
        return [
            ("NETIO", "NETIO", ["netio"], "start_netio_widget", "icons/NETIO.png"),
            ("OWIS", "OWIS", ["owis", "delay"], "start_owis_widget", "icons/OWIS.png"),
            ("STANDA", "STANDA", ["standa"], "start_standa_widget", "icons/STANDA.svg"),
            ("TOPDIRECT", "TOPDIRECT", ["topdirect"], "start_topdirect_widget", "icons/TopDirect.svg"),
            ("BASLER", "BASLER", ["basler", "camera"], "start_basler_widget", "icons/basler_camera.svg"),
            ("LASER_POINTING", "Laser Pointing", ["laser"], "start_laser_pointing_widget", "icons/laser_pointing.svg"),
        ]

    def _build_client_sections(self):
        # Clear existing (except stretch)
        try:
            while self._clients_tab_layout.count() > 1:
                item = self._clients_tab_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass
        self._clients_sections = {}

        from PyQt5.QtGui import QIcon

        for key, display, _keywords, _launcher, icon in self._client_configs():
            row = QHBoxLayout()
            btn = QPushButton(display)
            try:
                btn.setIcon(QIcon(icon))
            except Exception:
                pass
            combo = QComboBox()
            combo.addItem("(loading...)")
            open_btn = QPushButton("Open")
            open_btn.clicked.connect(lambda _, k=key: self._open_selected_client(k))

            row.addWidget(btn)
            row.addWidget(combo)
            row.addWidget(open_btn)
            row.addStretch()
            cont = QWidget()
            cont.setLayout(row)
            self._clients_tab_layout.insertWidget(self._clients_tab_layout.count() - 1, cont)
            self._clients_sections[key] = {"container": cont, "combo": combo}

    def refresh_device_clients_list_async(self):
        """Fetch exported devices and categorize by DS keywords in background."""
        from main_app.core.config import OFFLINE_MODE
        if OFFLINE_MODE:
            # Offline placeholders
            categorized = {key: [] for key, *_ in self._client_configs()}
            self._apply_clients_device_map(categorized)
            return
        try:
            import concurrent.futures
            from tango import Database
        except Exception:
            categorized = {key: [] for key, *_ in self._client_configs()}
            self._apply_clients_device_map(categorized)
            return

        def _fetch():
            try:
                db = Database()
                names = []
                for prefix in ("ELYSE", "manip"):
                    try:
                        names.extend(list(db.get_device_exported(f"{prefix}*")))
                    except Exception:
                        continue
                # Categorize by keywords
                out = {key: [] for key, *_ in self._client_configs()}
                lower_names = [(n, n.lower()) for n in set(names)]
                for key, _display, keywords, _launcher, _icon in self._client_configs():
                    for n, ln in lower_names:
                        if any(kw in ln for kw in keywords):
                            out[key].append(n)
                # Sort
                for k in out:
                    out[k] = sorted(out[k])
                return out
            except Exception:
                return {key: [] for key, *_ in self._client_configs()}

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_fetch)

        def _done(_f):
            try:
                categorized = _f.result(timeout=0) or {}
            except Exception:
                categorized = {key: [] for key, *_ in self._client_configs()}
            QTimer.singleShot(0, lambda d=categorized: self._apply_clients_device_map(d))
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    def _apply_clients_device_map(self, categorized: Dict[str, list]):
        self._client_devices_map = categorized or {}
        for key, data in self._clients_sections.items():
            combo = data["combo"]
            combo.clear()
            items = self._client_devices_map.get(key) or []
            if not items:
                combo.addItem("(none found)")
                combo.setEnabled(False)
            else:
                combo.addItems(items)
                combo.setEnabled(True)

    def _open_selected_client(self, key: str):
        data = self._clients_sections.get(key)
        if not data:
            return
        combo = data["combo"]
        if combo.count() == 0 or not combo.isEnabled():
            return
        device_name = combo.currentText()
        try:
            from main_app.ui import widget_launchers as wl
            # Map key -> launcher function
            fn_map = {
                "NETIO": wl.start_netio_widget,
                "OWIS": wl.start_owis_widget,
                "STANDA": wl.start_standa_widget,
                "TOPDIRECT": wl.start_topdirect_widget,
                "BASLER": wl.start_basler_widget,
                "LASER_POINTING": wl.start_laser_pointing_widget,
            }
            vis = self._client_vis.value if hasattr(self._client_vis, "value") else "FULL"
            # Launch
            w = None
            if key in ("NETIO", "LASER_POINTING", "BASLER", "STANDA", "TOPDIRECT"):
                w = fn_map[key](device_name, parent=None, vis=vis)
            elif key == "OWIS":
                # OWIS may auto-detect axes if not provided
                w = fn_map[key](device_name, axes=None, parent=None, vis=vis)
            if w is not None:
                self._launched_widgets.append(w)
        except Exception as e:
            QMessageBox.critical(self, "Client", f"Failed to open widget for {key}: {e}")

    def create_deviceservers_tab(self) -> QWidget:
        """Create the DeviceServers management tab"""
        tab = QWidget()
        v = QVBoxLayout(tab)

        # Controls row
        ctrl = QHBoxLayout()
        self.btn_refresh_ds = QPushButton("Refresh List")
        self.btn_refresh_ds.clicked.connect(self.on_refresh_deviceservers_clicked)
        ctrl.addWidget(self.btn_refresh_ds)

        self.btn_refresh_ds_status = QPushButton("Refresh Status")
        self.btn_refresh_ds_status.clicked.connect(self.update_deviceservers_status)
        ctrl.addWidget(self.btn_refresh_ds_status)

        self.btn_start_all_servers = QPushButton("Start All Configured")
        self.btn_start_all_servers.clicked.connect(self.start_all_devices)
        ctrl.addWidget(self.btn_start_all_servers)
        self.btn_stop_all_servers = QPushButton("Stop All Running")
        self.btn_stop_all_servers.clicked.connect(self.stop_all_running_devices)
        ctrl.addWidget(self.btn_stop_all_servers)
        ctrl.addStretch()
        v.addLayout(ctrl)

        # Scroll list
        self.ds_scroll = QScrollArea()
        self.ds_scroll.setWidgetResizable(True)
        self.ds_list_container = QWidget()
        self.ds_list_layout = QVBoxLayout(self.ds_list_container)
        self.ds_list_layout.addStretch()
        self.ds_scroll.setWidget(self.ds_list_container)
        v.addWidget(self.ds_scroll)

        # Map of ds key -> (led,label)
        self.ds_status_widgets: Dict[str, tuple] = {}

        # Initial build (defer to avoid UI blocking)
        QTimer.singleShot(0, self.rebuild_deviceservers_list)
        QTimer.singleShot(500, self.update_deviceservers_status)

        return tab

    def create_right_panel(self) -> QWidget:
        """Create the right log panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Log viewer
        log_label = QLabel("System Logs")
        log_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(log_label)

        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer)

        # Log controls
        log_controls = QHBoxLayout()

        clear_logs_btn = QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(self.clear_logs)
        log_controls.addWidget(clear_logs_btn)

        save_logs_btn = QPushButton("Save Logs")
        save_logs_btn.clicked.connect(self.save_logs)
        log_controls.addWidget(save_logs_btn)

        log_controls.addStretch()
        layout.addLayout(log_controls)

        return panel

    def create_status_bar(self):
        """Create the status bar."""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

    def initialize_async_manager(self):
        """Initialize the async connection manager."""
        try:
            # Import here to avoid any heavy imports before GUI shows
            from main_app.core.async_manager import AsyncConnectionManager

            self.async_manager = AsyncConnectionManager(self.bin_path)
            self.async_manager.add_status_callback(self.thread_safe_status_callback)

            # Setup GUI log callback (thread-safe)
            if self.logger_manager:
                self.logger_manager.set_gui_callback(self.thread_safe_log_callback)

            # Start background initialization
            self.async_manager.start_background_initialization()

            logger.info("Async connection manager initialized")
            self.statusBar.showMessage("Background initialization in progress...")

        except Exception as e:
            logger.error(f"Failed to initialize async manager: {e}")
            QMessageBox.critical(
                self,
                "Initialization Error",
                f"Failed to initialize connection manager:\n{e}",
            )

    def setup_timers(self):
        """Setup GUI update timers with reduced frequency to prevent blocking."""
        # Timer for processing status updates (less frequent)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.process_status_updates)
        self.status_timer.start(500)

        # Timer for GUI updates (less frequent)
        self.gui_timer = QTimer(self)
        self.gui_timer.timeout.connect(self.update_gui_state)
        self.gui_timer.start(2000)

    def on_status_update(self, update: StatusUpdate):
        """Handle status update from async manager."""
        # Updates are processed by the timer to avoid threading issues

    def thread_safe_log_callback(self, level: str, message: str, timestamp: float):
        """Thread-safe callback for log messages from background threads."""
        # Emit signal to main thread
        self.signals.log_message.emit(level, message, timestamp)

    def thread_safe_status_callback(self, update):
        """Thread-safe callback for status updates from background threads."""
        from main_app.core.async_manager import StatusUpdate

        if isinstance(update, StatusUpdate):
            # Emit signal to main thread
            self.signals.status_update.emit(
                update.component, update.status.value, update.message
            )

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

    def process_status_updates(self):
        """Process all pending status updates (minimal processing to avoid blocking)."""
        if not self.async_manager:
            return

        # Process only a few updates at a time to avoid blocking
        for _ in range(3):
            update = self.async_manager.get_status_update()
            if update is None:
                break
            # Emit thread-safe signal
            self.signals.status_update.emit(
                update.component, update.status.value, update.message
            )

    def update_gui_state(self):
        """Update GUI button states based on current status."""
        if not self.async_manager or not getattr(self, "_ui_ready", False):
            return

        status = self.async_manager.get_current_status()
        managers_ready = self.async_manager.is_managers_ready()

        # Update infrastructure buttons
        can_start_infra = (
            managers_ready
            and status.get("database", ConnectionStatus.DISCONNECTED)
            != ConnectionStatus.RUNNING
        )
        can_stop_infra = (
            managers_ready
            and status.get("database", ConnectionStatus.DISCONNECTED)
            == ConnectionStatus.RUNNING
        )

        self.start_infra_btn.setEnabled(can_start_infra)
        self.stop_infra_btn.setEnabled(can_stop_infra)

        # Update device buttons
        self.start_basler_btn.setEnabled(managers_ready)
        self.start_standa_btn.setEnabled(managers_ready)
        self.start_all_btn.setEnabled(managers_ready)

        # Update status bar if system is ready
        if managers_ready and not hasattr(self, "_system_ready_shown"):
            self.statusBar.showMessage("System ready - all components initialized")
            self._system_ready_shown = True

    def start_infrastructure(self):
        """Start Tango infrastructure."""
        if self.async_manager and self.async_manager.is_managers_ready():
            success = self.async_manager.start_infrastructure_async()
            if success:
                self.statusBar.showMessage("Starting infrastructure in background...")
                logger.info("Infrastructure startup initiated")
            else:
                QMessageBox.warning(
                    self, "Warning", "Infrastructure startup already in progress"
                )
        else:
            QMessageBox.warning(
                self,
                "Warning",
                "System not ready yet. Please wait for initialization to complete.",
            )

    def stop_infrastructure(self):
        """Stop Tango infrastructure."""
        if self.async_manager and self.async_manager.is_managers_ready():
            success = self.async_manager.stop_infrastructure_async()
            if success:
                self.statusBar.showMessage("Stopping infrastructure...")
                logger.info("Infrastructure stop initiated")
            else:
                QMessageBox.warning(
                    self, "Warning", "Infrastructure stop already in progress"
                )

    def start_device_server(self, device_type: str, instance: str):
        """Start a specific device server."""
        if self.async_manager and self.async_manager.is_managers_ready():
            success = self.async_manager.start_device_server_async(
                device_type, instance
            )
            if success:
                self.statusBar.showMessage(f"Starting {device_type}/{instance}...")
                logger.info(f"Device server {device_type}/{instance} startup initiated")
            else:
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Device server {device_type}/{instance} startup already in progress",
                )
        else:
            QMessageBox.warning(
                self,
                "Warning",
                "System not ready yet. Please wait for initialization to complete.",
            )

    def start_all_devices(self):
        """Start all configured device servers."""
        if not self.async_manager or not self.async_manager.is_managers_ready():
            QMessageBox.warning(self, "Warning", "System not ready yet.")
            return

        # Start all configured device servers from manager config
        started_count = 0
        if self.async_manager and self.async_manager.device_mgr:
            configs = self.async_manager.device_mgr.get_available_device_types()
            for device_type, cfg in configs.items():
                for instance in cfg.get("instances", []):
                    success = self.async_manager.start_device_server_async(
                        device_type, instance
                    )
                    if success:
                        started_count += 1

        if started_count > 0:
            self.statusBar.showMessage(f"Starting {started_count} device servers...")
            logger.info(
                f"Batch device server startup initiated for {started_count} devices"
            )
        else:
            QMessageBox.information(
                self, "Info", "No device servers were started (may already be running)"
            )

    def clear_logs(self):
        """Clear the log viewer."""
        self.log_viewer.clear()
        logger.info("Log viewer cleared")

    # ===== Legacy-inspired ELYSE control integration =====
    def create_elyse_control_tab(self) -> QWidget:
        """Create ELYSE control tab with dynamic sub-tabs populated from ZMQ messages."""
        tab = QWidget()
        v = QVBoxLayout(tab)
        self.elyse_tabs = QTabWidget()
        v.addWidget(self.elyse_tabs)
        return tab

    def _ensure_zmq_push(self):
        if self._zmq_push is None:
            try:
                self._zmq_context = zmq.Context()
                self._zmq_push = self._zmq_context.socket(zmq.PUSH)
                self._zmq_push.connect("tcp://127.0.0.1:5556")
            except Exception:
                self._zmq_push = None

    def start_elyse_control(self):
        """Start ELYSE ZMQ thread and handlers."""
        if self._elyse_thread is not None:
            return
        try:
            self._elyse_thread = ElyseDataThread()
            self._elyse_thread.data_signal.connect(self.update_elyse_ui)
            self._elyse_thread.start()
            self._ensure_zmq_push()
            logger.info("ELYSE control thread started")
        except Exception as e:
            logger.warning(f"Failed to start ELYSE thread: {e}")
            self._elyse_thread = None

    def update_elyse_ui(self, message: str):
        """Handle incoming ELYSE ZMQ messages and update UI accordingly."""
        try:
            msg = eval(message)
        except Exception:
            return
        for card in msg:
            for elem in card:
                parts = str(elem).split('/')
                if len(parts) <= 3:
                    continue
                tab_name = '/'.join(parts[0:2])
                elem_name = '/'.join(parts[-3:-1])
                key_label = f"tab_{tab_name}_label_{elem_name}"
                if f"tab_{tab_name}" not in self._elyse_tabs_widgets:
                    self._add_elyse_tab(tab_name)
                if key_label not in self._elyse_elements:
                    self._add_elyse_element(elem_name, tab_name, elem)
                else:
                    self._update_elyse_element(tab_name, elem_name, elem)

    def _add_elyse_tab(self, name: str):
        w = QWidget()
        layout = QVBoxLayout()
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(w)
        w.setLayout(layout)
        self.elyse_tabs.addTab(scroll, name)
        self._elyse_tabs_widgets[f"tab_{name}"] = w
        self._elyse_layouts[f"layout_{name}"] = layout

    def _add_elyse_element(self, element_name: str, tab_name: str, element_value: str):
        parts = str(element_value).split('/')
        if len(parts) > 3:
            label = QLabel()
            text = '/'.join(parts[-3:])
            try:
                val = float(parts[-1])
            except Exception:
                val = 0.0
            sb = QDoubleSpinBox()
            sb.setDecimals(6)
            sb.setRange(-1e9, 1e9)
            sb.setValue(val)
            sb.valueChanged.connect(lambda _v, t=tab_name, e=element_name: self._change_elyse_sb_value(t, e))
            label.setText(text)
            elem_key_label = f"tab_{tab_name}_label_{element_name}"
            elem_key_sb = f"tab_{tab_name}_sb_{element_name}"
            self._elyse_elements[elem_key_label] = label
            self._elyse_elements[elem_key_sb] = sb
            layout: QVBoxLayout = self._elyse_layouts.get(f"layout_{tab_name}")
            lo_h = QHBoxLayout()
            lo_h.addWidget(label)
            lo_h.addWidget(sb)
            lo_h.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            layout.addLayout(lo_h)

    def _update_elyse_element(self, tab_name: str, elem_name: str, value: str):
        parts = str(value).split('/')
        text = '/'.join(parts[-3:-1])
        label: QLabel = self._elyse_elements.get(f"tab_{tab_name}_label_{elem_name}")
        if label is not None:
            try:
                from decimal import Decimal
                label.setText(f"{text}/{Decimal(parts[-1]):.2E}")
            except Exception:
                label.setText(f"{text}/{parts[-1]}")

    def _change_elyse_sb_value(self, tab_name: str, elem_name: str):
        key = f"tab_{tab_name}_sb_{elem_name}"
        sb: QDoubleSpinBox = self._elyse_elements.get(key)
        if sb is None:
            return
        if self._elyse_primary:
            self._elyse_primary = False
            return
        self._ensure_zmq_push()
        if self._zmq_push is None:
            return
        try:
            val = f"{tab_name}/{elem_name}/{sb.value()}"
            self._zmq_push.send(val.encode('utf-8'))
            logger.info(f"ELYSE set: {val}")
        except Exception:
            pass

    # ===== Legacy-inspired Map integration =====
    def show_system_map(self):
        """Show the system layout map (legacy-style)."""
        try:
            # Prepare window
            map_w = QWidget()
            map_w.setWindowTitle("System Map")
            v = QVBoxLayout(map_w)
            h_image = QHBoxLayout()
            h_label = QHBoxLayout()
            v.addLayout(h_image)
            v.addLayout(h_label)

            glw = pg.GraphicsLayoutWidget()
            vb = glw.addViewBox(row=1, col=1)

            # Use existing icon (uppercase extension in repo)
            icon_path = str((self.bin_path / "icons" / "Main_layout_1200.PNG").resolve())
            im = imageio.imread(icon_path)

            img = pg.ImageItem()
            img.setImage(np.transpose(im, (1, 0, 2)))

            pos_lab = QLabel("Position")
            h_label.addWidget(pos_lab)

            def mouse_moved(lbl, ev):
                pos = ev[0]
                if img.sceneBoundingRect().contains(pos):
                    mp = vb.mapSceneToView(pos)
                    lbl.setText(f"x={mp.x():0.1f}, y={mp.y():0.1f}")

            proxy = pg.SignalProxy(vb.scene().sigMouseMoved, rateLimit=30, slot=lambda *e: mouse_moved(pos_lab, e))
            map_w._proxy = proxy  # keep ref
            vb.addItem(img)
            vb.setAspectLocked(True)
            vb.invertY(True)

            h_image.addWidget(glw)
            map_w.resize(1200, 700)
            map_w.show()

            # Keep reference to prevent GC
            if not hasattr(self, "_map_windows"):
                self._map_windows = []
            self._map_windows.append(map_w)
        except Exception as e:
            QMessageBox.warning(self, "Map", f"Failed to show system map: {e}")

    def save_logs(self):
        """Save logs to file."""
        # TODO: Implement log saving
        QMessageBox.information(self, "Info", "Log saving feature coming soon!")

    def stop_all_running_devices(self):
        """Stop all running device servers."""
        if not self.async_manager or not self.async_manager.is_managers_ready():
            QMessageBox.warning(self, "Warning", "System not ready yet.")
            return
        try:
            count = self.async_manager.device_mgr.stop_all_servers()
            self.statusBar.showMessage(f"Stopped {count} running device servers")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to stop servers: {e}")

    def refresh_starters(self):
        """Refresh the list of Starter devices and their state."""
        # Clear existing items (except final stretch)
        try:
            while self.starters_layout.count() > 1:
                item = self.starters_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass

        try:
            if not self.async_manager or not self.async_manager.infrastructure_mgr:
                row = QHBoxLayout()
                row.addWidget(QLabel("(infrastructure not initialized)"))
                self.starters_layout.insertLayout(0, row)
                return
            starters = self.async_manager.infrastructure_mgr.get_starters_status()
            if not starters:
                row = QHBoxLayout()
                row.addWidget(QLabel("No starters found or DB unavailable"))
                self.starters_layout.insertLayout(0, row)
                return
            for s in starters:
                name = s.get("name", "")
                state = s.get("state", "Unknown")
                row = QHBoxLayout()
                led = LedIndicator(12)
                if str(state).upper() in ("ON", "STANDBY", "MOVING", "RUNNING"):
                    led.set_on()
                elif str(state).upper() in ("OFF",):
                    led.set_off()
                else:
                    led.set_error()
                row.addWidget(led)
                row.addWidget(QLabel(name))
                row.addWidget(QLabel(f"State: {state}"))
                row.addStretch()
                self.starters_layout.insertLayout(self.starters_layout.count() - 1, row)
        except Exception as e:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Error loading starters: {e}"))
            self.starters_layout.insertLayout(0, row)

    def refresh_db_devices_list_async(self):
        """Fetch exported devices in a background thread and then rebuild UI."""
        if OFFLINE_MODE:
            self._rebuild_db_devices_list([])
            return
        try:
            import concurrent.futures

            from tango import Database
        except Exception:
            # If tango not available, clear list
            self._rebuild_db_devices_list([])
            return

        def _fetch():
            try:
                db = Database()
                names = []
                for prefix in ("ELYSE", "manip"):
                    try:
                        names.extend(list(db.get_device_exported(f"{prefix}*")))
                    except Exception:
                        continue
                return sorted(set(names))
            except Exception:
                return []

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_fetch)

        def _done(_fut):
            try:
                devices = _fut.result(timeout=0)
            except Exception:
                devices = []
            # Schedule UI update on main thread
            QTimer.singleShot(
                0,
                lambda d=devices: (
                    self._rebuild_db_devices_list(d),
                    self.update_db_devices_status_async(),
                ),
            )
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    def _rebuild_db_devices_list(self, devices):
        """Rebuild the UI list from provided device names (called on main thread)."""
        # Clear existing rows except final stretch
        try:
            while self.db_devices_layout.count() > 1:
                item = self.db_devices_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass
        self.db_devices_widgets = {}

        for name in devices:
            row = QHBoxLayout()
            led = LedIndicator(12)
            state_lab = QLabel("Unknown")
            state_lab.setMinimumWidth(90)
            row.addWidget(led)
            row.addWidget(QLabel(name))
            row.addWidget(QLabel("State:"))
            row.addWidget(state_lab)
            btn_open = QPushButton("Open GUI")
            btn_open.clicked.connect(
                lambda _, n=name: self.open_device_widget_for_name(n)
            )
            row.addWidget(btn_open)
            row.addStretch()
            container = QWidget()
            container.setLayout(row)
            self.db_devices_layout.insertWidget(
                self.db_devices_layout.count() - 1, container
            )
            self.db_devices_widgets[name] = (led, state_lab, btn_open)

    def update_db_devices_status_async(self):
        """Query device states in background and apply to UI when ready."""
        if OFFLINE_MODE:
            return
        if not getattr(self, "db_devices_widgets", None):
            return
        try:
            import concurrent.futures

            from tango import DeviceProxy
        except Exception:
            return

        names = list(self.db_devices_widgets.keys())

        def _read_all():
            res = {}
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:

                    def read_state(dev_name: str):
                        try:
                            dp = DeviceProxy(dev_name)
                            try:
                                st = dp.state()
                            except Exception:
                                st = dp.State()
                            return dev_name, str(st)
                        except Exception:
                            return dev_name, "Error"

                    futs = [ex.submit(read_state, n) for n in names]
                    for fut in futs:
                        try:
                            dev, state = fut.result(timeout=2.0)
                        except Exception:
                            continue
                        res[dev] = state
            except Exception:
                pass
            return res

        ex2 = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut2 = ex2.submit(_read_all)

        def _done_states(_f):
            try:
                results = _f.result(timeout=0) or {}
            except Exception:
                results = {}

            def apply():
                for dev, (led, lab, _btn) in self.db_devices_widgets.items():
                    state = (results.get(dev) or "Unknown").upper()
                    if state in ("ON", "STANDBY", "MOVING", "RUNNING"):
                        led.set_on()
                    elif state in ("OFF",):
                        led.set_off()
                    elif state in ("ERROR", "FAULT"):
                        led.set_error()
                    else:
                        led.set_off()
                    lab.setText(state.title())

            QTimer.singleShot(0, apply)
            try:
                ex2.shutdown(wait=False)
            except Exception:
                pass

        fut2.add_done_callback(_done_states)

    def open_device_widget_for_name(self, device_name: str):
        """Open the appropriate control widget for a Tango device name using best-effort mapping."""
        try:
            # Try mapping via DeviceServers registry
            try:
                from DeviceServers import get_class_match

                widget_map = get_class_match() or {}
            except Exception:
                widget_map = {}

            # Heuristic mapping by keywords
            name = device_name.lower()
            widget_cls = None
            # Map DS class name -> widget class from registry (values are classes)
            # We only need to pick one based on keywords
            keyword_map = [
                ("netio", "Netio_pdu"),
                ("basler", "Basler_camera"),
                ("owis", "OWIS_motor"),
                ("standa", "Standa_motor"),
                ("topdirect", "TopDirect_Motor"),
            ]

            # Build reverse index for easier lookup by class __name__
            reverse_by_name = {
                getattr(cls, "__name__", ""): cls for cls in widget_map.values()
            }

            for kw, cls_name in keyword_map:
                if kw in name and cls_name in reverse_by_name:
                    widget_cls = reverse_by_name[cls_name]
                    break

            if not widget_cls:
                QMessageBox.information(
                    self, "Info", f"No GUI widget mapping found for {device_name}"
                )
                return

            # Instantiate and show the widget
            from DeviceServers.shared.DS_Widget import VisType as DSVisType

            w = widget_cls(device_name, parent=None, vis_type=DSVisType.FULL)
            w.setWindowTitle(f"{widget_cls.__name__} - {device_name}")
            w.resize(900, 600)
            w.show()
            # Keep a reference to prevent garbage collection
            if not hasattr(self, "_open_ds_widgets"):
                self._open_ds_widgets = []
            self._open_ds_widgets.append(w)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open GUI for {device_name}: {e}"
            )

    def rebuild_deviceservers_list(self):
        """Rebuild the DeviceServers list UI from DB admin devices with controlled devices."""
        # Clear existing rows except final stretch
        try:
            while self.ds_list_layout.count() > 1:
                item = self.ds_list_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass
        self.ds_status_widgets = {}

        # Need infrastructure manager for DB-driven list
        if not self.async_manager or not self.async_manager.infrastructure_mgr:
            info = QLabel("Infrastructure manager not ready")
            self.ds_list_layout.insertWidget(self.ds_list_layout.count() - 1, info)
            return

        # Fetch admin servers with their devices (may be slow) -> run minimal blocking by calling manager directly
        try:
            servers = (
                self.async_manager.infrastructure_mgr.list_admin_servers_with_devices()
            )
        except Exception as e:
            servers = []
            self.ds_list_layout.insertWidget(
                self.ds_list_layout.count() - 1,
                QLabel(f"Failed to load admin servers: {e}"),
            )
            return

        # Build UI
        for s in sorted(
            servers,
            key=lambda d: f"{d.get('server_class', '')}/{d.get('instance', '')}",
        ):
            server_class = s.get("server_class", "")
            instance = s.get("instance", "")
            admin = s.get("admin", "")
            status = s.get("status", "Unknown")
            devices = s.get("devices", []) or []
            # Header row for admin server
            header_row = QHBoxLayout()
            led = LedIndicator(12)
            status_label = QLabel(str(status))
            key = str(admin) or f"{server_class}/{instance}"
            self.ds_status_widgets[key] = (led, status_label)
            header_row.addWidget(led)
            header_row.addWidget(QLabel(f"{server_class}/{instance}"))
            header_row.addWidget(QLabel("Status:"))
            header_row.addWidget(status_label)
            header_row.addStretch()
            header_container = QWidget()
            header_container.setLayout(header_row)
            self.ds_list_layout.insertWidget(
                self.ds_list_layout.count() - 1, header_container
            )

            # Controlled devices under this server
            if devices:
                for dev_name in sorted(devices):
                    row = QHBoxLayout()
                    row.addWidget(QLabel("↳"))
                    row.addWidget(QLabel(dev_name))
                    btn_open = QPushButton("Open GUI")
                    btn_open.clicked.connect(
                        lambda _, n=dev_name: self.open_device_widget_for_name(n)
                    )
                    row.addWidget(btn_open)
                    row.addStretch()
                    cont = QWidget()
                    cont.setLayout(row)
                    self.ds_list_layout.insertWidget(
                        self.ds_list_layout.count() - 1, cont
                    )
            else:
                # No devices found
                row = QHBoxLayout()
                row.addWidget(QLabel("↳ (no devices found)"))
                row.addStretch()
                cont = QWidget()
                cont.setLayout(row)
                self.ds_list_layout.insertWidget(self.ds_list_layout.count() - 1, cont)

    def on_refresh_deviceservers_clicked(self):
        self.rebuild_deviceservers_list()
        self.update_deviceservers_status()

    def update_deviceservers_status(self):
        """Update per-DS status by probing DB admin devices and applying LEDs."""
        try:
            # Default: set unknown
            for key, (led, lab) in self.ds_status_widgets.items():
                led.set_off()
                lab.setText("Unknown")
            if not self.async_manager or not self.async_manager.is_managers_ready():
                return
            if not self.async_manager.infrastructure_mgr:
                return
            servers = (
                self.async_manager.infrastructure_mgr.list_admin_servers_with_devices()
            )
            for s in servers:
                admin = s.get("admin") or f"{s.get('server_class')}/{s.get('instance')}"
                status = s.get("status", "Unknown")
                key = str(admin)
                if key in self.ds_status_widgets:
                    led, lab = self.ds_status_widgets[key]
                    st = (status or "").lower()
                    if st == "running":
                        led.set_on()
                    elif st == "stopped":
                        led.set_off()
                    elif st == "error":
                        led.set_error()
                    else:
                        led.set_off()
                    lab.setText(str(status))
        except Exception as e:
            logger.debug(f"update_deviceservers_status failed: {e}")

    def stop_device_server(self, device_type: str, instance: str):
        if not self.async_manager or not self.async_manager.is_managers_ready():
            QMessageBox.warning(self, "Warning", "System not ready yet.")
            return
        ok = self.async_manager.device_mgr.stop_deviceserver(device_type, instance)
        if ok:
            self.statusBar.showMessage(f"Stopped {device_type}/{instance}")
        else:
            QMessageBox.warning(
                self, "Warning", f"Failed to stop {device_type}/{instance}"
            )

    def open_device_client(self, device_type: str, instance: str):
        """Open GUI control widget for a device server using legacy ClientManager lazily."""
        try:
            if not hasattr(self, "_client_manager") or self._client_manager is None:
                from legacy.ClientManager import ClientManager, VisType

                self._client_manager = ClientManager()
                self._VisType = VisType
            # Launch client
            ok = self._client_manager.launch_client(
                device_type, instance, self._VisType.FULL
            )
            if not ok:
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Failed to launch GUI for {device_type}/{instance}",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error launching GUI for {device_type}/{instance}: {e}"
            )

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About PyConlyse v2.0",
            """PyConlyse v2.0 - Control System
                         
Modular Tango control system with async operations.

Features:
- Non-blocking GUI that starts immediately
- Background connection management
- Real-time status monitoring
- Comprehensive logging system
- Device server management

© 2025 PyConlyse Team""",
        )

    def closeEvent(self, event):
        """Handle application close."""
        logger.info("Application shutdown requested")

        if self.async_manager:
            self.async_manager.shutdown()

        # Stop ELYSE thread and ZMQ
        try:
            if self._elyse_thread:
                self._elyse_thread.stop()
                self._elyse_thread.wait(1000)
        except Exception:
            pass
        try:
            if self._zmq_push:
                self._zmq_push.close()
        except Exception:
            pass
        try:
            if self._zmq_context:
                self._zmq_context.term()
        except Exception:
            pass

        # Stop timers
        if hasattr(self, "status_timer"):
            self.status_timer.stop()
        if hasattr(self, "gui_timer"):
            self.gui_timer.stop()

        logger.info("Application shutdown complete")
        event.accept()

    def deferred_startup(self):
        """Perform heavy initialization after the GUI is shown."""
        if self._deferred_started:
            return
        self._deferred_started = True

        try:
            # Setup logging now (writes to files, handlers, etc.)
            self.logger_manager = setup_pyconlyse_logging()
            logger.info("Deferred startup: logging initialized")

            # Build full UI (menus, panels, logs)
            self.setup_ui()
            self.statusBar.showMessage(
                "Building UI... done. Starting background services..."
            )

            # Timers
            self.setup_timers()

            # Async managers
            self.initialize_async_manager()

            # Start legacy-inspired ELYSE control thread
            self.start_elyse_control()

            logger.info("Deferred startup complete")
            self.statusBar.showMessage("System initializing in background...")
        except Exception as e:
            logger.exception(f"Deferred startup failed: {e}")
            QMessageBox.critical(self, "Startup Error", f"Initialization failed: {e}")


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
