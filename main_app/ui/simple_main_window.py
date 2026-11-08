#!/usr/bin/env python3
"""Simple Modular PyConlyse GUI (legacy-like layout)

A minimal GUI inspired by bin/main_ctrl_LEGACY.py but implemented with the
current modular codebase and non-blocking behavior:
- Starts GUI immediately, defers device/DB operations to background
- Uses taurus.Device for device state reads (no DeviceProxy)
- Uses Tango Database for discovery
"""

from sys import modules as _refactor_modules

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Taurus imports (legacy style)
from taurus.qt.qtgui.application import TaurusApplication
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.input import TaurusValueComboBox

# Path setup
main_app_path = Path(__file__).parent.parent
sys.path.insert(0, str(main_app_path.parent))

from main_app.ui.simple_main_window_methods_build_menu import _bind_simple_main_window_methods_build_menu
from main_app.ui.simple_main_window_methods_refresh_devices_async import _bind_simple_main_window_methods_refresh_devices_async

logger = logging.getLogger(__name__)

# Config and launchers
from main_app.core.config import OFFLINE_MODE
from main_app.ui.experiment_preparation import open_preparation_window

# Optional DS visualization type
try:
    from DeviceServers.shared.DS_Widget import VisType as DSVisType
except Exception:  # pragma: no cover
    DSVisType = None  # type: ignore


class LedIndicator(QLabel):
    def __init__(self, diameter: int = 12):
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


def client_configs() -> List[Tuple[str, str, List[str], str, str]]:
    """Return simplified client configs: (key, display, keywords, launcher, icon)."""
    return [
        ("NETIO", "NETIO", ["netio"], "start_netio_client", "icons/NETIO.png"),
        ("OWIS", "OWIS", ["owis", "delay"], "start_owis_widget", "icons/OWIS.png"),
        ("ZABER", "Zaber", ["zaber"], "start_zaber_widget", "icons/OWIS.png"),
        ("STANDA", "STANDA", ["standa"], "start_standa_widget", "icons/STANDA.svg"),
        (
            "TOPDIRECT",
            "TOPDIRECT",
            ["topdirect"],
            "start_topdirect_widget",
            "icons/TopDirect.svg",
        ),
        (
            "BASLER",
            "BASLER",
            ["basler", "camera"],
            "start_basler_widget",
            "icons/basler_camera.svg",
        ),
        (
            "LASER_POINTING",
            "Laser Pointing",
            ["laser"],
            "start_laser_pointing_widget",
            "icons/laser_pointing.svg",
        ),
        (
            "KEYSIGHT",
            "KEYSIGHT 33509B",
            ["keysight", "awg", "33509"],
            "start_keysight_widget",
            "icons/NETIO.png",
        ),
        (
            "ITEST",
            "iTest PSU",
            ["itest", "2819", "bilt"],
            "start_itest_widget",
            "icons/NETIO.png",
        ),
    ]


class SimpleMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PYCONLYSE")
        # Use legacy icon path
        try:
            self.setWindowIcon(
                QIcon(str(main_app_path.parent / "bin" / "icons" / "main_icon.png"))
            )
        except Exception:
            pass

        # Visualization type (optional)
        self._client_vis = getattr(DSVisType, "FULL", None)

        # Central Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Clients tab
        self.clients_tab = QWidget()
        self.clients_layout = QVBoxLayout(self.clients_tab)
        self.tabs.addTab(self.clients_tab, "Clients")

        # Build Clients UI (multi-DS rows)
        self._build_clients_ui()

        # Menu
        self._build_menu()

        # Status bar
        self.statusBar().showMessage("Ready")

        # Auto-size window based on content
        self._auto_resize_window()

        # Defer loading so GUI shows instantly
        QTimer.singleShot(0, self._deferred_startup)

    _simple_main_window_methods_build_menu = _bind_simple_main_window_methods_build_menu(_refactor_modules[__name__])
    _build_menu = _simple_main_window_methods_build_menu["_build_menu"]

    _build_clients_ui = _simple_main_window_methods_build_menu["_build_clients_ui"]

    _build_devices_ui = _simple_main_window_methods_build_menu["_build_devices_ui"]

    _set_vis = _simple_main_window_methods_build_menu["_set_vis"]

    _open_experiment_preparation = _simple_main_window_methods_build_menu["_open_experiment_preparation"]

    # ----- Deferred startup -----
    _auto_resize_window = _simple_main_window_methods_build_menu["_auto_resize_window"]

    _launch_astor = _simple_main_window_methods_build_menu["_launch_astor"]

    _deferred_startup = _simple_main_window_methods_build_menu["_deferred_startup"]

    # ----- Config helpers -----
    _load_clients_config = _simple_main_window_methods_build_menu["_load_clients_config"]

    _save_clients_config = _simple_main_window_methods_build_menu["_save_clients_config"]

    _update_defaults_from_clients = _simple_main_window_methods_build_menu["_update_defaults_from_clients"]

    _refresh_client_combos_from_config = _simple_main_window_methods_build_menu["_refresh_client_combos_from_config"]

    edit_device_clients_config = _simple_main_window_methods_build_menu["edit_device_clients_config"]

    populate_clients_from_db = _simple_main_window_methods_build_menu["populate_clients_from_db"]
    del _simple_main_window_methods_build_menu

    _simple_main_window_methods_refresh_devices_async = _bind_simple_main_window_methods_refresh_devices_async(_refactor_modules[__name__])
    refresh_devices_async = _simple_main_window_methods_refresh_devices_async["refresh_devices_async"]

    _rebuild_devices_grid = _simple_main_window_methods_refresh_devices_async["_rebuild_devices_grid"]

    update_device_states_async = _simple_main_window_methods_refresh_devices_async["update_device_states_async"]

    # ----- Actions -----
    _resolve_itest_device = _simple_main_window_methods_refresh_devices_async["_resolve_itest_device"]

    _launch_client = _simple_main_window_methods_refresh_devices_async["_launch_client"]
    del _simple_main_window_methods_refresh_devices_async


def main():
    # Use TaurusApplication like legacy code
    app = TaurusApplication(sys.argv, cmd_line_parser=None)
    app.setApplicationName("PYCONLYSE")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("PyConlyse Team")

    win = SimpleMainWindow()
    win.show()
    return app.exec_()
