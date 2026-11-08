"""Implementation for create_right_panel and related operations."""


def _bind_main_window_methods_create_right_panel(api):
    """Bind implementation to the owning module and its runtime state."""

    def create_right_panel(self) -> api.QWidget:
        """Create the right log panel."""
        panel = api.QWidget()
        layout = api.QVBoxLayout(panel)

        # Log viewer
        log_label = api.QLabel("System Logs")
        log_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(log_label)

        self.log_viewer = api.LogViewer()
        layout.addWidget(self.log_viewer)

        # Log controls
        log_controls = api.QHBoxLayout()

        clear_logs_btn = api.QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(self.clear_logs)
        log_controls.addWidget(clear_logs_btn)

        save_logs_btn = api.QPushButton("Save Logs")
        save_logs_btn.clicked.connect(self.save_logs)
        log_controls.addWidget(save_logs_btn)

        log_controls.addStretch()
        layout.addLayout(log_controls)

        return panel

    def create_status_bar(self):
        """Create the status bar."""
        self.statusBar = api.QStatusBar()
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

            api.logger.info("Async connection manager initialized")
            self.statusBar.showMessage("Background initialization in progress...")

        except Exception as e:
            api.logger.error(f"Failed to initialize async manager: {e}")
            api.QMessageBox.critical(
                self,
                "Initialization Error",
                f"Failed to initialize connection manager:\n{e}",
            )

    def setup_timers(self):
        """Setup GUI update timers with reduced frequency to prevent blocking."""
        # Timer for processing status updates (less frequent)
        self.status_timer = api.QTimer(self)
        self.status_timer.timeout.connect(self.process_status_updates)
        self.status_timer.start(500)

        # Timer for GUI updates (less frequent)
        self.gui_timer = api.QTimer(self)
        self.gui_timer.timeout.connect(self.update_gui_state)
        self.gui_timer.start(2000)

    def on_status_update(self, update: api.StatusUpdate):
        """Handle status update from async manager."""

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
            and status.get("database", api.ConnectionStatus.DISCONNECTED)
            != api.ConnectionStatus.RUNNING
        )
        can_stop_infra = (
            managers_ready
            and status.get("database", api.ConnectionStatus.DISCONNECTED)
            == api.ConnectionStatus.RUNNING
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
                api.logger.info("Infrastructure startup initiated")
            else:
                api.QMessageBox.warning(
                    self, "Warning", "Infrastructure startup already in progress"
                )
        else:
            api.QMessageBox.warning(
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
                api.logger.info("Infrastructure stop initiated")
            else:
                api.QMessageBox.warning(
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
                api.logger.info(f"Device server {device_type}/{instance} startup initiated")
            else:
                api.QMessageBox.warning(
                    self,
                    "Warning",
                    f"Device server {device_type}/{instance} startup already in progress",
                )
        else:
            api.QMessageBox.warning(
                self,
                "Warning",
                "System not ready yet. Please wait for initialization to complete.",
            )

    def start_all_devices(self):
        """Start all configured device servers."""
        if not self.async_manager or not self.async_manager.is_managers_ready():
            api.QMessageBox.warning(self, "Warning", "System not ready yet.")
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
            api.logger.info(
                f"Batch device server startup initiated for {started_count} devices"
            )
        else:
            api.QMessageBox.information(
                self, "Info", "No device servers were started (may already be running)"
            )

    def clear_logs(self):
        """Clear the log viewer."""
        self.log_viewer.clear()
        api.logger.info("Log viewer cleared")

    def create_elyse_control_tab(self) -> api.QWidget:
        """Create ELYSE control tab with dynamic sub-tabs populated from ZMQ messages."""
        tab = api.QWidget()
        v = api.QVBoxLayout(tab)
        self.elyse_tabs = api.QTabWidget()
        v.addWidget(self.elyse_tabs)
        return tab

    def _ensure_zmq_push(self):
        if self._zmq_push is None:
            try:
                self._zmq_context = api.zmq.Context()
                self._zmq_push = self._zmq_context.socket(api.zmq.PUSH)
                self._zmq_push.connect("tcp://127.0.0.1:5556")
            except Exception:
                self._zmq_push = None

    def start_elyse_control(self):
        """Start ELYSE ZMQ thread and handlers."""
        if self._elyse_thread is not None:
            return
        try:
            self._elyse_thread = api.ElyseDataThread()
            self._elyse_thread.data_signal.connect(self.update_elyse_ui)
            self._elyse_thread.start()
            self._ensure_zmq_push()
            api.logger.info("ELYSE control thread started")
        except Exception as e:
            api.logger.warning(f"Failed to start ELYSE thread: {e}")
            self._elyse_thread = None

    def update_elyse_ui(self, message: str):
        """Handle incoming ELYSE ZMQ messages and update UI accordingly."""
        try:
            msg = eval(message)
        except Exception:
            return
        for card in msg:
            for elem in card:
                parts = str(elem).split("/")
                if len(parts) <= 3:
                    continue
                tab_name = "/".join(parts[0:2])
                elem_name = "/".join(parts[-3:-1])
                key_label = f"tab_{tab_name}_label_{elem_name}"
                if f"tab_{tab_name}" not in self._elyse_tabs_widgets:
                    self._add_elyse_tab(tab_name)
                if key_label not in self._elyse_elements:
                    self._add_elyse_element(elem_name, tab_name, elem)
                else:
                    self._update_elyse_element(tab_name, elem_name, elem)

    def _add_elyse_tab(self, name: str):
        w = api.QWidget()
        layout = api.QVBoxLayout()
        scroll = api.QScrollArea(widgetResizable=True)
        scroll.setWidget(w)
        w.setLayout(layout)
        self.elyse_tabs.addTab(scroll, name)
        self._elyse_tabs_widgets[f"tab_{name}"] = w
        self._elyse_layouts[f"layout_{name}"] = layout

    def _add_elyse_element(self, element_name: str, tab_name: str, element_value: str):
        parts = str(element_value).split("/")
        if len(parts) > 3:
            label = api.QLabel()
            text = "/".join(parts[-3:])
            try:
                val = float(parts[-1])
            except Exception:
                val = 0.0
            sb = api.QDoubleSpinBox()
            sb.setDecimals(6)
            sb.setRange(-1e9, 1e9)
            sb.setValue(val)
            sb.valueChanged.connect(
                lambda _v, t=tab_name, e=element_name: self._change_elyse_sb_value(t, e)
            )
            label.setText(text)
            elem_key_label = f"tab_{tab_name}_label_{element_name}"
            elem_key_sb = f"tab_{tab_name}_sb_{element_name}"
            self._elyse_elements[elem_key_label] = label
            self._elyse_elements[elem_key_sb] = sb
            layout: api.QVBoxLayout = self._elyse_layouts.get(f"layout_{tab_name}")
            lo_h = api.QHBoxLayout()
            lo_h.addWidget(label)
            lo_h.addWidget(sb)
            lo_h.addItem(
                api.QSpacerItem(40, 20, api.QSizePolicy.Expanding, api.QSizePolicy.Minimum)
            )
            layout.addLayout(lo_h)

    def _update_elyse_element(self, tab_name: str, elem_name: str, value: str):
        parts = str(value).split("/")
        text = "/".join(parts[-3:-1])
        label: api.QLabel = self._elyse_elements.get(f"tab_{tab_name}_label_{elem_name}")
        if label is not None:
            try:
                from decimal import Decimal

                label.setText(f"{text}/{Decimal(parts[-1]):.2E}")
            except Exception:
                label.setText(f"{text}/{parts[-1]}")

    def _change_elyse_sb_value(self, tab_name: str, elem_name: str):
        key = f"tab_{tab_name}_sb_{elem_name}"
        sb: api.QDoubleSpinBox = self._elyse_elements.get(key)
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
            self._zmq_push.send(val.encode("utf-8"))
            api.logger.info(f"ELYSE set: {val}")
        except Exception:
            pass

    def show_system_map(self):
        """Show the system layout map (legacy-style)."""
        try:
            # Prepare window
            map_w = api.QWidget()
            map_w.setWindowTitle("System Map")
            v = api.QVBoxLayout(map_w)
            h_image = api.QHBoxLayout()
            h_label = api.QHBoxLayout()
            v.addLayout(h_image)
            v.addLayout(h_label)

            glw = api.pg.GraphicsLayoutWidget()
            vb = glw.addViewBox(row=1, col=1)

            # Use existing icon (uppercase extension in repo)
            icon_path = str(
                (self.bin_path / "icons" / "Main_layout_1200.PNG").resolve()
            )
            im = api.imageio.imread(icon_path)

            img = api.pg.ImageItem()
            img.setImage(api.np.transpose(im, (1, 0, 2)))

            pos_lab = api.QLabel("Position")
            h_label.addWidget(pos_lab)

            def mouse_moved(lbl, ev):
                pos = ev[0]
                if img.sceneBoundingRect().contains(pos):
                    mp = vb.mapSceneToView(pos)
                    lbl.setText(f"x={mp.x():0.1f}, y={mp.y():0.1f}")

            proxy = api.pg.SignalProxy(
                vb.scene().sigMouseMoved,
                rateLimit=30,
                slot=lambda *e: mouse_moved(pos_lab, e),
            )
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
            api.QMessageBox.warning(self, "Map", f"Failed to show system map: {e}")

    def save_logs(self):
        """Save logs to file."""
        # TODO: Implement log saving
        api.QMessageBox.information(self, "Info", "Log saving feature coming soon!")

    def stop_all_running_devices(self):
        """Stop all running device servers."""
        if not self.async_manager or not self.async_manager.is_managers_ready():
            api.QMessageBox.warning(self, "Warning", "System not ready yet.")
            return
        try:
            count = self.async_manager.device_mgr.stop_all_servers()
            self.statusBar.showMessage(f"Stopped {count} running device servers")
        except Exception as e:
            api.QMessageBox.warning(self, "Warning", f"Failed to stop servers: {e}")

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
                row = api.QHBoxLayout()
                row.addWidget(api.QLabel("(infrastructure not initialized)"))
                self.starters_layout.insertLayout(0, row)
                return
            starters = self.async_manager.infrastructure_mgr.get_starters_status()
            if not starters:
                row = api.QHBoxLayout()
                row.addWidget(api.QLabel("No starters found or DB unavailable"))
                self.starters_layout.insertLayout(0, row)
                return
            for s in starters:
                name = s.get("name", "")
                state = s.get("state", "Unknown")
                row = api.QHBoxLayout()
                led = api.LedIndicator(12)
                if str(state).upper() in ("ON", "STANDBY", "MOVING", "RUNNING"):
                    led.set_on()
                elif str(state).upper() in ("OFF",):
                    led.set_off()
                else:
                    led.set_error()
                row.addWidget(led)
                row.addWidget(api.QLabel(name))
                row.addWidget(api.QLabel(f"State: {state}"))
                row.addStretch()
                self.starters_layout.insertLayout(self.starters_layout.count() - 1, row)
        except Exception as e:
            row = api.QHBoxLayout()
            row.addWidget(api.QLabel(f"Error loading starters: {e}"))
            self.starters_layout.insertLayout(0, row)

    def refresh_db_devices_list_async(self):
        """Fetch exported devices in a background thread and then rebuild UI."""
        if api.OFFLINE_MODE:
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
            api.QTimer.singleShot(
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
            row = api.QHBoxLayout()
            led = api.LedIndicator(12)
            state_lab = api.QLabel("Unknown")
            state_lab.setMinimumWidth(90)
            row.addWidget(led)
            row.addWidget(api.QLabel(name))
            row.addWidget(api.QLabel("State:"))
            row.addWidget(state_lab)
            btn_open = api.QPushButton("Open GUI")
            btn_open.clicked.connect(
                lambda _, n=name: self.open_device_widget_for_name(n)
            )
            row.addWidget(btn_open)
            row.addStretch()
            container = api.QWidget()
            container.setLayout(row)
            self.db_devices_layout.insertWidget(
                self.db_devices_layout.count() - 1, container
            )
            self.db_devices_widgets[name] = (led, state_lab, btn_open)

    return {
        "create_right_panel": create_right_panel,
        "create_status_bar": create_status_bar,
        "initialize_async_manager": initialize_async_manager,
        "setup_timers": setup_timers,
        "on_status_update": on_status_update,
        "thread_safe_log_callback": thread_safe_log_callback,
        "thread_safe_status_callback": thread_safe_status_callback,
        "process_status_updates": process_status_updates,
        "update_gui_state": update_gui_state,
        "start_infrastructure": start_infrastructure,
        "stop_infrastructure": stop_infrastructure,
        "start_device_server": start_device_server,
        "start_all_devices": start_all_devices,
        "clear_logs": clear_logs,
        "create_elyse_control_tab": create_elyse_control_tab,
        "_ensure_zmq_push": _ensure_zmq_push,
        "start_elyse_control": start_elyse_control,
        "update_elyse_ui": update_elyse_ui,
        "_add_elyse_tab": _add_elyse_tab,
        "_add_elyse_element": _add_elyse_element,
        "_update_elyse_element": _update_elyse_element,
        "_change_elyse_sb_value": _change_elyse_sb_value,
        "show_system_map": show_system_map,
        "save_logs": save_logs,
        "stop_all_running_devices": stop_all_running_devices,
        "refresh_starters": refresh_starters,
        "refresh_db_devices_list_async": refresh_db_devices_list_async,
        "_rebuild_db_devices_list": _rebuild_db_devices_list,
    }
