"""Implementation for build_minimal_ui and related operations."""


def _bind_main_window_methods_build_minimal_ui(api):
    """Bind implementation to the owning module and its runtime state."""

    def build_minimal_ui(self):
        """Build a minimal window to appear instantly."""
        self.setWindowTitle("PyConlyse v2.0 - Control System (Starting...)")
        self.setGeometry(100, 100, 900, 600)

        # Minimal central widget
        minimal = api.QWidget()
        vbox = api.QVBoxLayout(minimal)
        label = api.QLabel("Starting PyConlyse... Initializing components in background.")
        label.setAlignment(api.Qt.AlignCenter)
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
        central_widget = api.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = api.QVBoxLayout(central_widget)

        # Create menu bar
        self.create_menu_bar()

        # Create main content area
        splitter = api.QSplitter(api.Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Controls and Status
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel - Logs
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([800, 400])

        api.logger.info("GUI setup completed")
        self._ui_ready = True

    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        exit_action = api.QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Infrastructure menu
        infra_menu = menubar.addMenu("&Infrastructure")

        start_infra_action = api.QAction("&Start Infrastructure", self)
        start_infra_action.triggered.connect(self.start_infrastructure)
        infra_menu.addAction(start_infra_action)

        stop_infra_action = api.QAction("S&top Infrastructure", self)
        stop_infra_action.triggered.connect(self.stop_infrastructure)
        infra_menu.addAction(stop_infra_action)

        # Device menu
        device_menu = menubar.addMenu("&Devices")

        start_all_action = api.QAction("Start &All Devices", self)
        start_all_action.triggered.connect(self.start_all_devices)
        device_menu.addAction(start_all_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = api.QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_left_panel(self) -> api.QWidget:
        """Create the left control panel."""
        panel = api.QWidget()
        layout = api.QVBoxLayout(panel)

        # Create management tabs
        self.management_tabs = api.QTabWidget()
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
        self.progress_bar = api.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Stretch
        layout.addStretch()
        return panel

    def create_overview_tab(self) -> api.QWidget:
        """Create the Overview tab: status, DB LED, starters, infra & quick device controls."""
        tab = api.QWidget()
        v = api.QVBoxLayout(tab)

        # Status indicators group
        status_group = api.QGroupBox("System Status")
        status_layout = api.QGridLayout(status_group)

        # Indicators
        self.status_indicators = {
            "system": api.StatusIndicator("System"),
            "database": api.StatusIndicator("Database"),
            "starter": api.StatusIndicator("Starter"),
            "tango_connectivity": api.StatusIndicator("Connectivity"),
        }

        row = 0
        for name, indicator in self.status_indicators.items():
            status_layout.addWidget(api.QLabel(f"{name.title()}:"), row, 0)
            status_layout.addWidget(indicator, row, 1)
            row += 1

        # DB LED row (tango_connectivity)
        db_led_row = api.QHBoxLayout()
        db_led_row.addWidget(api.QLabel("DB LED:"))
        self.db_led = api.LedIndicator()
        db_led_row.addWidget(self.db_led)
        db_led_row.addStretch()
        status_layout.addLayout(db_led_row, row, 0, 1, 2)

        v.addWidget(status_group)

        preparation_group = api.QGroupBox("Experiment Preparation")
        preparation_layout = api.QHBoxLayout(preparation_group)
        preparation_layout.addWidget(api.QLabel("Experiment:"))
        self.preparation_experiment_combo = api.QComboBox(preparation_group)
        self.preparation_experiment_combo.addItems(["V0", "VD2"])
        preparation_layout.addWidget(self.preparation_experiment_combo)
        self.prepare_experiment_btn = api.QPushButton("Prepare")
        self.prepare_experiment_btn.setToolTip(
            "Open the progress window, check required device servers, and start required equipment."
        )
        self.prepare_experiment_btn.clicked.connect(self.open_experiment_preparation)
        preparation_layout.addWidget(self.prepare_experiment_btn)
        preparation_layout.addStretch()
        v.addWidget(preparation_group)

        # Starters group
        starters_group = api.QGroupBox("Starters")
        starters_v = api.QVBoxLayout(starters_group)
        btn_row = api.QHBoxLayout()
        self.btn_refresh_starters = api.QPushButton("Refresh Starters")
        self.btn_refresh_starters.clicked.connect(self.refresh_starters)
        btn_row.addWidget(self.btn_refresh_starters)
        btn_row.addStretch()
        starters_v.addLayout(btn_row)

        self.starters_scroll = api.QScrollArea()
        self.starters_scroll.setWidgetResizable(True)
        self.starters_widget = api.QWidget()
        self.starters_layout = api.QVBoxLayout(self.starters_widget)
        self.starters_layout.addStretch()  # keep stretch at end
        self.starters_scroll.setWidget(self.starters_widget)
        starters_v.addWidget(self.starters_scroll)
        v.addWidget(starters_group)

        # Infrastructure controls
        infra_group = api.QGroupBox("Infrastructure Control")
        infra_layout = api.QVBoxLayout(infra_group)

        self.start_infra_btn = api.QPushButton("🚀 Start Infrastructure")
        self.start_infra_btn.clicked.connect(self.start_infrastructure)
        self.start_infra_btn.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 10px; }"
        )
        infra_layout.addWidget(self.start_infra_btn)

        self.stop_infra_btn = api.QPushButton("🛑 Stop Infrastructure")
        self.stop_infra_btn.clicked.connect(self.stop_infrastructure)
        self.stop_infra_btn.setStyleSheet(
            "QPushButton { font-size: 14px; padding: 10px; }"
        )
        self.stop_infra_btn.setEnabled(False)
        infra_layout.addWidget(self.stop_infra_btn)
        v.addWidget(infra_group)

        # Quick Device controls
        device_group = api.QGroupBox("Quick Device Server Control")
        device_layout = api.QVBoxLayout(device_group)

        self.start_basler_btn = api.QPushButton("📷 Start BASLER Camera")
        self.start_basler_btn.clicked.connect(
            lambda: self.start_device_server("BASLER", "V0")
        )
        device_layout.addWidget(self.start_basler_btn)

        self.start_standa_btn = api.QPushButton("🔧 Start STANDA Stage")
        self.start_standa_btn.clicked.connect(
            lambda: self.start_device_server("STANDA", "V0")
        )
        device_layout.addWidget(self.start_standa_btn)

        self.start_all_btn = api.QPushButton("🚀 Start All Devices")
        self.start_all_btn.clicked.connect(self.start_all_devices)
        self.start_all_btn.setStyleSheet(
            "QPushButton { font-size: 12px; padding: 8px; background-color: #4CAF50; color: white; }"
        )
        device_layout.addWidget(self.start_all_btn)
        v.addWidget(device_group)

        v.addStretch()
        return tab

    def open_experiment_preparation(self):
        """Open the shared web progress window for the selected experiment."""
        experiment = self.preparation_experiment_combo.currentText()
        if api.open_preparation_window(experiment):
            self.statusBar.showMessage(
                f"Opened {experiment} experiment preparation progress window"
            )
            return
        api.QMessageBox.warning(
            self,
            "Experiment Preparation",
            "Could not open the web preparation window. Check that a default browser is configured.",
        )

    def create_devices_tab(self) -> api.QWidget:
        """Create the DB devices tab that lists all devices from the Tango DB and allows opening control widgets."""
        tab = api.QWidget()
        v = api.QVBoxLayout(tab)

        # Controls
        ctrl = api.QHBoxLayout()
        self.btn_refresh_db_devices = api.QPushButton("Refresh Devices (DB)")
        self.btn_refresh_db_devices.clicked.connect(self.refresh_db_devices_list_async)
        ctrl.addWidget(self.btn_refresh_db_devices)

        self.btn_refresh_db_status = api.QPushButton("Refresh States")
        self.btn_refresh_db_status.clicked.connect(self.update_db_devices_status_async)
        ctrl.addWidget(self.btn_refresh_db_status)

        # Legacy map button
        self.btn_show_map = api.QPushButton("Show System Map")
        self.btn_show_map.clicked.connect(self.show_system_map)
        ctrl.addWidget(self.btn_show_map)

        ctrl.addStretch()
        v.addLayout(ctrl)

        # Scroll area with device rows
        self.db_devices_scroll = api.QScrollArea()
        self.db_devices_scroll.setWidgetResizable(True)
        self.db_devices_container = api.QWidget()
        self.db_devices_layout = api.QVBoxLayout(self.db_devices_container)
        self.db_devices_layout.addStretch()
        self.db_devices_scroll.setWidget(self.db_devices_container)
        v.addWidget(self.db_devices_scroll)

        # Map: device_name -> (led, state_label, open_btn)
        self.db_devices_widgets: api.Dict[str, tuple] = {}

        # Initial populate (async, so we do not block UI)
        if not api.OFFLINE_MODE:
            api.QTimer.singleShot(0, self.refresh_db_devices_list_async)

        return tab

    def create_device_clients_tab(self) -> api.QWidget:
        """Create a GUI similar to legacy to open control widgets for DS by type."""
        tab = api.QWidget()
        v = api.QVBoxLayout(tab)

        # Visualization type selection (if DSVisType available)
        if api.DSVisType is not None:
            vis_group = api.QGroupBox("Visualization Type")
            vis_layout = api.QHBoxLayout()
            for vt in api.DSVisType:
                rb = api.QPushButton(vt.value)
                rb.setCheckable(True)
                if vt == api.DSVisType.FULL:
                    rb.setChecked(True)

                def _mk_setter(val):
                    return lambda: self._set_client_vis(val)

                rb.clicked.connect(_mk_setter(vt))
                vis_layout.addWidget(rb)
            vis_layout.addStretch()
            vis_group.setLayout(vis_layout)
            v.addWidget(vis_group)

        # Controls row
        ctrl = api.QHBoxLayout()
        self.btn_refresh_clients = api.QPushButton("Refresh Device Lists")
        self.btn_refresh_clients.clicked.connect(self.refresh_device_clients_list_async)
        ctrl.addWidget(self.btn_refresh_clients)
        ctrl.addStretch()
        v.addLayout(ctrl)

        # Scroll area
        self.clients_scroll = api.QScrollArea()
        self.clients_scroll.setWidgetResizable(True)
        self._clients_tab = api.QWidget()
        self._clients_tab_layout = api.QVBoxLayout(self._clients_tab)
        self._clients_tab_layout.addStretch()
        self.clients_scroll.setWidget(self._clients_tab)
        v.addWidget(self.clients_scroll)

        # Build sections
        self._build_client_sections()

        # Initial populate
        api.QTimer.singleShot(0, self.refresh_device_clients_list_async)

        return tab

    def _set_client_vis(self, val):
        try:
            self._client_vis = val
        except Exception:
            self._client_vis = getattr(api.DSVisType, "FULL", None)

    def _client_configs(self):
        """Return list of client configurations: (key, display, keywords, launcher_fn_name, icon)."""
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
            row = api.QHBoxLayout()
            btn = api.QPushButton(display)
            try:
                btn.setIcon(QIcon(icon))
            except Exception:
                pass
            combo = api.QComboBox()
            combo.addItem("(loading...)")
            open_btn = api.QPushButton("Open")
            open_btn.clicked.connect(lambda _, k=key: self._open_selected_client(k))

            row.addWidget(btn)
            row.addWidget(combo)
            row.addWidget(open_btn)
            row.addStretch()
            cont = api.QWidget()
            cont.setLayout(row)
            self._clients_tab_layout.insertWidget(
                self._clients_tab_layout.count() - 1, cont
            )
            self._clients_sections[key] = {"container": cont, "combo": combo}

    def refresh_device_clients_list_async(self):
        """Fetch exported devices and categorize by DS keywords in background."""
        from main_app.core.config import OFFLINE_MODE

        if OFFLINE_MODE:
            # Offline placeholders - special handling for NETIO
            categorized = {key: [] for key, *_ in self._client_configs()}
            categorized["NETIO"] = ["V0", "VD2", "all"]  # NETIO instances
            self._apply_clients_device_map(categorized)
            return
        try:
            import concurrent.futures

            from tango import Database
        except Exception:
            categorized = {key: [] for key, *_ in self._client_configs()}
            categorized["NETIO"] = ["V0", "VD2", "all"]  # NETIO instances
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
                    if key == "NETIO":
                        # Special handling for NETIO - show instances based on available devices
                        netio_devices = [
                            n
                            for n, ln in lower_names
                            if any(kw in ln for kw in keywords)
                        ]
                        if netio_devices:
                            # Always offer all instances if any NETIO devices exist
                            out[key] = ["V0", "VD2", "all"]
                        else:
                            out[key] = []
                    else:
                        for n, ln in lower_names:
                            if any(kw in ln for kw in keywords):
                                out[key].append(n)
                # Sort (except NETIO which has predefined order)
                for k in out:
                    if k != "NETIO":
                        out[k] = sorted(out[k])
                return out
            except Exception:
                categorized = {key: [] for key, *_ in self._client_configs()}
                categorized["NETIO"] = ["V0", "VD2", "all"]  # NETIO fallback
                return categorized

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_fetch)

        def _done(_f):
            try:
                categorized = _f.result(timeout=0) or {}
            except Exception:
                categorized = {key: [] for key, *_ in self._client_configs()}
                categorized["NETIO"] = ["V0", "VD2", "all"]  # NETIO fallback
            api.QTimer.singleShot(
                0, lambda d=categorized: self._apply_clients_device_map(d)
            )
            try:
                ex.shutdown(wait=False)
            except Exception:
                pass

        fut.add_done_callback(_done)

    def _apply_clients_device_map(self, categorized: api.Dict[str, list]):
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
        selection = combo.currentText()
        try:
            from main_app.ui import widget_launchers as wl

            # Map key -> launcher function
            fn_map = {
                "NETIO": wl.start_netio_client,  # Updated to use client approach
                "OWIS": wl.start_owis_widget,
                "STANDA": wl.start_standa_widget,
                "TOPDIRECT": wl.start_topdirect_widget,
                "BASLER": wl.start_basler_widget,
                "LASER_POINTING": wl.start_laser_pointing_widget,
                "KEYSIGHT": wl.start_keysight_widget,
            }
            vis = (
                self._client_vis.value if hasattr(self._client_vis, "value") else "FULL"
            )
            # Launch
            w = None
            if key == "NETIO":
                # For NETIO, selection is an instance (V0, VD2, all)
                w = fn_map[key](instance=selection, parent=None, vis=vis)
            elif key in ("LASER_POINTING", "BASLER", "STANDA", "TOPDIRECT", "KEYSIGHT"):
                # For these, selection is a device name
                w = fn_map[key](selection, parent=None, vis=vis)
            elif key == "OWIS":
                # OWIS may auto-detect axes if not provided
                w = fn_map[key](selection, axes=None, parent=None, vis=vis)
            if w is not None:
                self._launched_widgets.append(w)
        except Exception as e:
            api.QMessageBox.critical(
                self, "Client", f"Failed to open widget for {key}: {e}"
            )

    def create_deviceservers_tab(self) -> api.QWidget:
        """Create the DeviceServers management tab"""
        tab = api.QWidget()
        v = api.QVBoxLayout(tab)

        # Controls row
        ctrl = api.QHBoxLayout()
        self.btn_refresh_ds = api.QPushButton("Refresh List")
        self.btn_refresh_ds.clicked.connect(self.on_refresh_deviceservers_clicked)
        ctrl.addWidget(self.btn_refresh_ds)

        self.btn_refresh_ds_status = api.QPushButton("Refresh Status")
        self.btn_refresh_ds_status.clicked.connect(self.update_deviceservers_status)
        ctrl.addWidget(self.btn_refresh_ds_status)

        self.btn_start_all_servers = api.QPushButton("Start All Configured")
        self.btn_start_all_servers.clicked.connect(self.start_all_devices)
        ctrl.addWidget(self.btn_start_all_servers)
        self.btn_stop_all_servers = api.QPushButton("Stop All Running")
        self.btn_stop_all_servers.clicked.connect(self.stop_all_running_devices)
        ctrl.addWidget(self.btn_stop_all_servers)
        ctrl.addStretch()
        v.addLayout(ctrl)

        # Scroll list
        self.ds_scroll = api.QScrollArea()
        self.ds_scroll.setWidgetResizable(True)
        self.ds_list_container = api.QWidget()
        self.ds_list_layout = api.QVBoxLayout(self.ds_list_container)
        self.ds_list_layout.addStretch()
        self.ds_scroll.setWidget(self.ds_list_container)
        v.addWidget(self.ds_scroll)

        # Map of ds key -> (led,label)
        self.ds_status_widgets: api.Dict[str, tuple] = {}

        # Initial build (defer to avoid UI blocking)
        api.QTimer.singleShot(0, self.rebuild_deviceservers_list)
        api.QTimer.singleShot(500, self.update_deviceservers_status)

        return tab

    return {
        "build_minimal_ui": build_minimal_ui,
        "setup_ui": setup_ui,
        "create_menu_bar": create_menu_bar,
        "create_left_panel": create_left_panel,
        "create_overview_tab": create_overview_tab,
        "open_experiment_preparation": open_experiment_preparation,
        "create_devices_tab": create_devices_tab,
        "create_device_clients_tab": create_device_clients_tab,
        "_set_client_vis": _set_client_vis,
        "_client_configs": _client_configs,
        "_build_client_sections": _build_client_sections,
        "refresh_device_clients_list_async": refresh_device_clients_list_async,
        "_apply_clients_device_map": _apply_clients_device_map,
        "_open_selected_client": _open_selected_client,
        "create_deviceservers_tab": create_deviceservers_tab,
    }
