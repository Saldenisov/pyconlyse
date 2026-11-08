"""Implementation for _build_menu and related operations."""


def _bind_simple_main_window_methods_build_menu(api):
    """Bind implementation to the owning module and its runtime state."""

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        exit_action = api.QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Config menu
        cfg_menu = menubar.addMenu("&Config")
        edit_cfg_action = api.QAction("Edit Device Clients Config...", self)
        edit_cfg_action.triggered.connect(self.edit_device_clients_config)
        cfg_menu.addAction(edit_cfg_action)

        populate_action = api.QAction("Populate Device Lists from Tango DB", self)
        populate_action.setShortcut(api.QKeySequence("Ctrl+R"))
        populate_action.triggered.connect(self.populate_clients_from_db)
        cfg_menu.addAction(populate_action)

        # Clients menu with shortcuts
        clients_menu = menubar.addMenu("&Clients")

        act_netio = api.QAction("Start NETIO", self)
        act_netio.setShortcut(api.QKeySequence("Ctrl+N"))
        act_netio.triggered.connect(lambda: self._launch_client("NETIO"))
        clients_menu.addAction(act_netio)

        act_owis = api.QAction("Start OWIS", self)
        act_owis.setShortcut(api.QKeySequence("Ctrl+O"))
        act_owis.triggered.connect(lambda: self._launch_client("OWIS"))
        clients_menu.addAction(act_owis)

        act_standa = api.QAction("Start STANDA", self)
        act_standa.setShortcut(api.QKeySequence("Ctrl+S"))
        act_standa.triggered.connect(lambda: self._launch_client("STANDA"))
        clients_menu.addAction(act_standa)

        act_topdirect = api.QAction("Start TOPDIRECT", self)
        act_topdirect.setShortcut(api.QKeySequence("Ctrl+T"))
        act_topdirect.triggered.connect(lambda: self._launch_client("TOPDIRECT"))
        clients_menu.addAction(act_topdirect)

        act_basler = api.QAction("Start BASLER", self)
        act_basler.setShortcut(api.QKeySequence("Ctrl+B"))
        act_basler.triggered.connect(lambda: self._launch_client("BASLER"))
        clients_menu.addAction(act_basler)

        act_laser = api.QAction("Start LASER POINTING", self)
        act_laser.setShortcut(api.QKeySequence("Ctrl+L"))
        act_laser.triggered.connect(lambda: self._launch_client("LASER_POINTING"))
        clients_menu.addAction(act_laser)

        act_itest = api.QAction("Start iTest PSU", self)
        act_itest.setShortcut(api.QKeySequence("Ctrl+I"))
        act_itest.triggered.connect(lambda: self._launch_client("ITEST"))
        clients_menu.addAction(act_itest)

        act_spectroscopy = api.QAction("Start Spectroscopy", self)
        act_spectroscopy.setShortcut(api.QKeySequence("Ctrl+P"))
        act_spectroscopy.triggered.connect(lambda: self._launch_client("SPECTROSCOPY"))
        clients_menu.addAction(act_spectroscopy)

        clients_menu.addSeparator()
        act_astor = api.QAction("Start Astor", self)
        act_astor.setShortcut(api.QKeySequence("Ctrl+A"))
        act_astor.triggered.connect(self._launch_astor)
        clients_menu.addAction(act_astor)

    def _build_clients_ui(self):
        # Ensure config
        self.config_path = api.main_app_path / "config" / "device_clients.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._defaults = {
            # Instance/config names matching legacy cbox items (from DS_*_client.py)
            "NETIO": ["all", "V0", "VD2"],
            "OWIS": ["V0", "VD2", "all"],
            "ZABER": ["VD2"],
            "STANDA": ["alignment", "V0", "V0_short", "ELYSE", "OPA"],
            "TOPDIRECT": ["VD2", "all"],
            "BASLER": ["V0", "Cam1", "Cam2", "Cam3", "all"],
            "LASER_POINTING": ["Cam1", "Cam2", "Cam3", "V0", "3P"],
            "KEYSIGHT": ["laser"],
            "ITEST": ["ELYSE", "ITestPSU/test", "ITestPSU/bilt", "ITestPSU/lab", "ITestPSU/main"],
            "DAQMX": ["TRANCON-DAQ"],
            "DAQMX_ZMQ": ["DAQMX_ZMQ_1"],
            "SPECTROSCOPY": ["V0"],
            # Additional clients (not shown in UI rows yet)
            "ANDOR_CCD": [],
            "ANDOR_SPECTROGRAPH": [],
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
                "VD2": "VD2 sample holder: OWIS axis 2 (Aggregator / Ethernet backend)",
                "all": (
                    "All Delay Lines: axes 1,2,3 from DS_OWIS_PS90_IP + axis 4 "
                    "from DS_OWIS_PS90"
                ),
            },
            "ZABER": {"VD2": "VD2 source-selection mirror on Elysium2 (millimetres)"},
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
            "DAQMX": {
                "TRANCON-DAQ": "Direct local PCIe-6320 controls: control/DAQ/TRANCON-DAQ",
            },
            "DAQMX_ZMQ": {
                "DAQMX_ZMQ_1": "DAQmx ZMQ Reader: control/DAQ/DAQMX_ZMQ_1 (receives from LabVIEW PSP)",
            },
            "SPECTROSCOPY": {
                "V0": "Newton CCD together with Shamrock and Kymera controls",
            },
        }
        # Try to derive instance lists from installed client modules
        self._update_defaults_from_clients()
        self._config = self._load_clients_config()

        # Icons directory (absolute)
        self.icons_dir = api.main_app_path.parent / "bin" / "icons"
        # DS rows definition: key, display, icon, launcher key
        self._ds_rows_def = [
            ("NETIO", "NETIO", self.icons_dir / "NETIO.png", "client"),
            ("OWIS", "OWIS", self.icons_dir / "OWIS.svg", "widget"),
            ("ZABER", "Zaber", self.icons_dir / "OWIS.svg", "client"),
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
                "DAQMX",
                "DAQmx",
                self.icons_dir / "NETIO.png",
                "client",
            ),
            (
                "DAQMX_ZMQ",
                "DAQmx ZMQ",
                self.icons_dir / "NETIO.png",
                "client",
            ),
            (
                "SPECTROSCOPY",
                "Spectroscopy",
                self.icons_dir / "spectrometer.png",
                "client",
            ),
        ]

        self.client_rows: api.Dict[str, api.Dict[str, api.QWidget]] = {}
        self._launched_panels: api.List[api.QWidget] = []

        preparation_group = api.QGroupBox("Experiment Preparation")
        preparation_layout = api.QHBoxLayout(preparation_group)
        preparation_layout.addWidget(api.QLabel("Experiment:"))
        self.preparation_experiment_combo = api.QComboBox(preparation_group)
        self.preparation_experiment_combo.addItems(["V0", "VD2"])
        preparation_layout.addWidget(self.preparation_experiment_combo)
        prepare_button = api.QPushButton("Prepare", preparation_group)
        prepare_button.setToolTip(
            "Open the progress window, check required device servers, and start required equipment."
        )
        prepare_button.clicked.connect(self._open_experiment_preparation)
        preparation_layout.addWidget(prepare_button)
        preparation_layout.addStretch()
        self.clients_layout.addWidget(preparation_group)

        # Visualization type selection (legacy style)
        vis_group = api.QGroupBox("Type")
        vis_layout = api.QHBoxLayout(vis_group)
        if api.DSVisType is not None:
            for vt in api.DSVisType:
                rb = api.QPushButton(vt.value)
                rb.setCheckable(True)
                if vt == api.DSVisType.FULL:
                    rb.setChecked(True)

                def _mk(v):
                    return lambda: self._set_vis(v)

                rb.clicked.connect(_mk(vt))
                vis_layout.addWidget(rb)
        vis_layout.addStretch()
        self.clients_layout.addWidget(vis_group)

        # DS rows - 2 column grid layout
        grid = api.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(5)

        for idx, (key, display, icon, kind) in enumerate(self._ds_rows_def):
            row = idx // 2
            col = idx % 2

            # Use TaurusCommandButton like legacy
            btn = api.TaurusCommandButton(text=display, parent=self.clients_tab)
            try:
                btn.setIcon(api.QIcon(str(icon)))
            except Exception:
                pass
            combo = api.TaurusValueComboBox(parent=self.clients_tab)
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
        grid_container = api.QWidget()
        grid_container.setLayout(grid)
        self.clients_layout.addWidget(grid_container)

        # Add Astor button at the end
        astor_row = api.QHBoxLayout()
        astor_btn = api.TaurusCommandButton(text="Astor", parent=self.clients_tab)
        try:
            astor_btn.setIcon(api.QIcon(str(self.icons_dir / "main_icon.png")))
        except Exception:
            pass
        astor_btn.clicked.connect(self._launch_astor)
        astor_row.addWidget(astor_btn)
        astor_row.addStretch()
        astor_cont = api.QWidget()
        astor_cont.setLayout(astor_row)
        self.clients_layout.addWidget(astor_cont)

    def _build_devices_ui(self):
        # Controls
        ctrl = api.QHBoxLayout()
        self.btn_refresh_devices = api.QPushButton("Refresh Devices (ELYSE, manip)")
        self.btn_refresh_devices.clicked.connect(self.refresh_devices_async)
        ctrl.addWidget(self.btn_refresh_devices)

        self.btn_update_states = api.QPushButton("Update States")
        self.btn_update_states.clicked.connect(self.update_device_states_async)
        ctrl.addWidget(self.btn_update_states)

        ctrl.addStretch()
        self.devices_layout.addLayout(ctrl)

        # Scroll for devices grid
        self.devices_scroll = api.QScrollArea()
        self.devices_scroll.setWidgetResizable(True)
        self.devices_container = api.QWidget()
        self.devices_grid = api.QGridLayout(self.devices_container)
        self.devices_grid.setColumnStretch(2, 1)
        self.devices_scroll.setWidget(self.devices_container)
        self.devices_layout.addWidget(self.devices_scroll)

        self.device_widgets: api.Dict[str, api.Tuple[api.LedIndicator, api.QLabel]] = {}

    def _set_vis(self, val):
        try:
            self._client_vis = val
        except Exception:
            self._client_vis = getattr(api.DSVisType, "FULL", None)

    def _open_experiment_preparation(self):
        experiment = self.preparation_experiment_combo.currentText()
        if api.open_preparation_window(experiment):
            self.statusBar().showMessage(
                f"Opened {experiment} experiment preparation progress window"
            )
            return
        api.QMessageBox.warning(
            self,
            "Experiment Preparation",
            "Could not open the web preparation window. Check that a default browser is configured.",
        )

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
            api.QMessageBox.warning(
                self,
                "Astor",
                (
                    "Could not launch Astor. Please check if Tango is "
                    "installed and Astor is available."
                ),
            )

        except Exception as e:
            api.QMessageBox.critical(self, "Astor", f"Failed to launch Astor: {e}")

    def _deferred_startup(self):
        # No DS list to populate
        self.statusBar().showMessage("Ready")

    def _load_clients_config(self) -> api.Dict[str, api.List[str]]:
        try:
            if self.config_path.exists():
                with self.config_path.open("r", encoding="utf-8") as f:
                    data = api.json.load(f)
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

    def _save_clients_config(self, data: api.Dict[str, api.List[str]]):
        try:
            with self.config_path.open("w", encoding="utf-8") as f:
                api.json.dump(data, f, indent=2)
        except Exception as e:
            api.QMessageBox.warning(self, "Config", f"Failed to save config: {e}")

    def _update_defaults_from_clients(self):
        """Update defaults from DS client modules' `layouts` if available."""
        import importlib

        module_map = {
            "NETIO": "DeviceServers.power.netio.DS_NETIO_client",
            "OWIS": "DeviceServers.motion.owis.DS_OWIS_client",
            "ZABER": "DeviceServers.motion.zaber.DS_Zaber_client",
            "STANDA": "DeviceServers.motion.standa.DS_STANDA_client",
            "TOPDIRECT": "DeviceServers.motion.topdirect.DS_TOPDIRECT_client",
            "BASLER": "DeviceServers.cameras.basler.DS_BASLER_client",
            "LASER_POINTING": (
                "DeviceServers.control.laser_pointing.DS_LASER_POINTING_client"
            ),
            "SPECTROSCOPY": "DeviceServers.spectroscopy.DS_SPECTROSCOPY_client",
            "ANDOR_CCD": "DeviceServers.cameras.andor.DS_ANDOR_CCD_client",
            "ANDOR_SPECTROGRAPH": (
                "DeviceServers.spectrographs.andor.DS_ANDOR_SPECTROGRAPH_client"
            ),
            "AVANTES_CCD": "DeviceServers.cameras.avantes.DS_AVANTES_CCD_client",
            "AVANTES_SPECTRO": (
                "DeviceServers.spectrographs.avantes.DS_AVANTES_SPECTRO_client"
            ),
            "ARCHIVE": "DeviceServers.data.archive.DS_ARCHIVE_client",
            "EXPERIMENT": "DeviceServers.control.experiment.DS_Experiment_client",
            "ITEST": "DeviceServers.power.iTest.DS_iTest_client",
            "DAQMX": "DeviceServers.control.daqmx.DS_DAQmx_client",
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
            combo: api.QComboBox = refs.get("combo")  # type: ignore
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
        dlg = api.QDialog(self)
        dlg.setWindowTitle("Edit Device Clients Config")
        dlg.resize(600, 500)
        vbox = api.QVBoxLayout(dlg)
        info = api.QLabel(
            (
                "Edit JSON mapping: "
                "{ 'NETIO': ['ALL','V0',...], 'OWIS': ['device1', ...], ... }"
            )
        )
        info.setWordWrap(True)
        vbox.addWidget(info)
        editor = api.QPlainTextEdit()
        try:
            text = api.json.dumps(self._config, indent=2)
        except Exception:
            text = "{}"
        editor.setPlainText(text)
        vbox.addWidget(editor)
        btn_row = api.QHBoxLayout()
        btn_save = api.QPushButton("Save")
        btn_cancel = api.QPushButton("Cancel")
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        def on_save():
            try:
                data = api.json.loads(editor.toPlainText())
                if not isinstance(data, dict):
                    raise ValueError(
                        "Top-level must be a JSON object mapping keys to lists"
                    )
                # Normalize: keep only known keys as lists of strings
                norm: api.Dict[str, api.List[str]] = {}
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
                api.QMessageBox.critical(dlg, "Error", f"Invalid JSON: {e}")

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec_()

    def populate_clients_from_db(self):
        # Scan Tango DB and populate selection lists for DS (except NETIO)
        try:
            from main_app.core.config import OFFLINE_MODE as OM

            if OM:
                api.QMessageBox.information(
                    self, "Populate", "OFFLINE_MODE is enabled; cannot query DB."
                )
                return
            from tango import Database
        except Exception as e:
            api.QMessageBox.warning(self, "Populate", f"Cannot access Tango Database: {e}")
            return

        try:
            db = Database()
            names: api.List[str] = []
            for prefix in ("ELYSE", "manip"):
                try:
                    names.extend(list(db.get_device_exported(f"{prefix}*")))
                except Exception:
                    continue
            lower_names = [(n, n.lower()) for n in set(names)]

            # Categorize by keywords
            def match(keywords: api.List[str]) -> api.List[str]:
                out = []
                for n, ln in lower_names:
                    if any(kw in ln for kw in keywords):
                        out.append(n)
                return sorted(out)

            # Note: With instance-based configs, DB population is less useful
            # But we can still detect presence and suggest appropriate instances
            categories = {
                "OWIS": ["V0", "VD2", "all"] if match(["owis", "delay"]) else [],
                "ZABER": ["VD2"] if match(["zaber"]) else [],
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
            api.QMessageBox.critical(self, "Populate", f"Failed to populate from DB: {e}")

    return {
        "_build_menu": _build_menu,
        "_build_clients_ui": _build_clients_ui,
        "_build_devices_ui": _build_devices_ui,
        "_set_vis": _set_vis,
        "_open_experiment_preparation": _open_experiment_preparation,
        "_auto_resize_window": _auto_resize_window,
        "_launch_astor": _launch_astor,
        "_deferred_startup": _deferred_startup,
        "_load_clients_config": _load_clients_config,
        "_save_clients_config": _save_clients_config,
        "_update_defaults_from_clients": _update_defaults_from_clients,
        "_refresh_client_combos_from_config": _refresh_client_combos_from_config,
        "edit_device_clients_config": edit_device_clients_config,
        "populate_clients_from_db": populate_clients_from_db,
    }
