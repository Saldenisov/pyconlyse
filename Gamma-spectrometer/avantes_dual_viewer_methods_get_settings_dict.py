"""Implementation for get_settings_dict and related operations."""


def _bind_avantes_dual_viewer_methods_get_settings_dict(api):
    """Bind implementation to the owning module and its runtime state."""

    def get_settings_dict(self) -> dict:
        """Return current UI settings for JSON export."""
        return {
            "version": 1,
            "arduino": {
                "frequency_hz": float(self.arduino_frequency_hz),
                "lamp_warmup_seconds": float(self.lamp_warmup_seconds),
                "lamp_min_off_seconds": float(self.lamp_min_off_seconds),
                "auto_lamp_management_enabled": bool(self.auto_lamp_management_enabled),
                "lamp_off_between_points_enabled": bool(self.lamp_off_between_points_enabled),
            },
            "spectrometers": {
                "1": self.get_spectrometer_settings(self.spec1_widget),
                "2": self.get_spectrometer_settings(self.spec2_widget),
            },
            "reference_background": {
                "blocks": int(self.ref_blocks_spin.value()),
            },
            "data_collection": {
                "rate_s": float(self.collection_rate_spin.value()),
                "save_folder": self.save_folder_input.text(),
                "save_name": self.save_name_input.text(),
            },
            "od_plot_limits": {
                "x_auto": bool(self.od_x_auto_check.isChecked()),
                "x_min_nm": float(self.od_x_min_spin.value()),
                "x_max_nm": float(self.od_x_max_spin.value()),
                "y_auto": bool(self.od_y_auto_check.isChecked()),
                "y_min": float(self.od_y_min_spin.value()),
                "y_max": float(self.od_y_max_spin.value()),
            },
            "wavelength_tracking": {
                "wavelength_nm": float(self.track_wavelength_spin.value()),
            },
        }

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
        if "lamp_min_off_seconds" in arduino:
            self.lamp_min_off_seconds = float(arduino["lamp_min_off_seconds"])
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
        if "blocks" in ref_bg:
            self.ref_blocks_spin.setValue(int(ref_bg["blocks"]))
        elif "averages" in ref_bg:
            legacy_averages = int(ref_bg["averages"])
            self.spec1_widget.averages_spin.setValue(legacy_averages)
            self.spec2_widget.averages_spin.setValue(legacy_averages)

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

    def is_lamp_enabled(self, poll: bool = False) -> bool:
        """Check whether lamp TTL is enabled."""
        if poll:
            lamp_enabled, _ = self.get_arduino_state()
            return bool(lamp_enabled)
        return bool(getattr(self.arduino, "lamp_enabled", False))

    def is_avantes_enabled(self, poll: bool = False) -> bool:
        """Check whether Avantes TTL is enabled."""
        if poll:
            _, avantes_enabled = self.get_arduino_state()
            return bool(avantes_enabled)
        return bool(getattr(self.arduino, "avantes_enabled", False))

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
        if self.is_lamp_enabled() and self.is_avantes_enabled():
            self.arduino_status_label.setText("Status: Lamp + Avantes")
            self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            return True

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
        if not self.is_lamp_enabled() and self.is_avantes_enabled():
            self.arduino_status_label.setText("Status: Avantes Only")
            self.arduino_status_label.setStyleSheet("color: orange; font-weight: bold;")
            return True

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
            self.logger.info(
                f"REFERENCE: Measurement aborted by user "
                f"({len(self.reference_measurements)} of {self.reference_target_blocks} blocks collected)"
            )
            self.measuring_reference = False
            self.reference_measurements = []
            self.statusBar().showMessage("Reference measurement aborted")

        if self.measuring_background:
            self.logger.info(
                f"BACKGROUND: Measurement aborted by user "
                f"({len(self.background_measurements)} of {self.background_target_blocks} blocks collected)"
            )
            self.measuring_background = False
            self.background_measurements = []
            self.statusBar().showMessage("Background measurement aborted")

        # Re-enable buttons
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)
        self.pending_ref_bg_role = None

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

        n_avg = self.get_detector_average_count()
        n_blocks = self.ref_blocks_spin.value()
        self.reference_target_blocks = n_blocks
        self.pending_ref_bg_role = None
        self.measuring_reference = True
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button

        self.logger.info(
            f"REFERENCE: Starting measurement (lamp ON, hardware avg={n_avg} pulses, "
            f"blocks={n_blocks}, total pulses={n_avg * n_blocks})"
        )
        self.statusBar().showMessage(f"Measuring reference block 1/{n_blocks} (Avantes avg={n_avg})...")

        self.single_measurement(measurement_role="reference")

    def measure_background(self):
        """Measure background spectra by averaging N measurements (with lamp OFF)."""
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            api.QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            return

        # Ensure lamp is OFF
        self.set_avantes_only()

        n_avg = self.get_detector_average_count()
        n_blocks = self.ref_blocks_spin.value()
        self.background_target_blocks = n_blocks
        self.pending_ref_bg_role = None
        self.measuring_background = True
        self.background_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button

        self.logger.info(
            f"BACKGROUND: Starting measurement (lamp OFF, hardware avg={n_avg} pulses, "
            f"blocks={n_blocks}, total pulses={n_avg * n_blocks})"
        )
        self.statusBar().showMessage(f"Measuring background block 1/{n_blocks} (Avantes avg={n_avg})...")

        self.single_measurement(measurement_role="background")

    def measure_reference_complete(self):
        """Called when reference measurement is complete."""
        if self.reference_measurements:
            self.reference_ch1 = api.np.mean([m['ch1'] for m in self.reference_measurements], axis=0)
            self.reference_ch2 = api.np.mean([m['ch2'] for m in self.reference_measurements], axis=0)
            self.reference_wavelengths = self.spec1_widget.wavelengths
            self.clear_zero_baseline()
            self.has_reference = True

            # Display reference lines on plots (magenta/purple)
            if self.reference_wavelengths is not None:
                self.ref_curve1.setData(self.reference_wavelengths, self.reference_ch1)
                self.ref_curve2.setData(self.reference_wavelengths, self.reference_ch2)

            n_blocks = len(self.reference_measurements)
            n_avg = self.get_detector_average_count()
            self.logger.info(
                f"REFERENCE: Measurement complete (lamp ON, blocks={n_blocks}, "
                f"hardware avg={n_avg}, total pulses={n_blocks * n_avg})"
            )
            self.statusBar().showMessage(f"Reference measured ({n_blocks} blocks x {n_avg} pulses)")

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
        self.update_analysis_buttons()

    def set_zero_baseline_from_current(self):
        """Store current no-sample OD as a baseline to subtract from future OD."""
        data1 = self.spec1_widget.last_data
        data2 = self.spec2_widget.last_data
        wavelengths = self.spec1_widget.wavelengths

        if data1 is None or data2 is None or wavelengths is None:
            api.QMessageBox.warning(self, "Set Zero", "No current spectra available")
            return

        if not self.has_reference or not self.has_background:
            api.QMessageBox.warning(self, "Set Zero", "Measure background and reference first")
            return

        od_spectrum = self.calculate_optical_density(data1, data2, apply_zero_baseline=False)
        if od_spectrum is not None:
            self.zero_baseline_wavelengths = api.np.array(wavelengths, dtype=float, copy=True)
            self.zero_baseline_od = api.np.array(od_spectrum, dtype=float, copy=True)
            corrected_od = od_spectrum - self.zero_baseline_od
            self.curve_od.setData(self.zero_baseline_wavelengths, corrected_od)

        self.update_analysis_buttons()
        self.logger.info("ZERO: Baseline OD set from current spectra")
        self.statusBar().showMessage("Zero baseline set from current spectra")

    def measure_background_complete(self):
        """Called when background measurement is complete."""
        if self.background_measurements:
            self.background_ch1 = api.np.mean([m['ch1'] for m in self.background_measurements], axis=0)
            self.background_ch2 = api.np.mean([m['ch2'] for m in self.background_measurements], axis=0)
            self.clear_zero_baseline()
            self.has_background = True

            # Display background lines on plots (blue)
            # Use wavelengths from spectrometer (always available after connection)
            wavelengths = self.spec1_widget.wavelengths
            if wavelengths is not None:
                self.bg_curve1.setData(wavelengths, self.background_ch1)
                self.bg_curve2.setData(wavelengths, self.background_ch2)
                n_blocks = len(self.background_measurements)
                n_avg = self.get_detector_average_count()
                self.logger.info(
                    f"BACKGROUND: Measurement complete (lamp OFF, blocks={n_blocks}, "
                    f"hardware avg={n_avg}, total pulses={n_blocks * n_avg})"
                )
            else:
                self.logger.warning("BACKGROUND: Wavelengths not available for plotting")

            self.statusBar().showMessage(f"Background measured ({len(self.background_measurements)} blocks)")
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

    return {
        "get_settings_dict": get_settings_dict,
        "get_spectrometer_settings": get_spectrometer_settings,
        "apply_settings_dict": apply_settings_dict,
        "apply_spectrometer_settings": apply_spectrometer_settings,
        "load_settings_json": load_settings_json,
        "load_settings_from_file": load_settings_from_file,
        "save_settings_json_as": save_settings_json_as,
        "update_settings_json": update_settings_json,
        "write_settings_json": write_settings_json,
        "is_lamp_enabled": is_lamp_enabled,
        "is_avantes_enabled": is_avantes_enabled,
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
        "set_zero_baseline_from_current": set_zero_baseline_from_current,
        "measure_background_complete": measure_background_complete,
    }
