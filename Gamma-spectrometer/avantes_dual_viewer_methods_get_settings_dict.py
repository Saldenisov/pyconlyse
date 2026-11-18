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

    def apply_settings_dict(self, settings: dict, *, apply_trigger_frequency=True):
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
            if not apply_trigger_frequency or not self.set_arduino_frequency_hz(frequency):
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
        if not self.may_open_collection():
            self.statusBar().showMessage("Stop acquisition and finish the blank schedule before loading settings")
            return
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

    def set_lamp_and_avantes(self):
        """Set Arduino to trigger both lamp and Avantes."""
        if self.is_lamp_enabled() and self.is_avantes_enabled():
            self.arduino_status_label.setText("Status: Lamp + Avantes")
            self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            return True

        if self.arduino.set_mode("LAMP AND AVANTES"):
            self.arduino_status_label.setText("Status: Lamp + Avantes")
            self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.logger.info("ARDUINO: Lamp + Avantes mode activated")

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
            if not self.check_sample_metadata():
                return
            if self.collection_run is not None:
                try:
                    self.ensure_standard_run()
                except (OSError, ValueError, KeyError, RuntimeError) as exc:
                    api.QMessageBox.warning(self, "Live Preview", str(exc))
                    return
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
        """Stop after the current readout, keeping the raw capture on disk."""
        self.calibration_start_timer.stop()
        if self.current_measurement_role is None:
            self.calibration_capture = None
        elif self.calibration_capture is not None:
            self.calibration_capture["aborted"] = True
        self.stop_measure_btn.setEnabled(False)
        self.statusBar().showMessage("Capture stopped. Recorded blocks remain in HDF5.")
        self.update_analysis_buttons()

    def open_preparation_run(self):
        name = self.save_name_input.text().strip()
        if not name or name.endswith(".") or any(c in name for c in '<>:"/\\|?*') or any(ord(c) < 32 for c in name):
            raise ValueError("Enter a valid run filename before measuring Background")
        folder = api.Path(self.save_folder_input.text()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (name + ".h5")
        wavelengths, serials = self.current_hardware()
        settings = self.get_settings_dict()
        settings.update(
            sample_name=name, sample_comment=self.sample_comment_input.text().strip(),
            exposure=dict(self.exposure_setup),
            emulator=dict(enabled=self.emulate_hardware, demo_kinetics=self.demo_kinetics_enabled,
                          duration_s=self.demo_kinetics_duration_s, max_od=self.demo_kinetics_max_od),
        )
        try:
            self.preparation_run = api.AvantesRun.create(path, wavelengths, serials, api.time.time(), settings, {})
        except FileExistsError as exc:
            raise ValueError("That HDF5 file already exists. Enter a new name or open the existing file.") from exc
        self.update_loaded_collection_label(path)
        return self.preparation_run

    def measure_background(self):
        self.measure_calibration("background")

    def measure_reference(self):
        self.measure_calibration("reference")

    def measure_calibration(self, role):
        if self.collection_run is not None:
            if (role not in {"background", "empty"} or self.data_collection_active
                    or self.current_measurement_role is not None or self.calibration_capture is not None
                    or self.analysis_worker is not None):
                return
            if not self.check_sample_metadata(require_reference=True):
                return
            try:
                run = self.ensure_standard_run()
                wavelengths, serials, _, _ = run.info()
                if not self.match_run_hardware(wavelengths, serials):
                    raise ValueError("Connect the same spectrometers used in the run")
                if not self.same_detector_setup(self.current_detector_setup(), run.detector_setup()):
                    raise ValueError("Use the same integration times and trigger modes as the run")
                self.start_spectral_capture(run, f"{role}_check")
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                api.QMessageBox.critical(self, "Calibration check", str(exc))
            return
        if not self.may_open_collection():
            return
        if not self.save_name_input.text().strip():
            api.QMessageBox.information(self, "Background", "Enter the sample name first.")
            self.save_name_input.setFocus()
            return
        if not self.check_sample_metadata(require_reference=role == "reference"):
            return
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            self.statusBar().showMessage("Connect both spectrometers before measuring")
            return
        if (role == "empty" and not self.has_background or role == "reference" and "empty" not in self.calibration_blocks):
            return
        try:
            run = self.preparation_run or self.open_preparation_run()
            if not self.same_detector_setup(self.current_detector_setup(), run.detector_setup()):
                raise ValueError("Restore the detector settings used for Background")
            if role == "reference":
                run.set_prepared_exposure(self.exposure_setup)
            self.start_spectral_capture(run, role)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            api.QMessageBox.critical(self, "Calibration capture", str(exc))
        self.update_analysis_buttons()

    def start_spectral_capture(self, run, role):
        if self.continuous_mode:
            self.stop_live_preview()
        repeats = self.ref_repeats_spin.value()
        blocks = self.ref_blocks_spin.value()
        name = run.begin_capture(role, repeats, blocks)
        self.calibration_capture = dict(run=run, name=name, role=role, target=repeats * blocks, aborted=False)
        self.update_analysis_buttons()
        self.stop_measure_btn.setEnabled(True)
        dark = role in {"background", "background_check"}
        self.statusBar().showMessage("Preparing " + ("dark acquisition" if dark else "lamp") + "…")
        warmup = role in {"empty", "empty_check", "reference"} and not (self.is_lamp_enabled() and self.is_avantes_enabled())
        try:
            lamp_ready = self.set_avantes_only() if dark else self.set_lamp_and_avantes()
            if not lamp_ready:
                raise RuntimeError("Could not set the lamp and spectrometer triggers")
        except Exception:
            self.stop_measurement()
            raise
        if warmup:
            self.statusBar().showMessage("Warming the lamp before acquisition…")
            self.calibration_start_timer.start(1000)
        else:
            self.begin_spectral_readout()

    def begin_spectral_readout(self):
        capture = self.calibration_capture
        if capture is not None and not self.single_measurement(measurement_role=capture["role"]):
            self.stop_measurement()
            if self.closing_requested:
                api.QTimer.singleShot(0, self.close)

    def complete_spectral_capture(self, role, blocks):
        if role == "blank":
            self.save_blank(blocks)
            return
        if role in {"background_check", "empty_check"}:
            label = role.partition("_")[0].title()
            self.statusBar().showMessage(f"{label} check saved ({len(blocks)} blocks)")
            self.blank_status.setText(f"{label} check saved. The stored calibration remains selected.")
            return
        ch1, ch2 = api.mean_counts(blocks)
        repeated = role in self.calibration_blocks
        if repeated:
            if role in {"background", "empty"}:
                self.empty_zero_selected = False
            self.reference_zero_selected = False
            self.calibration_blocks.pop("initial_blank", None)
            self.curve_od.setData([], [])
            self.plot_od.setTitle("Optical Density (OD) Spectrum")
            self.blank_status.setText("The latest capture is selected. Set Zero is optional.")
        self.calibration_blocks[role] = blocks
        w1, w2 = self.current_hardware()[0]
        if role == "background":
            self.background_ch1, self.background_ch2 = ch1, ch2
            self.has_background = True
            self.bg_curve1.setData(w1, ch1)
            self.bg_curve2.setData(w2, ch2)
        elif role == "empty":
            self.curve1.setData(w1, ch1)
            self.curve2.setData(w2, ch2)
        elif role == "reference":
            self.reference_ch1, self.reference_ch2 = ch1, ch2
            self.reference_wavelengths = w1
            self.has_reference = True
            od = self.calculate_calibration_od((ch1, ch2), api.mean_counts(self.calibration_blocks["empty"]))
            self.curve_od.setData(w1, od)
            self.plot_od.setTitle("Reference OD vs Empty")
            self.ref_curve1.setData(w1, ch1)
            self.ref_curve2.setData(w2, ch2)
        self.statusBar().showMessage(f"{role.title()} saved and selected ({len(blocks)} blocks)")

    def calculate_calibration_od(self, counts, baseline):
        return api.optical_density(
            *counts, baseline, (self.background_ch1, self.background_ch2), self.current_hardware()[0]
        )

    def set_calibration_zero(self, role):
        if not self.may_open_collection() or self.preparation_run is None or role not in self.calibration_blocks:
            return
        if not self.calibration_matches_detector_setup():
            self.statusBar().showMessage("Restore the detector settings used for calibration.")
            return
        blocks = self.calibration_blocks[role]
        counts = api.mean_counts(blocks)
        od = self.calculate_calibration_od(counts, counts)
        if not api.np.any(api.np.isfinite(od)):
            self.statusBar().showMessage("No valid optical density. Check the lamp, dark counts and saturation.")
            return
        try:
            self.preparation_run.set_preparation_zero(role, od)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            api.QMessageBox.critical(self, "Save calibration zero", str(exc))
            return
        if role == "empty":
            self.empty_zero_selected = True
        else:
            self.reference_ch1, self.reference_ch2 = counts
            self.reference_wavelengths = self.current_hardware()[0][0]
            self.calibration_blocks["initial_blank"] = blocks
            self.has_reference = True
            self.reference_zero_selected = True
        self.plot_od.setTitle(f"Optical Density vs {role.title()} Zero")
        self.curve_od.setData(self.current_hardware()[0][0], od)
        if role == "empty":
            text = "Measure the reference, or use the saved reference to start collection."
        else:
            text = "Insert the sample, then Start DC."
        self.blank_status.setText(text)
        self.statusBar().showMessage(f"{role.title()} zero saved to HDF5")
        self.update_analysis_buttons()

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
        "open_preparation_run": open_preparation_run,
        "measure_calibration": measure_calibration,
        "start_spectral_capture": start_spectral_capture,
        "begin_spectral_readout": begin_spectral_readout,
        "complete_spectral_capture": complete_spectral_capture,
        "calculate_calibration_od": calculate_calibration_od,
        "set_calibration_zero": set_calibration_zero,
        "measure_reference": measure_reference,
        "measure_background": measure_background,
    }
