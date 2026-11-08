"""Implementation for create_deviceserver_section and related operations."""


def _bind_main_control_methods_create_deviceserver_section(api):
    """Bind implementation to the owning module and its runtime state."""

    def create_deviceserver_section(
        self, device_type: str, instances: api.List[str]
    ) -> api.QWidget:
        """Create a DeviceServer control section"""
        section = api.QFrame()
        section.setFrameStyle(api.QFrame.StyledPanel)
        layout = api.QVBoxLayout()

        # Header
        header_layout = api.QHBoxLayout()
        title = api.QLabel(f"{device_type} DeviceServers")
        title.setFont(api.QFont("Arial", 10, api.QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Instance controls
        for instance in instances:
            instance_layout = api.QHBoxLayout()

            instance_label = api.QLabel(f"  {instance}:")
            instance_label.setMinimumWidth(100)

            btn_start = api.QPushButton("Start")
            btn_start.setMaximumWidth(60)
            btn_start.clicked.connect(
                api.partial(self.start_deviceserver, device_type, instance)
            )

            btn_stop = api.QPushButton("Stop")
            btn_stop.setMaximumWidth(60)
            btn_stop.clicked.connect(
                api.partial(self.stop_deviceserver, device_type, instance)
            )

            btn_restart = api.QPushButton("Restart")
            btn_restart.setMaximumWidth(80)
            btn_restart.clicked.connect(
                api.partial(self.restart_deviceserver, device_type, instance)
            )

            status_label = api.QLabel("Unknown")
            status_label.setMinimumWidth(80)

            instance_layout.addWidget(instance_label)
            instance_layout.addWidget(btn_start)
            instance_layout.addWidget(btn_stop)
            instance_layout.addWidget(btn_restart)
            instance_layout.addWidget(status_label)
            instance_layout.addStretch()

            layout.addLayout(instance_layout)

        section.setLayout(layout)
        return section

    def start_tango_infrastructure(self):
        """Start the Tango infrastructure"""
        try:
            progress = api.QProgressDialog(
                "Starting Tango Infrastructure...", "Cancel", 0, 0, self
            )
            progress.setWindowModality(api.Qt.WindowModal)
            progress.show()

            def progress_callback(message):
                progress.setLabelText(message)
                api.QtWidgets.QApplication.processEvents()

            success = self.tango_manager.start_infrastructure(progress_callback)
            progress.close()

            if success:
                self.btn_start_tango.setEnabled(False)
                self.btn_stop_tango.setEnabled(True)
                self.status_label.setText("Tango Infrastructure Starting...")
                self.status_label.setStyleSheet(
                    "QLabel { color: orange; font-weight: bold; }"
                )
                self.log_message("Tango infrastructure startup initiated")

                # Auto-configure Astor after a delay
                api.QTimer.singleShot(10000, self.auto_configure_astor)  # 10 seconds delay
            else:
                self.show_error("Failed to start Tango infrastructure")

        except Exception as e:
            api.logger.error(f"Error starting Tango infrastructure: {e}")
            self.show_error(f"Error starting Tango infrastructure: {e}")

    def stop_tango_infrastructure(self):
        """Stop the Tango infrastructure"""
        try:
            success = self.tango_manager.stop_infrastructure()

            if success:
                self.btn_start_tango.setEnabled(True)
                self.btn_stop_tango.setEnabled(False)
                self.status_label.setText("System Ready")
                self.status_label.setStyleSheet(
                    "QLabel { color: green; font-weight: bold; }"
                )
                self.log_message("Tango infrastructure stopped")
            else:
                self.show_error("Failed to stop Tango infrastructure")

        except Exception as e:
            api.logger.error(f"Error stopping Tango infrastructure: {e}")
            self.show_error(f"Error stopping Tango infrastructure: {e}")

    def configure_astor(self):
        """Configure Astor for DeviceServer management"""
        try:
            config_script = api.Path(api.__file__).parent / "configure_astor_startup.py"
            if not config_script.exists():
                self.show_error("Astor configuration script not found!")
                return

            # Run configuration script
            process = api.subprocess.Popen(
                [api.sys.executable, str(config_script)],
                cwd=str(config_script.parent),
                stdout=api.subprocess.PIPE,
                stderr=api.subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()

            if process.returncode == 0:
                self.log_message("Astor configuration completed successfully")
                self.show_info(
                    "Astor configuration completed!\nDeviceServers should now be managed automatically."
                )
            else:
                self.log_message(f"Astor configuration failed: {stderr}")
                self.show_error(f"Astor configuration failed:\n{stderr}")

        except Exception as e:
            api.logger.error(f"Error configuring Astor: {e}")
            self.show_error(f"Error configuring Astor: {e}")

    def auto_configure_astor(self):
        """Automatically configure Astor after Tango startup"""
        self.log_message("Auto-configuring Astor...")
        self.configure_astor()

    def start_client(self, device_type: str, combo: api.TaurusValueComboBox):
        """Start a device client using ClientManager"""
        try:
            instance = combo.itemText(combo.currentIndex())

            # Check if client is already running
            if self.client_manager.is_client_running(device_type, instance):
                self.log_message(f"{device_type}/{instance} client is already running")
                self.show_info(
                    f"{device_type} client for {instance} is already running."
                )
                return

            # Launch the client
            success = self.client_manager.launch_client(
                device_type, instance, self.type_vis
            )

            if success:
                self.log_message(f"Started {device_type} client: {instance}")
            else:
                self.log_message(f"Failed to start {device_type} client: {instance}")
                self.show_error(f"Failed to start {device_type} client for {instance}")

        except Exception as e:
            api.logger.error(f"Failed to start client {device_type}: {e}")
            self.log_message(f"Error starting {device_type} client: {e}")
            self.show_error(f"Error starting {device_type} client: {e}")

    def start_deviceserver(self, device_type: str, instance: str):
        """Start a DeviceServer"""
        success = self.device_manager.start_deviceserver(
            device_type, instance, self.type_vis.value
        )
        if success:
            self.log_message(f"Started DeviceServer: {device_type}/{instance}")
        else:
            self.log_message(f"Failed to start DeviceServer: {device_type}/{instance}")
        self.refresh_deviceserver_status()

    def stop_deviceserver(self, device_type: str, instance: str):
        """Stop a DeviceServer"""
        success = self.device_manager.stop_deviceserver(device_type, instance)
        if success:
            self.log_message(f"Stopped DeviceServer: {device_type}/{instance}")
        else:
            self.log_message(f"Failed to stop DeviceServer: {device_type}/{instance}")
        self.refresh_deviceserver_status()

    def restart_deviceserver(self, device_type: str, instance: str):
        """Restart a DeviceServer"""
        success = self.device_manager.restart_deviceserver(
            device_type, instance, self.type_vis.value
        )
        if success:
            self.log_message(f"Restarted DeviceServer: {device_type}/{instance}")
        else:
            self.log_message(
                f"Failed to restart DeviceServer: {device_type}/{instance}"
            )
        self.refresh_deviceserver_status()

    def start_all_deviceservers(self):
        """Start all configured DeviceServers"""
        count = 0
        for device_type, config in self.device_manager.device_configs.items():
            for instance in config["instances"]:
                if self.device_manager.start_deviceserver(
                    device_type, instance, self.type_vis.value
                ):
                    count += 1

        self.log_message(f"Started {count} DeviceServers")
        self.refresh_deviceserver_status()

    def stop_all_deviceservers(self):
        """Stop all running DeviceServers"""
        running_servers = list(self.device_manager.running_servers.keys())
        count = 0

        for server_key in running_servers:
            server_info = self.device_manager.running_servers[server_key]
            if self.device_manager.stop_deviceserver(
                server_info["device_type"], server_info["instance"]
            ):
                count += 1

        self.log_message(f"Stopped {count} DeviceServers")
        self.refresh_deviceserver_status()

    def refresh_deviceserver_status(self):
        """Refresh the DeviceServer status display"""
        # This would update the status labels in the DeviceServer sections
        running_servers = self.device_manager.get_running_servers()
        self.deviceservers_status_label.setText(
            f"DeviceServers: {len(running_servers)} running"
        )

    def toggle_rpi_pin(self, pin: int):
        """Toggle an RPI GPIO pin with timeout protection"""

        def _toggle_pin():
            try:
                rpi_device = api.Device("manip/v0/rpi4_gpio_v0")
                state = rpi_device.get_pin_state(pin)
                if state != -1:
                    rpi_device.set_pin_state([pin, 1])
                    api.sleep(0.25)
                    rpi_device.set_pin_state([pin, 0])
                    return True
                return False
            except Exception as e:
                api.logger.error(f"Device operation failed for pin {pin}: {e}")
                return None

        try:
            # Use timeout for device operations
            with api.concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_toggle_pin)
                result = future.result(timeout=5.0)  # 5 second timeout

            if result is True:
                self.log_message(f"Toggled RPI pin {pin}")
            elif result is False:
                self.log_message(f"Invalid RPI pin state: {pin}")
            else:
                self.log_message(f"Failed to toggle RPI pin {pin}")

        except api.concurrent.futures.TimeoutError:
            api.logger.error(f"RPI pin {pin} toggle timed out")
            self.log_message(f"RPI pin {pin} toggle timed out")
        except Exception as e:
            api.logger.error(f"Failed to toggle RPI pin {pin}: {e}")
            self.log_message(f"Error toggling RPI pin {pin}: {e}")

    def show_system_map(self):
        """Show the system layout map"""
        try:
            # This would implement the system map display
            # For now, just show a message
            self.show_info(
                "System map functionality will be implemented here.\nThis would show the device layout visualization."
            )

        except Exception as e:
            api.logger.error(f"Error showing system map: {e}")
            self.show_error(f"Error showing system map: {e}")

    def on_vis_type_changed(self, value: str):
        """Handle visualization type change"""
        self.type_vis = api.VisType(value)
        self.log_message(f"Visualization type changed to: {value}")

    def on_device_state_changed(self, device_name: str, state):
        """Handle device state change"""
        if device_name in self.device_labels:
            label = self.device_labels[device_name]

            if state == api.DevState.ON:
                label.update_style("background-color: green")
            elif state == api.DevState.STANDBY:
                label.update_style("background-color: yellow")
            elif state == api.DevState.OFF:
                label.update_style("background-color: gray")
            elif state == api.DevState.FAULT:
                label.update_style("background-color: red")
            else:
                label.update_style("background-color: purple")

    def on_device_label_clicked(self, device_name: str):
        """Handle device label click"""
        self.log_message(f"Device clicked: {device_name}")

    def on_elyse_data_received(self, message: str):
        """Handle ELYSE data message"""
        try:
            # Process ELYSE data message
            # This is a simplified version of the original implementation
            self.log_message(f"ELYSE data received: {len(message)} bytes")

        except Exception as e:
            api.logger.error(f"Error processing ELYSE data: {e}")

    def update_status(self):
        """Update system status display"""
        try:
            # Get detailed status of all Tango components
            tango_status = self.tango_manager.get_status()
            tango_running = self.tango_manager.check_tango_running()

            # Update overall Tango status
            if tango_running:
                self.tango_status_label.setText("Tango: Connected")
                self.status_label.setText("System Running")
                self.status_label.setStyleSheet(
                    "QLabel { color: green; font-weight: bold; }"
                )
                # Update the manager's internal flag if we detect it's running
                if not self.tango_manager.is_running:
                    self.tango_manager.is_running = True
                    self.btn_start_tango.setEnabled(False)
                    self.btn_stop_tango.setEnabled(True)
            else:
                self.tango_status_label.setText("Tango: Disconnected")
                self.status_label.setText("System Ready")
                self.status_label.setStyleSheet(
                    "QLabel { color: orange; font-weight: bold; }"
                )
                # Update the manager's internal flag if we detect it's not running
                if self.tango_manager.is_running:
                    self.tango_manager.is_running = False
                    self.btn_start_tango.setEnabled(True)
                    self.btn_stop_tango.setEnabled(False)

            # Update individual component status
            db_status = tango_status.get("database", "Unknown")
            starter_status = tango_status.get("starter", "Unknown")
            astor_status = tango_status.get("astor", "Unknown")

            self.tango_db_label.setText(f"Database: {db_status}")
            self.tango_starter_label.setText(f"Starter: {starter_status}")
            self.tango_astor_label.setText(f"Astor: {astor_status}")

            # Set colors for component status
            for label, status in [
                (self.tango_db_label, db_status),
                (self.tango_starter_label, starter_status),
                (self.tango_astor_label, astor_status),
            ]:
                if "Running" in status:
                    label.setStyleSheet("QLabel { color: green; }")
                elif "Not started" in status:
                    label.setStyleSheet("QLabel { color: gray; }")
                else:
                    label.setStyleSheet("QLabel { color: red; }")

            # Update DeviceServer status
            running_count = len(self.device_manager.get_running_servers())
            self.deviceservers_status_label.setText(
                f"DeviceServers: {running_count} running"
            )

        except Exception as e:
            api.logger.debug(f"Status update error: {e}")

    def log_message(self, message: str):
        """Add message to log display"""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.log_display.append(formatted_message)

        # Keep only last 100 lines
        if self.log_display.document().lineCount() > 100:
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor)
            cursor.removeSelectedText()

    def show_error(self, message: str):
        """Show error message dialog"""
        api.QMessageBox.critical(self, "Error", message)

    def show_info(self, message: str):
        """Show info message dialog"""
        api.QMessageBox.information(self, "Information", message)

    def on_client_launched(self, client_type: str, instance: str):
        """Handle client launched signal"""
        self.log_message(f"Client launched: {client_type}/{instance}")

    def on_client_closed(self, client_type: str, instance: str):
        """Handle client closed signal"""
        self.log_message(f"Client closed: {client_type}/{instance}")

    def on_client_error(self, client_type: str, instance: str, error: str):
        """Handle client error signal"""
        self.log_message(f"Client error {client_type}/{instance}: {error}")

    def get_active_clients_info(self) -> str:
        """Get information about active clients"""
        active_clients = self.client_manager.get_active_clients()
        if not active_clients:
            return "No active clients"

        info_lines = []
        for key, client in active_clients.items():
            info_lines.append(
                f"- {client.client_type}/{client.instance} ({client.vis_type.value})"
            )

        return f"Active clients ({len(active_clients)}):\n" + "\n".join(info_lines)

    def close_all_clients(self):
        """Close all active clients"""
        try:
            active_count = len(self.client_manager.get_active_clients())
            if active_count > 0:
                self.client_manager.close_all_clients()
                self.log_message(f"Closed {active_count} client(s)")
            else:
                self.log_message("No active clients to close")
        except Exception as e:
            api.logger.error(f"Error closing clients: {e}")
            self.log_message(f"Error closing clients: {e}")

    def show_active_clients(self):
        """Show information about active clients"""
        try:
            clients_info = self.get_active_clients_info()
            self.show_info(f"Active Client Information:\n\n{clients_info}")
        except Exception as e:
            api.logger.error(f"Error showing active clients: {e}")
            self.show_error(f"Error showing active clients: {e}")

    def closeEvent(self, event):
        """Handle application close"""
        try:
            # Close all active clients
            self.close_all_clients()

            # Stop monitoring threads
            if self.device_monitor_thread:
                self.device_monitor_thread.stop()
                self.device_monitor_thread.wait(1000)

            if self.elyse_data_thread:
                self.elyse_data_thread.stop()
                self.elyse_data_thread.wait(1000)

            # Close ZMQ socket
            if self.zmq_socket_push:
                self.zmq_socket_push.close()
            if self.zmq_context:
                self.zmq_context.destroy()

            api.logger.info("Application closing")

        except Exception as e:
            api.logger.error(f"Error during close: {e}")

        event.accept()

    return {
        "create_deviceserver_section": create_deviceserver_section,
        "start_tango_infrastructure": start_tango_infrastructure,
        "stop_tango_infrastructure": stop_tango_infrastructure,
        "configure_astor": configure_astor,
        "auto_configure_astor": auto_configure_astor,
        "start_client": start_client,
        "start_deviceserver": start_deviceserver,
        "stop_deviceserver": stop_deviceserver,
        "restart_deviceserver": restart_deviceserver,
        "start_all_deviceservers": start_all_deviceservers,
        "stop_all_deviceservers": stop_all_deviceservers,
        "refresh_deviceserver_status": refresh_deviceserver_status,
        "toggle_rpi_pin": toggle_rpi_pin,
        "show_system_map": show_system_map,
        "on_vis_type_changed": on_vis_type_changed,
        "on_device_state_changed": on_device_state_changed,
        "on_device_label_clicked": on_device_label_clicked,
        "on_elyse_data_received": on_elyse_data_received,
        "update_status": update_status,
        "log_message": log_message,
        "show_error": show_error,
        "show_info": show_info,
        "on_client_launched": on_client_launched,
        "on_client_closed": on_client_closed,
        "on_client_error": on_client_error,
        "get_active_clients_info": get_active_clients_info,
        "close_all_clients": close_all_clients,
        "show_active_clients": show_active_clients,
        "closeEvent": closeEvent,
    }
