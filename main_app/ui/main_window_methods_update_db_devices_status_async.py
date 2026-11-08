"""Implementation for update_db_devices_status_async and related operations."""


def _bind_main_window_methods_update_db_devices_status_async(api):
    """Bind implementation to the owning module and its runtime state."""

    def update_db_devices_status_async(self):
        """Query device states in background and apply to UI when ready."""
        if api.OFFLINE_MODE:
            return
        if not getattr(self, "db_devices_widgets", None):
            return
        try:
            import concurrent.futures

            from taurus import Device
        except Exception:
            return

        names = list(self.db_devices_widgets.keys())

        def _read_all():
            res = {}
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:

                    def read_state(dev_name: str):
                        try:
                            dev = Device(dev_name)
                            st = dev.state()
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

            api.QTimer.singleShot(0, apply)
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
                ("zaber", "ZaberStageWidget"),
                ("netio", "Netio_pdu"),
                ("basler", "Basler_camera"),
                ("owis", "OWIS_motor"),
                ("standa", "Standa_motor"),
                ("topdirect", "TopDirect_Motor"),
                ("keysight", "Keysight_33509B"),
                ("awg", "Keysight_33509B"),
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
                api.QMessageBox.information(
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
            api.QMessageBox.critical(
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
            info = api.QLabel("Infrastructure manager not ready")
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
                api.QLabel(f"Failed to load admin servers: {e}"),
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
            header_row = api.QHBoxLayout()
            led = api.LedIndicator(12)
            status_label = api.QLabel(str(status))
            key = str(admin) or f"{server_class}/{instance}"
            self.ds_status_widgets[key] = (led, status_label)
            header_row.addWidget(led)
            header_row.addWidget(api.QLabel(f"{server_class}/{instance}"))
            header_row.addWidget(api.QLabel("Status:"))
            header_row.addWidget(status_label)
            header_row.addStretch()
            header_container = api.QWidget()
            header_container.setLayout(header_row)
            self.ds_list_layout.insertWidget(
                self.ds_list_layout.count() - 1, header_container
            )

            # Controlled devices under this server
            if devices:
                for dev_name in sorted(devices):
                    row = api.QHBoxLayout()
                    row.addWidget(api.QLabel("↳"))
                    row.addWidget(api.QLabel(dev_name))
                    btn_open = api.QPushButton("Open GUI")
                    btn_open.clicked.connect(
                        lambda _, n=dev_name: self.open_device_widget_for_name(n)
                    )
                    row.addWidget(btn_open)
                    row.addStretch()
                    cont = api.QWidget()
                    cont.setLayout(row)
                    self.ds_list_layout.insertWidget(
                        self.ds_list_layout.count() - 1, cont
                    )
            else:
                # No devices found
                row = api.QHBoxLayout()
                row.addWidget(api.QLabel("↳ (no devices found)"))
                row.addStretch()
                cont = api.QWidget()
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
            api.logger.debug(f"update_deviceservers_status failed: {e}")

    def stop_device_server(self, device_type: str, instance: str):
        if not self.async_manager or not self.async_manager.is_managers_ready():
            api.QMessageBox.warning(self, "Warning", "System not ready yet.")
            return
        ok = self.async_manager.device_mgr.stop_deviceserver(device_type, instance)
        if ok:
            self.statusBar.showMessage(f"Stopped {device_type}/{instance}")
        else:
            api.QMessageBox.warning(
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
                api.QMessageBox.warning(
                    self,
                    "Warning",
                    f"Failed to launch GUI for {device_type}/{instance}",
                )
        except Exception as e:
            api.QMessageBox.critical(
                self, "Error", f"Error launching GUI for {device_type}/{instance}: {e}"
            )

    def show_about(self):
        """Show about dialog."""
        api.QMessageBox.about(
            self,
            "About PyConlyse v2.0",
            """PyConlyse v2.0 - Control System
                        \x20
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
        api.logger.info("Application shutdown requested")

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

        api.logger.info("Application shutdown complete")
        event.accept()

    def deferred_startup(self):
        """Perform heavy initialization after the GUI is shown."""
        if self._deferred_started:
            return
        self._deferred_started = True

        try:
            # Setup logging now (writes to files, handlers, etc.)
            self.logger_manager = api.setup_pyconlyse_logging()
            api.logger.info("Deferred startup: logging initialized")

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

            api.logger.info("Deferred startup complete")
            self.statusBar.showMessage("System initializing in background...")
        except Exception as e:
            api.logger.exception(f"Deferred startup failed: {e}")
            api.QMessageBox.critical(self, "Startup Error", f"Initialization failed: {e}")

    return {
        "update_db_devices_status_async": update_db_devices_status_async,
        "open_device_widget_for_name": open_device_widget_for_name,
        "rebuild_deviceservers_list": rebuild_deviceservers_list,
        "on_refresh_deviceservers_clicked": on_refresh_deviceservers_clicked,
        "update_deviceservers_status": update_deviceservers_status,
        "stop_device_server": stop_device_server,
        "open_device_client": open_device_client,
        "show_about": show_about,
        "closeEvent": closeEvent,
        "deferred_startup": deferred_startup,
    }
