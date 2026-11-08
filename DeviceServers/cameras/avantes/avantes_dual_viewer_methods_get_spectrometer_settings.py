"""Implementation for get_spectrometer_settings and related operations."""


def _bind_avantes_dual_viewer_methods_get_spectrometer_settings(api):
    """Bind implementation to the owning module and its runtime state."""

    def get_spectrometer_settings(self, widget) -> dict:
        """Return settings for one spectrometer panel."""
        return {
            "serial": widget.serial_input.text().strip(),
            "integration_ms": float(widget.integration_spin.value()),
            "averages": int(widget.averages_spin.value()),
            "trigger_mode": int(widget.trigger_combo.currentIndex()),
        }

    def apply_settings_dict(self, settings: dict):
        """Apply settings loaded from JSON."""
        arduino = settings.get("arduino", {})
        if "lamp_warmup_seconds" in arduino:
            self.lamp_warmup_seconds = float(arduino["lamp_warmup_seconds"])
        if "auto_lamp_management_enabled" in arduino:
            self.auto_lamp_management_enabled = bool(arduino["auto_lamp_management_enabled"])
        if "lamp_off_between_points_enabled" in arduino:
            self.lamp_off_between_points_enabled = bool(arduino["lamp_off_between_points_enabled"])
        if "frequency_hz" in arduino:
            frequency = min(max(float(arduino["frequency_hz"]), 1.0), 100.0)
            if not self.set_arduino_frequency_hz(frequency):
                self.arduino_frequency_hz = frequency

        spectrometers = settings.get("spectrometers", {})
        self.apply_spectrometer_settings(self.spec1_widget, spectrometers.get("1", {}))
        self.apply_spectrometer_settings(self.spec2_widget, spectrometers.get("2", {}))

        ref_bg = settings.get("reference_background", {})
        if "averages" in ref_bg:
            self.ref_averages_spin.setValue(int(ref_bg["averages"]))

        data_collection = settings.get("data_collection", {})
        if "rate_s" in data_collection:
            self.collection_rate_spin.setValue(float(data_collection["rate_s"]))
        if "save_folder" in data_collection:
            self.save_folder_input.setText(str(data_collection["save_folder"]))
        if "save_name" in data_collection:
            self.save_name_input.setText(str(data_collection["save_name"]))

        od_limits = settings.get("od_plot_limits", {})
        if "x_auto" in od_limits:
            self.od_x_auto_check.setChecked(bool(od_limits["x_auto"]))
        if "x_min_nm" in od_limits:
            self.od_x_min_spin.setValue(float(od_limits["x_min_nm"]))
        if "x_max_nm" in od_limits:
            self.od_x_max_spin.setValue(float(od_limits["x_max_nm"]))
        if "y_auto" in od_limits:
            self.od_y_auto_check.setChecked(bool(od_limits["y_auto"]))
        if "y_min" in od_limits:
            self.od_y_min_spin.setValue(float(od_limits["y_min"]))
        if "y_max" in od_limits:
            self.od_y_max_spin.setValue(float(od_limits["y_max"]))
        self.update_od_axis_limits()

        tracking = settings.get("wavelength_tracking", {})
        if "wavelength_nm" in tracking:
            self.track_wavelength_spin.setValue(float(tracking["wavelength_nm"]))

        self.validate_collection_rate(show_warning=False)
        self.update_live_preview_interval()

    def apply_spectrometer_settings(self, widget, settings: dict):
        """Apply settings to one spectrometer panel."""
        if "serial" in settings:
            widget.serial_input.setText(str(settings["serial"]))
        if "integration_ms" in settings:
            widget.integration_spin.setValue(float(settings["integration_ms"]))
        if "averages" in settings:
            widget.averages_spin.setValue(int(settings["averages"]))
        if "trigger_mode" in settings:
            widget.trigger_combo.setCurrentIndex(int(settings["trigger_mode"]))

    def load_settings_json(self):
        """Choose and load JSON settings."""
        filename, _ = api.QFileDialog.getOpenFileName(
            self,
            "Load Settings JSON",
            str(self.settings_json_path),
            "JSON Files (*.json)"
        )
        if filename:
            self.load_settings_from_file(api.Path(filename), show_message=True)

    def load_settings_from_file(self, path: api.Path, show_message: bool = False):
        """Load JSON settings from path."""
        try:
            settings = api.json.loads(path.read_text(encoding="utf-8"))
            self.apply_settings_dict(settings)
            self.settings_json_path = path
            self.statusBar().showMessage(f"Loaded settings: {path}")
            self.logger.info(f"SETTINGS: Loaded {path}")
            if show_message:
                api.QMessageBox.information(self, "Settings Loaded", f"Loaded:\n{path}")
        except Exception as e:
            self.logger.error(f"SETTINGS: Failed to load {path} - {e}")
            api.QMessageBox.critical(self, "Settings Error", f"Failed to load settings:\n{e}")

    def save_settings_json_as(self):
        """Choose JSON path and save settings."""
        filename, _ = api.QFileDialog.getSaveFileName(
            self,
            "Save Settings JSON",
            str(self.settings_json_path),
            "JSON Files (*.json)"
        )
        if not filename:
            return
        path = api.Path(filename)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        self.settings_json_path = path
        self.write_settings_json(path, show_message=True)

    def update_settings_json(self):
        """Write current settings to current JSON path."""
        self.write_settings_json(self.settings_json_path, show_message=True)

    def write_settings_json(self, path: api.Path, show_message: bool = False):
        """Write current settings to JSON."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                api.json.dumps(self.get_settings_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            self.statusBar().showMessage(f"Updated settings JSON: {path}")
            self.logger.info(f"SETTINGS: Updated {path}")
            if show_message:
                api.QMessageBox.information(self, "Settings Saved", f"Saved:\n{path}")
        except Exception as e:
            self.logger.error(f"SETTINGS: Failed to save {path} - {e}")
            api.QMessageBox.critical(self, "Settings Error", f"Failed to save settings:\n{e}")

    def is_lamp_enabled(self) -> bool:
        """Check whether lamp TTL is enabled."""
        lamp_enabled, _ = self.get_arduino_state()
        return bool(lamp_enabled)

    def set_lamp_on(self):
        """Enable lamp and Avantes TTL pulses."""
        return self.set_lamp_and_avantes()

    def set_lamp_off(self, reschedule=True):
        """Disable lamp while keeping Avantes TTL available."""
        result = self.set_avantes_only()
        if result and reschedule and self.data_collection_active and self.collection_next_due_time:
            self.schedule_collection_due_time(self.collection_next_due_time)
        return result

    def set_lamp_and_avantes(self, wait_for_thermalization=False):
        """Set Arduino to trigger both lamp and Avantes.

        Parameters
        ----------
        wait_for_thermalization : bool
            If True, wait 1 second after enabling lamp for thermalization
        """
        # Always send command to ensure mode is set correctly
        if self.arduino.set_mode("LAMP AND AVANTES"):
            self.arduino_status_label.setText("Status: Lamp + Avantes")
            self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.logger.info("ARDUINO: Lamp + Avantes mode activated")

            # Wait for lamp thermalization if requested
            if wait_for_thermalization:
                self.logger.info("ARDUINO: Waiting 1s for lamp thermalization...")
                api.QTimer.singleShot(1000, lambda: self.logger.info("ARDUINO: Thermalization complete"))
                # Process events to keep UI responsive during wait
                from PyQt5.QtCore import QEventLoop
                loop = QEventLoop()
                api.QTimer.singleShot(1000, loop.quit)
                loop.exec_()

            return True
        else:
            self.arduino_status_label.setText("Status: Error")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.error("ARDUINO: Failed to set Lamp + Avantes mode")
            return False

    def set_avantes_only(self):
        """Set Arduino to trigger only Avantes (no lamp)."""
        # Always send command to ensure mode is set correctly
        if self.arduino.set_mode("ONLY AVANTES"):
            self.arduino_status_label.setText("Status: Avantes Only")
            self.arduino_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.logger.info("ARDUINO: Avantes Only mode activated (lamp OFF)")
            return True
        else:
            self.arduino_status_label.setText("Status: Error")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.error("ARDUINO: Failed to set Avantes Only mode")
            return False

    def set_arduino_off(self):
        """Turn off Arduino triggers."""
        if self.arduino.set_mode("OFF"):
            self.arduino_status_label.setText("Status: OFF")
            self.arduino_status_label.setStyleSheet("color: gray; font-weight: bold;")
            self.logger.info("ARDUINO: Triggers disabled")
        else:
            self.arduino_status_label.setText("Status: Error")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.error("ARDUINO: Failed to turn off")

    def toggle_continuous_readout(self):
        """Toggle manual live preview on/off."""
        if self.continuous_mode:
            self.stop_live_preview()
        else:
            # Start live preview at a modest rate; experiment collection has its own timer.
            interval_ms = self.get_live_preview_interval_ms()
            self.continuous_timer.start(interval_ms)
            self.continuous_mode = True
            self.continuous_btn.setText("Stop Live Preview")
            self.continuous_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
            self.logger.info(f"LIVE PREVIEW: Started ({interval_ms}ms interval)")
            self.statusBar().showMessage("Live preview active")

    def stop_live_preview(self):
        """Stop manual live preview if it is active."""
        if self.continuous_timer.isActive():
            self.continuous_timer.stop()
        self.continuous_mode = False
        self.continuous_btn.setText("Start Live Preview")
        self.continuous_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.logger.info(f"LIVE PREVIEW: Stopped ({self._measurement_count} measurements completed)")
        self.statusBar().showMessage("Live preview stopped")

    def stop_measurement(self):
        """Stop current reference or background measurement."""
        if self.measuring_reference:
            self.logger.info(f"REFERENCE: Measurement aborted by user ({len(self.reference_measurements)} of {self.ref_averages_spin.value()} collected)")
            self.measuring_reference = False
            self.reference_measurements = []
            self.statusBar().showMessage("Reference measurement aborted")

        if self.measuring_background:
            self.logger.info(f"BACKGROUND: Measurement aborted by user ({len(self.background_measurements)} of {self.ref_averages_spin.value()} collected)")
            self.measuring_background = False
            self.background_measurements = []
            self.statusBar().showMessage("Background measurement aborted")

        # Re-enable buttons
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)

    def measure_reference(self):
        """Measure reference spectra by averaging N measurements (with lamp ON)."""
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            api.QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            return

        # Ensure lamp is ON and wait for thermalization
        self.statusBar().showMessage("Preparing lamp...")
        if not self.set_lamp_and_avantes(wait_for_thermalization=True):
            api.QMessageBox.warning(self, "Error", "Failed to enable lamp")
            return

        n_avg = self.ref_averages_spin.value()
        self.measuring_reference = True
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button

        self.logger.info(f"REFERENCE: Starting measurement (lamp ON, hardware averaging {n_avg} pulses)")
        self.statusBar().showMessage(f"Measuring reference (hardware avg={n_avg})...")

        self.single_measurement(averages_override=n_avg, measurement_role="reference")

    def measure_background(self):
        """Measure background spectra by averaging N measurements (with lamp OFF)."""
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            api.QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            return

        # Ensure lamp is OFF
        self.set_avantes_only()

        n_avg = self.ref_averages_spin.value()
        self.measuring_background = True
        self.background_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button

        self.logger.info(f"BACKGROUND: Starting measurement (lamp OFF, hardware averaging {n_avg} pulses)")
        self.statusBar().showMessage(f"Measuring background (hardware avg={n_avg})...")

        self.single_measurement(averages_override=n_avg, measurement_role="background")

    def measure_reference_complete(self):
        """Called when reference measurement is complete."""
        if self.reference_measurements:
            self.reference_ch1 = self.reference_measurements[-1]['ch1']
            self.reference_ch2 = self.reference_measurements[-1]['ch2']
            self.reference_wavelengths = self.spec1_widget.wavelengths
            self.has_reference = True

            # Display reference lines on plots (magenta/purple)
            if self.reference_wavelengths is not None:
                self.ref_curve1.setData(self.reference_wavelengths, self.reference_ch1)
                self.ref_curve2.setData(self.reference_wavelengths, self.reference_ch2)

            self.logger.info("REFERENCE: Measurement complete (lamp ON)")
            self.statusBar().showMessage("Reference measured")

            # Enable data collection and tracking after reference and background exist.
            self.update_analysis_buttons()

        else:
            self.logger.error("REFERENCE: Failed - no measurement")
            self.statusBar().showMessage("Reference measurement failed")

        self.measuring_reference = False
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)  # Disable stop button

    def measure_background_complete(self):
        """Called when background measurement is complete."""
        if self.background_measurements:
            self.background_ch1 = self.background_measurements[-1]['ch1']
            self.background_ch2 = self.background_measurements[-1]['ch2']
            self.has_background = True

            # Display background lines on plots (blue)
            # Use wavelengths from spectrometer (always available after connection)
            wavelengths = self.spec1_widget.wavelengths
            if wavelengths is not None:
                self.bg_curve1.setData(wavelengths, self.background_ch1)
                self.bg_curve2.setData(wavelengths, self.background_ch2)
                self.logger.info("BACKGROUND: Measurement complete (lamp OFF) - blue lines displayed")
            else:
                self.logger.warning("BACKGROUND: Wavelengths not available for plotting")

            self.statusBar().showMessage("Background measured")
            self.update_analysis_buttons()

        else:
            self.logger.error("BACKGROUND: Failed - no measurement")
            self.statusBar().showMessage("Background measurement failed")

        # Reset measuring flag FIRST before any other updates
        self.measuring_background = False
        self.background_measurements = []
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)  # Disable stop button

        # Log the state explicitly
        self.logger.info(f"BACKGROUND: Flags reset - measuring_background={self.measuring_background}, has_background={self.has_background}")

    def toggle_data_collection(self):
        """Toggle data collection mode."""
        if not self.data_collection_active:
            # Start data collection
            if not self.has_reference or not self.has_background:
                api.QMessageBox.warning(self, "Error", "Please measure reference and background first")
                return

            if not self.validate_collection_rate(show_warning=True):
                return

            interval_ms = int(self.collection_rate_spin.value() * 1000)
            if interval_ms < 100:
                api.QMessageBox.warning(self, "Error", "Minimum collection rate is 0.1s (100ms)")
                return

            try:
                save_dir = api.Path(self.save_folder_input.text()).expanduser()
                save_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                api.QMessageBox.critical(self, "Save Folder Error", f"Cannot use save folder:\n{str(e)}")
                return

            base_name = self.save_name_input.text().strip() or "avantes_measurement"
            self.collection_file_path = save_dir / f"{base_name}.dat"

            self.data_collection_active = True
            self.collection_data = []
            self.collection_point_index = 0
            self.collection_start_time = api.time.time()
            self.collection_point_start_time = None
            self.collection_next_due_time = None
            self.reset_od_heatmap()
            if self.collection_file_path.exists():
                self.collection_file_path.unlink()

            self.start_collection_btn.setText("Stop DC")
            self.collection_countdown_timer.start()
            self.update_collection_countdown_label()
            self.logger.info(
                f"DATA COLLECTION: Started (rate={self.collection_rate_spin.value()}s, "
                f"detector_avg={self.get_detector_average_count()}, file={self.collection_file_path})"
            )
            self.statusBar().showMessage(f"Data collection active ({self.collection_rate_spin.value()}s interval)")
            self.collect_data_point()
        else:
            # Stop data collection
            self.data_collection_active = False
            self.collection_timer.stop()
            self.lamp_warmup_timer.stop()
            self.collection_countdown_timer.stop()
            self.start_collection_btn.setText("Start DC")

            n_points = len(self.collection_data) if hasattr(self, 'collection_data') else 0
            self.update_collection_countdown_label()
            self.logger.info(f"DATA COLLECTION: Stopped ({n_points} data points collected, file={self.collection_file_path})")
            self.statusBar().showMessage(f"Data collection stopped ({n_points} points)")

    def collect_data_point(self):
        """Collect a data point during active data collection."""
        if not self.data_collection_active or not self.has_reference or not self.has_background:
            return
        if self.measurement_thread and self.measurement_thread.isRunning():
            return

        n_avg = self.get_detector_average_count()
        self.collection_timer.stop()
        self.lamp_warmup_timer.stop()
        if not self.is_lamp_enabled():
            self.logger.info("DATA COLLECTION: Lamp was off at measurement time; enabling now")
            if not self.set_lamp_and_avantes():
                self.statusBar().showMessage("Data collection paused: failed to enable lamp")
                self.schedule_next_collection_point()
                return
        self.collection_point_start_time = api.time.time()
        self.statusBar().showMessage(f"Collecting point {self.collection_point_index + 1} (avg={n_avg})...")
        self.update_collection_countdown_label()
        self.single_measurement(averages_override=n_avg, measurement_role="collection")

    def schedule_next_collection_point(self):
        """Schedule next collection point without overlapping hardware averaging."""
        if not self.data_collection_active:
            return

        self.validate_collection_rate(show_warning=False)
        interval_s = float(self.collection_rate_spin.value())
        base_time = self.collection_point_start_time or api.time.time()
        self.schedule_collection_due_time(base_time + interval_s)
        self.update_collection_countdown_label()

    def on_collection_rate_changed(self):
        """Reschedule active data collection when rate changes."""
        if not self.data_collection_active:
            return
        if self.measurement_thread and self.measurement_thread.isRunning():
            return

        self.validate_collection_rate(show_warning=False)
        interval_s = float(self.collection_rate_spin.value())
        base_time = self.collection_point_start_time or self.collection_start_time or api.time.time()
        self.schedule_collection_due_time(base_time + interval_s)
        self.update_collection_countdown_label()

    def schedule_collection_due_time(self, due_time: float):
        """Schedule warmup and measurement for the next collection point."""
        if not self.data_collection_active:
            return

        self.collection_next_due_time = due_time
        self.collection_timer.stop()
        self.lamp_warmup_timer.stop()

        now = api.time.time()
        seconds_until_due = max(0.0, due_time - now)
        warmup_s = self.lamp_warmup_seconds

        if not self.auto_lamp_management_enabled:
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(f"Next point in {seconds_until_due:.0f}s")
        elif seconds_until_due > warmup_s and self.lamp_off_between_points_enabled:
            if self.is_lamp_enabled():
                self.set_lamp_off(reschedule=False)
            warmup_delay_ms = int((seconds_until_due - warmup_s) * 1000)
            self.lamp_warmup_timer.start(warmup_delay_ms)
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(
                f"Next point in {seconds_until_due:.0f}s; lamp warmup starts in {seconds_until_due - warmup_s:.0f}s"
            )
        else:
            if not self.is_lamp_enabled():
                self.prepare_lamp_for_collection()
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(f"Next point in {seconds_until_due:.0f}s; lamp stays on")
        self.update_collection_countdown_label()

    def prepare_lamp_for_collection(self):
        """Enable lamp before a scheduled collection point."""
        if not self.data_collection_active:
            return
        if self.is_lamp_enabled():
            return
        if self.set_lamp_and_avantes():
            due = self.collection_next_due_time or api.time.time()
            self.statusBar().showMessage(f"Lamp warming; next point in {max(0.0, due - api.time.time()):.0f}s")
            self.logger.info("DATA COLLECTION: Lamp enabled for scheduled measurement")
            self.update_collection_countdown_label()

    def format_seconds_for_countdown(self, seconds: float) -> str:
        """Format countdown seconds as compact time text."""
        seconds = max(0, int(round(seconds)))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:d}:{secs:02d}"

    def update_collection_countdown_label(self):
        """Update data-collection countdown and point counter."""
        points = self.collection_point_index if hasattr(self, "collection_point_index") else 0
        if not hasattr(self, "collection_countdown_label"):
            return
        if not self.data_collection_active:
            self.collection_countdown_label.setText(f"Next: -- | Points: {points}")
            return
        if getattr(self, "current_measurement_role", None) == "collection":
            self.collection_countdown_label.setText(f"Collecting... | Points: {points}")
            return
        if self.collection_next_due_time is None:
            self.collection_countdown_label.setText(f"Next: now | Points: {points}")
            return

        remaining = max(0.0, self.collection_next_due_time - api.time.time())
        text = f"Next: {self.format_seconds_for_countdown(remaining)} | Points: {points}"

        if self.auto_lamp_management_enabled and self.lamp_off_between_points_enabled:
            warmup_start_in = remaining - self.lamp_warmup_seconds
            if warmup_start_in > 0:
                text += f" | Lamp in {self.format_seconds_for_countdown(warmup_start_in)}"
            else:
                text += " | Lamp on"

        self.collection_countdown_label.setText(text)

    return {
        "get_spectrometer_settings": get_spectrometer_settings,
        "apply_settings_dict": apply_settings_dict,
        "apply_spectrometer_settings": apply_spectrometer_settings,
        "load_settings_json": load_settings_json,
        "load_settings_from_file": load_settings_from_file,
        "save_settings_json_as": save_settings_json_as,
        "update_settings_json": update_settings_json,
        "write_settings_json": write_settings_json,
        "is_lamp_enabled": is_lamp_enabled,
        "set_lamp_on": set_lamp_on,
        "set_lamp_off": set_lamp_off,
        "set_lamp_and_avantes": set_lamp_and_avantes,
        "set_avantes_only": set_avantes_only,
        "set_arduino_off": set_arduino_off,
        "toggle_continuous_readout": toggle_continuous_readout,
        "stop_live_preview": stop_live_preview,
        "stop_measurement": stop_measurement,
        "measure_reference": measure_reference,
        "measure_background": measure_background,
        "measure_reference_complete": measure_reference_complete,
        "measure_background_complete": measure_background_complete,
        "toggle_data_collection": toggle_data_collection,
        "collect_data_point": collect_data_point,
        "schedule_next_collection_point": schedule_next_collection_point,
        "on_collection_rate_changed": on_collection_rate_changed,
        "schedule_collection_due_time": schedule_collection_due_time,
        "prepare_lamp_for_collection": prepare_lamp_for_collection,
        "format_seconds_for_countdown": format_seconds_for_countdown,
        "update_collection_countdown_label": update_collection_countdown_label,
    }
