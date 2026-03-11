#!/usr/bin/env python3
"""Simple Modular PyConlyse GUI (legacy-like layout)

A minimal GUI inspired by bin/main_ctrl_LEGACY.py but implemented with the
current modular codebase and non-blocking behavior:
- Starts GUI immediately, defers device/DB operations to background
- Uses taurus.Device for device state reads (no DeviceProxy)
- Uses Tango Database for discovery
"""

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

logger = logging.getLogger(__name__)

# Config and launchers
from main_app.core.config import OFFLINE_MODE

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

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Config menu
        cfg_menu = menubar.addMenu("&Config")
        edit_cfg_action = QAction("Edit Device Clients Config...", self)
        edit_cfg_action.triggered.connect(self.edit_device_clients_config)
        cfg_menu.addAction(edit_cfg_action)

        populate_action = QAction("Populate Device Lists from Tango DB", self)
        populate_action.setShortcut(QKeySequence("Ctrl+R"))
        populate_action.triggered.connect(self.populate_clients_from_db)
        cfg_menu.addAction(populate_action)

        # Clients menu with shortcuts
        clients_menu = menubar.addMenu("&Clients")

        act_netio = QAction("Start NETIO", self)
        act_netio.setShortcut(QKeySequence("Ctrl+N"))
        act_netio.triggered.connect(lambda: self._launch_client("NETIO"))
        clients_menu.addAction(act_netio)

        act_owis = QAction("Start OWIS", self)
        act_owis.setShortcut(QKeySequence("Ctrl+O"))
        act_owis.triggered.connect(lambda: self._launch_client("OWIS"))
        clients_menu.addAction(act_owis)

        act_standa = QAction("Start STANDA", self)
        act_standa.setShortcut(QKeySequence("Ctrl+S"))
        act_standa.triggered.connect(lambda: self._launch_client("STANDA"))
        clients_menu.addAction(act_standa)

        act_topdirect = QAction("Start TOPDIRECT", self)
        act_topdirect.setShortcut(QKeySequence("Ctrl+T"))
        act_topdirect.triggered.connect(lambda: self._launch_client("TOPDIRECT"))
        clients_menu.addAction(act_topdirect)

        act_basler = QAction("Start BASLER", self)
        act_basler.setShortcut(QKeySequence("Ctrl+B"))
        act_basler.triggered.connect(lambda: self._launch_client("BASLER"))
        clients_menu.addAction(act_basler)

        act_laser = QAction("Start LASER POINTING", self)
        act_laser.setShortcut(QKeySequence("Ctrl+L"))
        act_laser.triggered.connect(lambda: self._launch_client("LASER_POINTING"))
        clients_menu.addAction(act_laser)

        act_itest = QAction("Start iTest PSU", self)
        act_itest.setShortcut(QKeySequence("Ctrl+I"))
        act_itest.triggered.connect(lambda: self._launch_client("ITEST"))
        clients_menu.addAction(act_itest)

        clients_menu.addSeparator()
        act_astor = QAction("Start Astor", self)
        act_astor.setShortcut(QKeySequence("Ctrl+A"))
        act_astor.triggered.connect(self._launch_astor)
        clients_menu.addAction(act_astor)

    def _build_clients_ui(self):
        # Ensure config
        self.config_path = main_app_path / "config" / "device_clients.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._defaults = {
            # Instance/config names matching legacy cbox items (from DS_*_client.py)
            "NETIO": ["all", "V0", "VD2"],
            "OWIS": ["V0", "VD2", "all"],
            "STANDA": ["alignment", "V0", "V0_short", "ELYSE", "OPA"],
            "TOPDIRECT": ["VD2", "all"],
            "BASLER": ["V0", "Cam1", "Cam2", "Cam3", "all"],
            "LASER_POINTING": ["Cam1", "Cam2", "Cam3", "V0", "3P"],
            "KEYSIGHT": ["laser"],
            "ITEST": ["ELYSE", "ITestPSU/test", "ITestPSU/bilt", "ITestPSU/lab", "ITestPSU/main"],
            "DAQMX_ZMQ": ["DAQMX_ZMQ_1"],
            # Additional clients (not shown in UI rows yet)
            "ANDOR_CCD": [],
            "AVANTES_CCD": [],
            "AVANTES_SPECTRO": [],
            "ARCHIVE": [],
            "EXPERIMENT": [],
        }

        # Device mappings from actual DS client layouts for tooltips
        self._instance_info = {
            "NETIO": {
                "all": "All PDUs: V0, VD2, SD1, SD2, ELYSE",
                "V0": "V0 Setup PDUs: PDU_VO, PDU_SD1, PDU_SD2",
                "VD2": "VD2 Setup PDUs: PDU_VD2, PDU_SD2",
                "ELYSE": "ELYSE PDU only",
            },
            "OWIS": {
                "V0": (
                    "V0 Delay Lines: axes 2,3 from DS_OWIS_PS90_IP + axis 4 "
                    "from DS_OWIS_PS90"
                ),
                "VD2": "VD2 Delay Line: axis 1 (preferred DS_OWIS_PS90_IP)",
                "all": (
                    "All Delay Lines: axes 1,2,3 from DS_OWIS_PS90_IP + axis 4 "
                    "from DS_OWIS_PS90"
                ),
            },
            "STANDA": {
                "ELYSE": "ELYSE Motors: DE1, F1, MME_X/Y, MM1_X/Y, MM2_X/Y (8 motors)",
                "V0": (
                    "V0 Motors: MM3/4_X/Y, DV01-04, S1-3, L-2_1, OPA_X/Y, "
                    "TS_SC/OPA (16 motors)"
                ),
                "V0_short": "V0 Essential: DV04, L-2_1 (2 motors)",
                "alignment": (
                    "Alignment Motors: DE1/2, DV01-03, MM1-4_X/Y, S1-2, "
                    "L-2_1 (16 motors)"
                ),
                "OPA": "OPA Motors: OPA_X, OPA_Y (2 motors)",
            },
            "TOPDIRECT": {
                "all": "All TopDirect: Lense260, DL_SC1 (2 motors)",
                "VD2": "VD2 TopDirect: Mirror, Emission Mirrors, Filter 1&2 (4 motors)",
            },
            "BASLER": {
                "V0": "V0 Cameras: Cam1_V0, Cam2_V0 (2 cameras)",
                "all": "All Cameras: Cam1_V0, Cam2_V0, Cam3_V0 (3 cameras)",
                "Cam1": "Camera 1: Cam1_V0 only",
                "Cam2": "Camera 2: Cam2_V0 only",
                "Cam3": "Camera 3: Cam3_V0 only",
            },
            "LASER_POINTING": {
                "V0": "V0 Pointing: LaserPointing-Cam1, Cam2 (2 devices)",
                "3P": "3-Point Pointing: LaserPointing-Cam1, Cam2, Cam3 (3 devices)",
                "Cam1": "Pointing Cam1: LaserPointing-Cam1 only",
                "Cam2": "Pointing Cam2: LaserPointing-Cam2 only",
                "Cam3": "Pointing Cam3: LaserPointing-Cam3 only",
            },
            "KEYSIGHT": {
                "laser": "Keysight 33509B: manip/awg/keysight33509b_laser",
            },
            "ITEST": {
                "ELYSE": "iTest PSU ELYSE: ELYSE/pdu/iTest (DS_itest_psu/1_iTest)",
                "ITestPSU/test": "iTest PSU Test Rack (8 slots): test/itest/psu01",
                "ITestPSU/bilt": "iTest PSU BILT Rack (8 slots): bilt/power/itest_main",
                "ITestPSU/lab": "iTest PSU Lab Rack (8 slots): lab/itest/psu01",
                "ITestPSU/main": "iTest PSU Main Rack (8 slots): manip/power/itest_psu01",
            },
            "DAQMX_ZMQ": {
                "DAQMX_ZMQ_1": "DAQmx ZMQ Reader: control/DAQ/DAQMX_ZMQ_1 (receives from LabVIEW PSP)",
            },
        }
        # Try to derive instance lists from installed client modules
        self._update_defaults_from_clients()
        self._config = self._load_clients_config()

        # Icons directory (absolute)
        self.icons_dir = main_app_path.parent / "bin" / "icons"
        # DS rows definition: key, display, icon, launcher key
        self._ds_rows_def = [
            ("NETIO", "NETIO", self.icons_dir / "NETIO.png", "client"),
            ("OWIS", "OWIS", self.icons_dir / "OWIS.svg", "widget"),
            ("STANDA", "STANDA", self.icons_dir / "STANDA.svg", "widget"),
            ("TOPDIRECT", "TOPDIRECT", self.icons_dir / "TopDirect.svg", "widget"),
            ("BASLER", "BASLER", self.icons_dir / "basler_camera.svg", "widget"),
            (
                "LASER_POINTING",
                "Laser Pointing",
                self.icons_dir / "laser_pointing.svg",
                "widget",
            ),
            (
                "KEYSIGHT",
                "KEYSIGHT 33509B",
                self.icons_dir / "NETIO.png",
                "client",
            ),
            (
                "ITEST",
                "iTest PSU",
                self.icons_dir / "NETIO.png",
                "client",
            ),
            (
                "DAQMX_ZMQ",
                "DAQmx ZMQ",
                self.icons_dir / "NETIO.png",
                "client",
            ),
        ]

        self.client_rows: Dict[str, Dict[str, QWidget]] = {}
        self._launched_panels: List[QWidget] = []

        # Visualization type selection (legacy style)
        vis_group = QGroupBox("Type")
        vis_layout = QHBoxLayout(vis_group)
        if DSVisType is not None:
            for vt in DSVisType:
                rb = QPushButton(vt.value)
                rb.setCheckable(True)
                if vt == DSVisType.FULL:
                    rb.setChecked(True)

                def _mk(v):
                    return lambda: self._set_vis(v)

                rb.clicked.connect(_mk(vt))
                vis_layout.addWidget(rb)
        vis_layout.addStretch()
        self.clients_layout.addWidget(vis_group)

        # DS rows - 2 column grid layout
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(5)
        
        for idx, (key, display, icon, kind) in enumerate(self._ds_rows_def):
            row = idx // 2
            col = idx % 2
            
            # Use TaurusCommandButton like legacy
            btn = TaurusCommandButton(text=display, parent=self.clients_tab)
            try:
                btn.setIcon(QIcon(str(icon)))
            except Exception:
                pass
            combo = TaurusValueComboBox(parent=self.clients_tab)
            # Populate from config (fall back to defaults)
            options = self._config.get(key) or self._defaults.get(key) or []
            if options:
                combo.addItems(options)
                # Add tooltip with device info
                tooltip_lines = [f"{display} Instance Configurations:"]
                info_map = self._instance_info.get(key, {})
                for opt in options:
                    desc = info_map.get(opt, f"Instance: {opt}")
                    tooltip_lines.append(f"• {opt}: {desc}")
                combo.setToolTip("\n".join(tooltip_lines))
            else:
                combo.addItem("(configure...)")
                combo.setEnabled(False)
                combo.setToolTip(
                    f"No {display} instances configured. Use Config menu to add."
                )

            # Add to grid: button in first column, combo in second column of each pair
            grid.addWidget(btn, row, col * 2)
            grid.addWidget(combo, row, col * 2 + 1)

            # Store refs
            self.client_rows[key] = {"button": btn, "combo": combo, "kind": kind}

            # Connect
            btn.clicked.connect(lambda _, k=key: self._launch_client(k))
        
        # Add grid to layout
        grid_container = QWidget()
        grid_container.setLayout(grid)
        self.clients_layout.addWidget(grid_container)

        # Add Astor button at the end
        astor_row = QHBoxLayout()
        astor_btn = TaurusCommandButton(text="Astor", parent=self.clients_tab)
        try:
            astor_btn.setIcon(QIcon(str(self.icons_dir / "main_icon.png")))
        except Exception:
            pass
        astor_btn.clicked.connect(self._launch_astor)
        astor_row.addWidget(astor_btn)
        astor_row.addStretch()
        astor_cont = QWidget()
        astor_cont.setLayout(astor_row)
        self.clients_layout.addWidget(astor_cont)

    def _build_devices_ui(self):
        # Controls
        ctrl = QHBoxLayout()
        self.btn_refresh_devices = QPushButton("Refresh Devices (ELYSE, manip)")
        self.btn_refresh_devices.clicked.connect(self.refresh_devices_async)
        ctrl.addWidget(self.btn_refresh_devices)

        self.btn_update_states = QPushButton("Update States")
        self.btn_update_states.clicked.connect(self.update_device_states_async)
        ctrl.addWidget(self.btn_update_states)

        ctrl.addStretch()
        self.devices_layout.addLayout(ctrl)

        # Scroll for devices grid
        self.devices_scroll = QScrollArea()
        self.devices_scroll.setWidgetResizable(True)
        self.devices_container = QWidget()
        self.devices_grid = QGridLayout(self.devices_container)
        self.devices_grid.setColumnStretch(2, 1)
        self.devices_scroll.setWidget(self.devices_container)
        self.devices_layout.addWidget(self.devices_scroll)

        self.device_widgets: Dict[str, Tuple[LedIndicator, QLabel]] = {}

    def _set_vis(self, val):
        try:
            self._client_vis = val
        except Exception:
            self._client_vis = getattr(DSVisType, "FULL", None)

    # ----- Deferred startup -----
    def _auto_resize_window(self):
        # Calculate size based on DS rows + Astor button + padding
        num_rows = len(self._ds_rows_def) + 1  # +1 for Astor button
        # Base height: menu + status + visualization group + padding (no tabs now)
        base_height = 50 + 30 + 60 + 40  # ~180px
        row_height = 40  # Height per DS row
        calc_height = base_height + (num_rows * row_height)

        # Width based on button + combo + margins
        calc_width = 450

        self.resize(calc_width, calc_height)
        self.setMinimumSize(calc_width, calc_height)

    def _launch_astor(self):
        """Launch Astor from Windows Start Menu"""
        try:
            import subprocess

            # Try multiple possible paths for Astor
            astor_paths = [
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Tango\Astor.lnk",
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Tango\Astor.exe",
                "astor",  # If in PATH
                "Astor",  # Case variation
            ]

            for path in astor_paths:
                try:
                    if path.endswith(".lnk"):
                        # Use start command for .lnk files
                        subprocess.Popen(["cmd", "/c", "start", "", path], shell=False)
                    else:
                        subprocess.Popen([path], shell=False)
                    self.statusBar().showMessage("Astor started")
                    return
                except Exception:
                    continue

            # If all paths failed, show error
            QMessageBox.warning(
                self,
                "Astor",
                (
                    "Could not launch Astor. Please check if Tango is "
                    "installed and Astor is available."
                ),
            )

        except Exception as e:
            QMessageBox.critical(self, "Astor", f"Failed to launch Astor: {e}")

    def _deferred_startup(self):
        # No DS list to populate
        self.statusBar().showMessage("Ready")

    # ----- Config helpers -----
    def _load_clients_config(self) -> Dict[str, List[str]]:
        try:
            if self.config_path.exists():
                with self.config_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Merge with defaults to ensure keys exist
                        merged = {
                            **self._defaults,
                            **{k: v for k, v in data.items() if isinstance(v, list)},
                        }
                        return merged
            # If missing or invalid, write defaults
            self._save_clients_config(self._defaults)
            return dict(self._defaults)
        except Exception:
            return dict(self._defaults)

    def _save_clients_config(self, data: Dict[str, List[str]]):
        try:
            with self.config_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Config", f"Failed to save config: {e}")

    def _update_defaults_from_clients(self):
        """Update defaults from DS client modules' `layouts` if available."""
        import importlib

        module_map = {
            "NETIO": "DeviceServers.power.netio.DS_NETIO_client",
            "OWIS": "DeviceServers.motion.owis.DS_OWIS_client",
            "STANDA": "DeviceServers.motion.standa.DS_STANDA_client",
            "TOPDIRECT": "DeviceServers.motion.topdirect.DS_TOPDIRECT_client",
            "BASLER": "DeviceServers.cameras.basler.DS_BASLER_client",
            "LASER_POINTING": (
                "DeviceServers.control.laser_pointing.DS_LASER_POINTING_client"
            ),
            "ANDOR_CCD": "DeviceServers.cameras.andor.DS_ANDOR_CCD_client",
            "AVANTES_CCD": "DeviceServers.cameras.avantes.DS_AVANTES_CCD_client",
            "AVANTES_SPECTRO": (
                "DeviceServers.spectrographs.avantes.DS_AVANTES_SPECTRO_client"
            ),
            "ARCHIVE": "DeviceServers.data.archive.DS_ARCHIVE_client",
            "EXPERIMENT": "DeviceServers.control.experiment.DS_Experiment_client",
            "ITEST": "DeviceServers.power.iTest.DS_iTest_client",
        }
        for key, modname in module_map.items():
            try:
                mod = importlib.import_module(modname)
                layouts = getattr(mod, "layouts", None)
                if isinstance(layouts, dict) and layouts:
                    # Preserve order of keys
                    self._defaults[key] = list(layouts.keys())
            except Exception:
                continue

    def _refresh_client_combos_from_config(self):
        self._config = self._load_clients_config()
        for key, refs in self.client_rows.items():
            combo: QComboBox = refs.get("combo")  # type: ignore
            # kind = refs.get("kind")  # unused variable
            combo.setEnabled(True)
            combo.clear()
            options = self._config.get(key) or self._defaults.get(key) or []
            if options:
                combo.addItems(options)
            else:
                combo.addItem("(configure...)")
                combo.setEnabled(False)

    def edit_device_clients_config(self):
        # Open a simple JSON editor dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Device Clients Config")
        dlg.resize(600, 500)
        vbox = QVBoxLayout(dlg)
        info = QLabel(
            (
                "Edit JSON mapping: "
                "{ 'NETIO': ['ALL','V0',...], 'OWIS': ['device1', ...], ... }"
            )
        )
        info.setWordWrap(True)
        vbox.addWidget(info)
        editor = QPlainTextEdit()
        try:
            text = json.dumps(self._config, indent=2)
        except Exception:
            text = "{}"
        editor.setPlainText(text)
        vbox.addWidget(editor)
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        def on_save():
            try:
                data = json.loads(editor.toPlainText())
                if not isinstance(data, dict):
                    raise ValueError(
                        "Top-level must be a JSON object mapping keys to lists"
                    )
                # Normalize: keep only known keys as lists of strings
                norm: Dict[str, List[str]] = {}
                for k in self._defaults.keys():
                    v = data.get(k, self._defaults[k])
                    if isinstance(v, list):
                        norm[k] = [str(x) for x in v]
                    else:
                        norm[k] = list(self._defaults[k])
                self._save_clients_config(norm)
                self._refresh_client_combos_from_config()
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(dlg, "Error", f"Invalid JSON: {e}")

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec_()

    def populate_clients_from_db(self):
        # Scan Tango DB and populate selection lists for DS (except NETIO)
        try:
            from main_app.core.config import OFFLINE_MODE as OM

            if OM:
                QMessageBox.information(
                    self, "Populate", "OFFLINE_MODE is enabled; cannot query DB."
                )
                return
            from tango import Database
        except Exception as e:
            QMessageBox.warning(self, "Populate", f"Cannot access Tango Database: {e}")
            return

        try:
            db = Database()
            names: List[str] = []
            for prefix in ("ELYSE", "manip"):
                try:
                    names.extend(list(db.get_device_exported(f"{prefix}*")))
                except Exception:
                    continue
            lower_names = [(n, n.lower()) for n in set(names)]

            # Categorize by keywords
            def match(keywords: List[str]) -> List[str]:
                out = []
                for n, ln in lower_names:
                    if any(kw in ln for kw in keywords):
                        out.append(n)
                return sorted(out)

            # Note: With instance-based configs, DB population is less useful
            # But we can still detect presence and suggest appropriate instances
            categories = {
                "OWIS": ["V0", "VD2", "all"] if match(["owis", "delay"]) else [],
                "STANDA": (
                    ["alignment", "V0", "V0_short", "ELYSE", "OPA"]
                    if match(["standa", "mm3", "mm4", "mm", "opa"])
                    else []
                ),
                "TOPDIRECT": ["VD2", "all"] if match(["topdirect"]) else [],
                "BASLER": (
                    ["V0", "Cam1", "Cam2", "Cam3"]
                    if match(["basler", "cam", "camera"])
                    else []
                ),
                "LASER_POINTING": (
                    ["Cam1", "Cam2", "Cam3", "V0", "3P"]
                    if match(["laserpointing", "laser_pointing", "laser", "pointing"])
                    else []
                ),
            }

            # Merge with current config, keep NETIO as-is
            new_cfg = dict(self._config)
            for k, lst in categories.items():
                # Only update if we found devices; else keep existing list
                if lst:
                    new_cfg[k] = lst
            self._save_clients_config(new_cfg)
            self._refresh_client_combos_from_config()
            self.statusBar().showMessage("Device lists populated from DB")
        except Exception as e:
            QMessageBox.critical(self, "Populate", f"Failed to populate from DB: {e}")

    def refresh_devices_async(self):
        # Build device list from DB and place into grid; states updated separately
        if OFFLINE_MODE:
            self._rebuild_devices_grid([])
            return
        try:
            import concurrent.futures

            from tango import Database
        except Exception:
            self._rebuild_devices_grid([])
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
                # Unique and sorted
                return sorted(set(names))
            except Exception:
                return []

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_fetch)

        def _done(_f):
            try:
                names = _f.result(timeout=0) or []
            except Exception:
                names = []
            QTimer.singleShot(0, lambda lst=names: self._rebuild_devices_grid(lst))
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    def _rebuild_devices_grid(self, device_names: List[str]):
        # Clear grid
        try:
            while self.devices_grid.count() > 0:
                item = self.devices_grid.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
        except Exception:
            pass
        self.device_widgets.clear()

        # Rebuild
        row, col = 0, 0
        cols = 3
        for name in device_names:
            led = LedIndicator(10)
            lab = QLabel(name)
            lab.setStyleSheet("font-size: 11px")
            self.devices_grid.addWidget(led, row, col)
            self.devices_grid.addWidget(lab, row, col + 1)
            self.device_widgets[name] = (led, lab)
            col += 2
            if col >= cols * 2:
                col = 0
                row += 1
        self.statusBar().showMessage(f"Devices listed: {len(device_names)}")

    def update_device_states_async(self):
        if OFFLINE_MODE:
            return
        if not self.device_widgets:
            return
        try:
            import concurrent.futures

            from taurus import Device
        except Exception:
            return

        names = list(self.device_widgets.keys())

        def _read_all():
            res = {}
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:

                    def read_state(dev_name: str):
                        try:
                            dev = Device(dev_name)
                            st = str(dev.state()).upper()
                            return dev_name, st
                        except Exception:
                            return dev_name, "ERROR"

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

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_read_all)

        def _done(_f):
            try:
                results = _f.result(timeout=0) or {}
            except Exception:
                results = {}

            def apply():
                for dev, (led, lab) in self.device_widgets.items():
                    st = (results.get(dev) or "UNKNOWN").upper()
                    if st in ("ON", "RUNNING", "STANDBY", "MOVING"):
                        led.set_on()
                    elif st in ("OFF",):
                        led.set_off()
                    elif st in ("ERROR", "FAULT", "ALARM"):
                        led.set_error()
                    else:
                        led.set_off()
                    lab.setText(dev)

            QTimer.singleShot(0, apply)
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    # ----- Actions -----
    def _resolve_itest_device(self, config_or_device: str) -> str:
        """Map selection to Tango device for iTest client.
        Accepts either a config name (e.g. 'ITestPSU/test') or a full device name.
        """
        mapping = {
            "ELYSE": "ELYSE/pdu/iTest",
            "ITestPSU/ELYSE": "ELYSE/pdu/iTest",
            "ITestPSU/test": "test/itest/psu01",
            "ITestPSU/main": "manip/power/itest_psu01",
            "ITestPSU/lab": "lab/itest/psu01",
            "ITestPSU/bilt": "bilt/power/itest_main",
            "test": "test/itest/psu01",
            "main": "manip/power/itest_psu01",
            "lab": "lab/itest/psu01",
            "bilt": "bilt/power/itest_main",
        }
        if "/" in config_or_device and config_or_device not in mapping:
            return config_or_device
        return mapping.get(config_or_device, config_or_device)

    def _launch_client(self, key: str):
        try:
            import subprocess
            import sys
            from pathlib import Path

            refs = self.client_rows.get(key) or {}
            combo: QComboBox = refs.get("combo")  # type: ignore
            if not combo or combo.count() == 0 or not combo.isEnabled():
                QMessageBox.information(
                    self, key, "Please configure selection list in Config menu."
                )
                return
            selection = (combo.currentText() or "").strip()
            vis = (
                self._client_vis.value if hasattr(self._client_vis, "value") else "FULL"
            )

            # All DS now use instance/config names, not device names
            if not selection or selection.startswith("("):
                QMessageBox.information(
                    self, key, "Please select an instance or configure list."
                )
                return

            # If this key is configured as a 'widget', prefer launching in-process widget
            kind = refs.get("kind") if isinstance(refs, dict) else None
            if key == "ITEST" and kind == "widget":
                try:
                    from main_app.ui.widget_launchers import start_itest_widget
                except Exception as e:
                    QMessageBox.critical(self, key, f"Cannot import iTest widget: {e}")
                    return
                device_name = self._resolve_itest_device(selection)
                panel = start_itest_widget(device_name, parent=self, vis=vis)
                if panel:
                    try:
                        self._launched_panels.append(panel)
                    except Exception:
                        pass
                    self.statusBar().showMessage(
                        f"Started iTest Tab client for {device_name} in this window"
                    )
                    return
                else:
                    QMessageBox.warning(self, key, f"Failed to start iTest widget for {device_name}")
                    return

            # Map device server keys to client script paths
            client_paths = {
                "NETIO": "DeviceServers\\power\\netio\\DS_NETIO_client.py",
                "OWIS": "DeviceServers\\motion\\owis\\DS_OWIS_client.py",
                "STANDA": "DeviceServers\\motion\\standa\\DS_STANDA_client.py",
                "TOPDIRECT": "DeviceServers\\motion\\topdirect\\DS_TOPDIRECT_client.py",
                "BASLER": "DeviceServers\\cameras\\basler\\DS_BASLER_client.py",
                "LASER_POINTING": (
                    "DeviceServers\\control\\laser_pointing\\"
                    "DS_LASER_POINTING_client.py"
                ),
                "KEYSIGHT": (
                    "DeviceServers\\instruments\\keysight\\"
                    "DS_KEYSIGHT_33509B_client.py"
                ),
                "ITEST": (
                    "DeviceServers\\power\\iTest\\"
                    "DS_iTest_client.py"
                ),
                "ANDOR_CCD": "DeviceServers\\cameras\\andor\\DS_ANDOR_CCD_client.py",
                "AVANTES_CCD": (
                    "DeviceServers\\cameras\\avantes\\DS_AVANTES_CCD_client.py"
                ),
                "AVANTES_SPECTRO": (
                    "DeviceServers\\spectrographs\\avantes\\"
                    "DS_AVANTES_SPECTRO_client.py"
                ),
                "ARCHIVE": "DeviceServers\\data\\archive\\DS_ARCHIVE_client.py",
                "EXPERIMENT": (
                    "DeviceServers\\control\\experiment\\DS_Experiment_client.py"
                ),
                "DAQMX_ZMQ": (
                    "DeviceServers\\control\\daqmx\\DS_DAQmx_zmq_client.py"
                ),
            }

            if key not in client_paths:
                QMessageBox.warning(self, key, f"No client script configured for {key}")
                return

            # Build full path to client script
            pyconlyse_root = Path(
                main_app_path
            ).parent  # Go up from main_app to pyconlyse root
            client_script = pyconlyse_root / client_paths[key]

            if not client_script.exists():
                QMessageBox.warning(
                    self, key, f"Client script not found: {client_script}"
                )
                return

            # Determine python console executable (prefer CONDA env from PYCONLYSE_ENV)
            import os

            python_path: str | None = None
            env_name = os.environ.get("PYCONLYSE_ENV", "").strip()
            if env_name:
                try:
                    # Try to resolve conda environment path
                    # Method 1: Check if it's already a full path
                    if os.path.isabs(env_name) and os.path.exists(env_name):
                        env_dir = Path(env_name)
                    else:
                        # Method 2: Use conda info --envs to find the environment
                        result = subprocess.run(
                            ["conda", "info", "--envs"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        env_dir = None
                        if result.returncode == 0:
                            # Parse conda info output to find environment path
                            for line in result.stdout.splitlines():
                                if env_name in line and not line.startswith("#"):
                                    # Line format: "env_name    *    /path/to/env"
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[0] == env_name:
                                        env_path = parts[-1]  # Last part is the path
                                        if os.path.exists(env_path):
                                            env_dir = Path(env_path)
                                            break
                        
                        # Method 3: Try common conda paths if not found
                        if not env_dir:
                            # Try user conda envs directory
                            user_envs = Path.home() / ".conda" / "envs" / env_name
                            if user_envs.exists():
                                env_dir = user_envs
                            else:
                                # Try system conda envs
                                conda_prefix = os.environ.get("CONDA_PREFIX")
                                if conda_prefix:
                                    system_envs = Path(conda_prefix).parent / "envs" / env_name
                                    if system_envs.exists():
                                        env_dir = system_envs

                    # Look for python.exe in the environment directory
                    if env_dir and env_dir.exists():
                        env_python = env_dir / "python.exe"
                        if not env_python.exists():
                            # Fallback: some env layouts might place python under Scripts
                            alt_python = env_dir / "Scripts" / "python.exe"
                            if alt_python.exists():
                                env_python = alt_python
                        if env_python.exists():
                            python_path = str(env_python)
                except Exception:
                    python_path = None

            if not python_path:
                # Fallback to interpreter next to current executable, else current executable
                pyexe = Path(sys.executable)
                py_console = pyexe.with_name("python.exe")
                python_path = str(py_console if py_console.exists() else pyexe)

            # Build arguments for the new console process
            args = [python_path, str(client_script), selection]
            if vis != "FULL":
                args.append(vis)

            # Launch in a brand-new console window (Windows-specific)
            creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(args, cwd=str(pyconlyse_root), creationflags=creationflags)

            self.statusBar().showMessage(
                f"Started {key} ({selection}) in separate window"
            )

        except Exception as e:
            QMessageBox.critical(self, key, f"Failed to start {key}: {e}")


def main():
    # Use TaurusApplication like legacy code
    app = TaurusApplication(sys.argv, cmd_line_parser=None)
    app.setApplicationName("PYCONLYSE")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("PyConlyse Team")

    win = SimpleMainWindow()
    win.show()
    return app.exec_()
