"""Implementation for auto_start_tango_infrastructure and related operations."""


def _bind_main_control_methods_auto_start_tango_infrastructure(api):
    """Bind implementation to the owning module and its runtime state."""

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
                        api.logger.info("Tango infrastructure detected as already running")
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
                        api.QTimer.singleShot(
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
                            api.QTimer.singleShot(
                                15000, self.auto_configure_astor
                            )  # 15 seconds delay
                        else:
                            self.log_message("❌ Failed to start Tango infrastructure")
                            self.status_label.setText("Tango Start Failed")
                            self.status_label.setStyleSheet(
                                "QLabel { color: red; font-weight: bold; }"
                            )

                except Exception as e:
                    api.logger.error(f"Error during Tango check/start: {e}")
                    self.log_message(f"Error checking Tango status: {e}")
                    self.status_label.setText("Tango Check Error")
                    self.status_label.setStyleSheet(
                        "QLabel { color: red; font-weight: bold; }"
                    )

            # Delay check by 2 seconds to allow UI to fully load
            api.QTimer.singleShot(2000, delayed_check)

        except Exception as e:
            api.logger.error(f"Error in auto_start_tango_infrastructure: {e}")
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
            api.logger.debug(f"Error checking Starter process: {e}")
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
            result = api.subprocess.run(
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

            astor_process = api.subprocess.Popen(
                astor_cmd,
                cwd=str(self.tango_manager.bin_path),
                shell=True,
                stdout=api.subprocess.PIPE,
                stderr=api.subprocess.PIPE,
                text=True,
            )

            self.tango_manager.processes["astor"] = astor_process
            self.log_message("✓ Astor GUI started")

        except Exception as e:
            api.logger.error(f"Error starting Astor: {e}")
            self.log_message(f"Error starting Astor: {e}")

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("PYCONLYSE Control Center v2.0")
        self.setWindowIcon(api.QIcon("icons/main_icon.png"))
        self.setMinimumSize(800, 600)

        # Main layout
        main_layout = api.QVBoxLayout()

        # Create toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # Create main content with splitter
        splitter = api.QSplitter()

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

    def create_toolbar(self) -> api.QWidget:
        """Create the main toolbar with system controls"""
        toolbar_frame = api.QFrame()
        toolbar_frame.setFrameStyle(api.QFrame.StyledPanel)
        toolbar_layout = api.QHBoxLayout()

        # Tango Infrastructure Controls
        tango_group = api.QGroupBox("Tango Infrastructure")
        tango_layout = api.QHBoxLayout()

        self.btn_start_tango = api.QPushButton("Start Tango")
        self.btn_start_tango.setIcon(api.QIcon("icons/DL.svg"))
        self.btn_start_tango.clicked.connect(self.start_tango_infrastructure)

        self.btn_stop_tango = api.QPushButton("Stop Tango")
        self.btn_stop_tango.setIcon(api.QIcon("icons/rect20454.png"))
        self.btn_stop_tango.clicked.connect(self.stop_tango_infrastructure)
        self.btn_stop_tango.setEnabled(False)

        self.btn_configure_astor = api.QPushButton("Configure Astor")
        self.btn_configure_astor.setIcon(api.QIcon("icons/experiment.svg"))
        self.btn_configure_astor.clicked.connect(self.configure_astor)

        tango_layout.addWidget(self.btn_start_tango)
        tango_layout.addWidget(self.btn_stop_tango)
        tango_layout.addWidget(self.btn_configure_astor)
        tango_group.setLayout(tango_layout)

        # Client Management Controls
        client_group = api.QGroupBox("Client Management")
        client_layout = api.QHBoxLayout()

        self.btn_close_all_clients = api.QPushButton("Close All Clients")
        self.btn_close_all_clients.setIcon(api.QIcon("icons/close.png"))
        self.btn_close_all_clients.clicked.connect(self.close_all_clients)

        self.btn_show_clients = api.QPushButton("Show Active")
        self.btn_show_clients.setIcon(api.QIcon("icons/info.png"))
        self.btn_show_clients.clicked.connect(self.show_active_clients)

        client_layout.addWidget(self.btn_close_all_clients)
        client_layout.addWidget(self.btn_show_clients)
        client_group.setLayout(client_layout)

        # Status indicator
        self.status_label = api.QLabel("System Ready")
        self.status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")

        toolbar_layout.addWidget(tango_group)
        toolbar_layout.addWidget(client_group)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.status_label)

        toolbar_frame.setLayout(toolbar_layout)
        return toolbar_frame

    def create_tabs(self) -> api.QTabWidget:
        """Create the main tab widget"""
        tabs = api.QTabWidget()

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

    def create_clients_tab(self) -> api.QWidget:
        """Create the device clients tab"""
        tab = api.QWidget()
        layout = api.QVBoxLayout()

        # Visualization type selection
        vis_group = api.QGroupBox("Visualization Type")
        vis_layout = api.QHBoxLayout()

        for vis_type in api.VisType:
            rb = api.QtWidgets.QRadioButton(text=vis_type.value)
            if vis_type == api.VisType.FULL:
                rb.setChecked(True)
            rb.toggled.connect(api.partial(self.on_vis_type_changed, vis_type.value))
            vis_layout.addWidget(rb)

        vis_group.setLayout(vis_layout)
        layout.addWidget(vis_group)

        # Device client controls
        scroll_area = api.QScrollArea()
        clients_widget = api.QWidget()
        clients_layout = api.QVBoxLayout()

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
        separator = api.QFrame()
        separator.setFrameShape(api.QFrame.HLine)
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
        self, device_type: str, instances: api.List[str], icon_name: str
    ) -> api.QWidget:
        """Create a device client control section"""
        section = api.QFrame()
        section.setFrameStyle(api.QFrame.StyledPanel)
        layout = api.QHBoxLayout()

        # Button
        button = api.TaurusCommandButton(text=device_type, parent=self)
        try:
            button.setIcon(api.QIcon(f"icons/{icon_name}"))
        except:
            pass  # Icon not found, continue without

        # Combo box
        combo = api.TaurusValueComboBox(parent=self)
        combo.addItems(instances)

        # Connect button
        button.clicked.connect(api.partial(self.start_client, device_type, combo))

        layout.addWidget(button)
        layout.addWidget(combo)
        layout.addStretch()

        section.setLayout(layout)
        return section

    def create_lights_section(self) -> api.QWidget:
        """Create the lights control section"""
        section = api.QFrame()
        section.setFrameStyle(api.QFrame.StyledPanel)
        layout = api.QHBoxLayout()

        layout.addWidget(api.QLabel("Room Controls:"))

        # Light and laser buttons
        self.btn_light_room = api.TaurusCommandButton(text="SM Light", parent=self)
        self.btn_light_room.setIcon(api.QIcon("icons/light.png"))
        self.btn_light_room.clicked.connect(api.partial(self.toggle_rpi_pin, 3))

        self.btn_laser = api.TaurusCommandButton(text="Laser", parent=self)
        self.btn_laser.setIcon(api.QIcon("icons/laser.svg"))
        self.btn_laser.setEnabled(False)  # Disabled by default for safety
        self.btn_laser.clicked.connect(api.partial(self.toggle_rpi_pin, 4))

        layout.addWidget(self.btn_light_room)
        layout.addWidget(self.btn_laser)

        # Safety note
        note_label = api.QLabel("Press 'q' to enable laser button")
        note_label.setStyleSheet("QLabel { color: orange; font-style: italic; }")
        layout.addWidget(note_label)

        layout.addStretch()
        section.setLayout(layout)
        return section

    def create_devices_tab(self) -> api.QWidget:
        """Create the devices status tab"""
        tab = api.QWidget()
        layout = api.QVBoxLayout()

        # Map button
        self.btn_show_map = api.QPushButton("Show System Map")
        self.btn_show_map.setIcon(api.QIcon("icons/layout.svg"))
        self.btn_show_map.clicked.connect(self.show_system_map)
        layout.addWidget(self.btn_show_map)

        # Device status grid
        scroll_area = api.QScrollArea()
        self.devices_widget = api.QWidget()
        self.devices_layout = api.QGridLayout()
        self.devices_widget.setLayout(self.devices_layout)
        scroll_area.setWidget(self.devices_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        tab.setLayout(layout)
        return tab

    def create_elyse_tab(self) -> api.QWidget:
        """Create the ELYSE control tab"""
        tab = api.QWidget()
        layout = api.QVBoxLayout()

        self.elyse_tabs = api.QTabWidget()
        layout.addWidget(self.elyse_tabs)

        tab.setLayout(layout)
        return tab

    def create_deviceservers_tab(self) -> api.QWidget:
        """Create the DeviceServers management tab"""
        tab = api.QWidget()
        layout = api.QVBoxLayout()

        # Control buttons
        controls_layout = api.QHBoxLayout()

        self.btn_refresh_servers = api.QPushButton("Refresh Status")
        self.btn_refresh_servers.clicked.connect(self.refresh_deviceserver_status)

        self.btn_start_all_servers = api.QPushButton("Start All Configured")
        self.btn_start_all_servers.clicked.connect(self.start_all_deviceservers)

        self.btn_stop_all_servers = api.QPushButton("Stop All")
        self.btn_stop_all_servers.clicked.connect(self.stop_all_deviceservers)

        controls_layout.addWidget(self.btn_refresh_servers)
        controls_layout.addWidget(self.btn_start_all_servers)
        controls_layout.addWidget(self.btn_stop_all_servers)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # DeviceServer status area
        scroll_area = api.QScrollArea()
        self.servers_widget = api.QWidget()
        self.servers_layout = api.QVBoxLayout()
        self.servers_widget.setLayout(self.servers_layout)
        scroll_area.setWidget(self.servers_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)

        # Initialize server status display
        self.update_deviceserver_display()

        tab.setLayout(layout)
        return tab

    def create_status_panel(self) -> api.QWidget:
        """Create the status and logs panel"""
        panel = api.QWidget()
        layout = api.QVBoxLayout()

        # Status section
        status_group = api.QGroupBox("System Status")
        status_layout = api.QVBoxLayout()

        self.tango_status_label = api.QLabel("Tango: Not Started")
        self.tango_db_label = api.QLabel("Database: Not Started")
        self.tango_starter_label = api.QLabel("Starter: Not Started")
        self.tango_astor_label = api.QLabel("Astor: Not Started")
        self.deviceservers_status_label = api.QLabel("DeviceServers: 0 running")

        status_layout.addWidget(self.tango_status_label)
        status_layout.addWidget(self.tango_db_label)
        status_layout.addWidget(self.tango_starter_label)
        status_layout.addWidget(self.tango_astor_label)
        status_layout.addWidget(self.deviceservers_status_label)
        status_group.setLayout(status_layout)

        # Logs section
        logs_group = api.QGroupBox("Activity Logs")
        logs_layout = api.QVBoxLayout()

        self.log_display = api.QTextEdit()
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
        self.status_timer = api.QTimer()
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
            self.device_monitor_thread = api.DeviceMonitorThread([])
            self.device_monitor_thread.device_state_changed.connect(
                self.on_device_state_changed
            )
            self.device_monitor_thread.start()

            # Start ELYSE data thread
            self.elyse_data_thread = api.ElyseDataThread()
            self.elyse_data_thread.data_signal.connect(self.on_elyse_data_received)
            self.elyse_data_thread.start()

            self.populate_device_status()

        except Exception as e:
            api.logger.error(f"Failed to start monitoring: {e}")
            self.log_message(f"Warning: Monitoring not available - {e}")

    def populate_device_status(self):
        """Populate the device status display with timeout protection"""

        def _populate_devices():
            try:
                db = api.Database()
                servers = ["ELYSE", "manip"]
                devices = []
                for server in servers:
                    devices.extend(list(db.get_device_exported(f"{server}*")))
                return devices
            except Exception as e:
                api.logger.warning(f"Could not get device list: {e}")
                return []

        try:
            # Use timeout for device list retrieval
            with api.concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
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
                label = api.MyQLabel(device_name)
                label.clicked.connect(
                    api.partial(self.on_device_label_clicked, device_name)
                )
                self.device_labels[device_name] = label

                self.devices_layout.addWidget(label, row, col)
                col += 1
                if col >= columns:
                    col = 0
                    row += 1

            api.logger.info(f"Populated device status with {len(devices)} devices")

        except api.concurrent.futures.TimeoutError:
            api.logger.warning("Device list population timed out")
            self.log_message("Warning: Device list loading timed out")
        except Exception as e:
            api.logger.error(f"Failed to populate device status: {e}")
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

    return {
        "auto_start_tango_infrastructure": auto_start_tango_infrastructure,
        "_check_starter_running": _check_starter_running,
        "_start_astor_if_needed": _start_astor_if_needed,
        "setup_ui": setup_ui,
        "create_toolbar": create_toolbar,
        "create_tabs": create_tabs,
        "create_clients_tab": create_clients_tab,
        "create_device_client_section": create_device_client_section,
        "create_lights_section": create_lights_section,
        "create_devices_tab": create_devices_tab,
        "create_elyse_tab": create_elyse_tab,
        "create_deviceservers_tab": create_deviceservers_tab,
        "create_status_panel": create_status_panel,
        "setup_connections": setup_connections,
        "start_monitoring": start_monitoring,
        "populate_device_status": populate_device_status,
        "update_deviceserver_display": update_deviceserver_display,
    }
