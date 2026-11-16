"""Implementation for toggle_data_collection and related operations."""


def _bind_avantes_dual_viewer_methods_toggle_data_collection(api):
    """Bind implementation to the owning module and its runtime state."""

    def toggle_data_collection(self):
        if self.current_measurement_role is not None or self.analysis_worker is not None:
            return
        if self.data_collection_active or self.collection_paused:
            self.set_collection_state(active=False, paused=False)
            self.log_run_event("stop")
            self.statusBar().showMessage(f"Collection stopped ({self.collection_point_index} points). Add Blank is available.")
            return
        if self.blank_schedule is not None or not self.validate_collection_rate(show_warning=True):
            return
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            api.QMessageBox.warning(self, "Start DC", "Connect both spectrometers first")
            return

        path = api.Path(self.save_folder_input.text()).expanduser() / (
            (self.save_name_input.text().strip() or "avantes_measurement") + ".h5"
        )
        old_path = self.collection_file_path
        resume = False
        if old_path and path.with_suffix("") == old_path.with_suffix("") and old_path.exists():
            mode = self.ask_collection_start_mode(old_path, self.collection_point_index)
            if mode is None:
                return
            resume = mode == "resume"

        try:
            if resume and old_path.suffix.lower() in {".h5", ".hdf5"}:
                run = api.AvantesRun(old_path)
                wavelengths, serials, epoch, count = run.info()
                if not self.match_run_hardware(wavelengths, serials):
                    raise ValueError("Connected spectrometers differ from the saved run")
                if not self.same_detector_setup(self.current_detector_setup(), run.detector_setup()):
                    raise ValueError("Restore the integration times and trigger modes used in the saved run")
                run = self.standard_run(run)
            else:
                if not self.has_reference or not self.has_background:
                    raise ValueError("Measure Background and Reference before starting a new run")
                wavelengths, serials = self.current_hardware()
                if not self.calibration_matches_detector_setup():
                    raise ValueError("Remeasure Background and Reference with the current detector settings")
                offset = 0.0
                if resume:
                    loaded_grid = self.od_heatmap_wavelengths
                    if wavelengths[0].shape != loaded_grid.shape or not api.np.allclose(wavelengths[0], loaded_grid, atol=1e-3, rtol=0):
                        raise ValueError("Ch1 wavelength calibration differs from the DAT file")
                    offset = self.get_resume_collection_time_offset(self.od_heatmap_times)
                epoch = api.time.time() - offset
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    path = self.suggest_new_collection_file_path(path)
                settings = self.get_settings_dict()
                settings["exposure"] = dict(self.exposure_setup, start_offset_s=offset)
                settings["emulator"] = dict(enabled=self.emulate_hardware, demo_kinetics=self.demo_kinetics_enabled,
                                            duration_s=self.demo_kinetics_duration_s, max_od=self.demo_kinetics_max_od)
                run = api.AvantesRun.create(path, wavelengths, serials, epoch, settings, self.calibration_blocks)
                count = 0
                if resume:
                    for t, row in zip(self.od_heatmap_times, self.od_heatmap_rows):
                        count = run.append(t, api.np.nan, None, None, None, row, {"source": "legacy_dat"})
                    run.append_event("import_dat", api.time.time(), path=str(old_path), rows=count)
                initial = self.calibration_blocks.get("initial_blank")
                if initial:
                    block = initial[0]
                    od = self.calculate_optical_density(*api.valid_counts(block), apply_zero_baseline=False)
                    run.add_blank(offset, initial, od, initial=True)
            self.restore_run_calibration(run)
            run.append_event("resume" if resume else "start", api.time.time())
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.logger.exception("Cannot start data collection")
            api.QMessageBox.critical(self, "Start DC", str(api.exc))
            return

        if self.continuous_mode:
            self.stop_live_preview()
        self.collection_run = run
        self.exposure_state = run.irradiation_state()
        self.run_volumes = run.sample_volumes()
        self.collection_file_path = run.path
        self.collection_start_time = epoch
        self.collection_point_index = count
        self.save_folder_input.setText(str(run.path.parent))
        self.save_name_input.setText(run.path.stem)
        self.update_loaded_collection_label(run.path)
        self.reset_od_heatmap()
        self.collection_point_start_time = None
        self.set_collection_state(active=True, paused=False)
        self.collect_data_point()

    def collect_data_point(self):
        """Collect a data point during active data collection."""
        if not self.data_collection_active or not self.has_reference or not self.has_background:
            return
        if self.current_measurement_role is not None:
            self.collection_timer.start(50)
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
        if not self.single_measurement(averages_override=n_avg, measurement_role="collection"):
            self.set_collection_state(active=False, paused=True)
            self.log_run_event("acquisition_paused", reason="spectrometer not ready")

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
        warmup_s = max(0.0, float(self.lamp_warmup_seconds))
        lamp_off_gap_s = seconds_until_due - warmup_s
        min_off_s = max(0.0, float(self.lamp_min_off_seconds))
        can_save_lamp = (
            self.auto_lamp_management_enabled
            and self.lamp_off_between_points_enabled
            and lamp_off_gap_s >= min_off_s
        )

        if not self.auto_lamp_management_enabled:
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(f"Next point in {seconds_until_due:.0f}s")
        elif can_save_lamp:
            if self.is_lamp_enabled():
                self.set_lamp_off(reschedule=False)
            warmup_delay_ms = int(lamp_off_gap_s * 1000)
            self.lamp_warmup_timer.start(warmup_delay_ms)
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(
                f"Next point in {seconds_until_due:.0f}s; lamp warmup starts in {lamp_off_gap_s:.0f}s"
            )
        else:
            if not self.is_lamp_enabled():
                self.prepare_lamp_for_collection()
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(f"Next point in {seconds_until_due:.0f}s; lamp stays on")
            if (
                self.auto_lamp_management_enabled
                and self.lamp_off_between_points_enabled
                and lamp_off_gap_s > 0
            ):
                self.logger.info(
                    f"DATA COLLECTION: Lamp stays on; off gap {lamp_off_gap_s:.1f}s "
                    f"is shorter than minimum {min_off_s:.1f}s"
                )
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
            state = "Paused" if self.collection_paused else "Next: --"
            self.collection_countdown_label.setText(f"{state} | Points: {points}")
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
            warmup_start_in = remaining - max(0.0, float(self.lamp_warmup_seconds))
            if warmup_start_in >= max(0.0, float(self.lamp_min_off_seconds)):
                text += f" | Lamp in {self.format_seconds_for_countdown(warmup_start_in)}"
            else:
                text += " | Lamp on"

        self.collection_countdown_label.setText(text)

    def browse_save_folder(self):
        """Choose folder for exported and collected files."""
        folder = api.QFileDialog.getExistingDirectory(self, "Choose Save Folder", self.save_folder_input.text())
        if folder:
            self.save_folder_input.setText(folder)

    def update_loaded_collection_label(self, path: api.Optional[api.Path]):
        """Show loaded collection path in the Data Collection panel."""
        if not hasattr(self, "loaded_collection_label"):
            return
        if path is None:
            self.loaded_collection_label.setText("No run opened")
            self.loaded_collection_label.setToolTip("")
            return
        text = str(path)
        self.loaded_collection_label.setText(text)
        self.loaded_collection_label.setToolTip(text)

    def ask_collection_start_mode(self, path: api.Path, n_points: int) -> api.Optional[str]:
        """Ask whether to continue an existing acquisition or start a new file."""
        msg = api.QMessageBox(self)
        msg.setIcon(api.QMessageBox.Question)
        msg.setWindowTitle("Start Data Collection")
        msg.setText(f"Existing run:\n{path}")
        action = "Import the DAT and resume in a new HDF5 file?" if path.suffix.lower() == ".dat" else "Resume this HDF5 run?"
        msg.setInformativeText(f"{n_points} existing points. {action}")
        resume_btn = msg.addButton("Resume", api.QMessageBox.AcceptRole)
        new_btn = msg.addButton("Start New", api.QMessageBox.DestructiveRole)
        msg.addButton("Cancel", api.QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked == resume_btn:
            return "resume"
        if clicked == new_btn:
            return "new"
        return None

    def suggest_new_collection_file_path(self, path):
        """Find a free sibling name. HDF5 exclusive creation also checks for races."""
        for index in range(1, 1000):
            candidate = path.with_name(f"{path.stem}_{index:03d}.h5")
            if not candidate.exists():
                return candidate
        raise ValueError("Choose a new run name")

    def get_resume_collection_time_offset(self, times) -> float:
        """Return first resumed timestamp anchor: last time plus last positive delta."""
        if not times:
            return 0.0
        clean_times = sorted(float(value) for value in times)
        last_time = clean_times[-1]
        if len(clean_times) < 2:
            return last_time + float(self.collection_rate_spin.value())

        deltas = [
            clean_times[index] - clean_times[index - 1]
            for index in range(1, len(clean_times))
            if clean_times[index] > clean_times[index - 1]
        ]
        if not deltas:
            return last_time + float(self.collection_rate_spin.value())
        return last_time + deltas[-1]

    def load_collection_dat(self):
        """Load a saved data-collection DAT file and display it as an OD map."""
        if not self.may_open_collection():
            return
        filename, _ = api.QFileDialog.getOpenFileName(
            self,
            "Load Avantes Measurement DAT",
            self.save_folder_input.text(),
            "Avantes DAT (*.dat);;All Files (*)",
        )
        if not filename:
            return

        try:
            self.load_collection_dat_file(api.Path(filename))
        except Exception as e:
            self.logger.error(f"DATA LOAD: Failed to load {filename} - {e}")
            api.QMessageBox.critical(self, "Load DAT Error", f"Failed to load DAT file:\n{e}")

    def load_collection_dat_file(self, path: api.Path):
        """Load one DAT file written by save_collection_point()."""
        path = api.Path(path)
        with path.open("r", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")

        if len(header) < 2 or header[0] != "time_s":
            raise ValueError("Expected first header column to be time_s")

        wavelengths = api.np.array([float(value) for value in header[1:]], dtype=float)
        data = api.np.loadtxt(path, delimiter="\t", skiprows=1)
        data = api.np.atleast_2d(data)
        if data.shape[1] != len(wavelengths) + 1:
            raise ValueError(
                f"DAT column count mismatch: expected {len(wavelengths) + 1}, got {data.shape[1]}"
            )

        times = api.np.asarray(data[:, 0], dtype=float)
        rows = api.np.asarray(data[:, 1:], dtype=float)
        self.od_heatmap_wavelengths = wavelengths
        self.od_heatmap_times = [float(value) for value in times]
        self.od_heatmap_rows = [api.np.array(row, dtype=float) for row in rows]
        self.collection_run = None
        self.collection_point_index = len(rows)
        self.set_open_collection_path(path)

        if len(rows):
            self.curve_od.setData(wavelengths, rows[-1])
            if not self.od_x_auto_check.isChecked():
                self.plot_od.setXRange(self.od_x_min_spin.value(), self.od_x_max_spin.value(), padding=0)
            if not self.od_y_auto_check.isChecked():
                self.plot_od.setYRange(self.od_y_min_spin.value(), self.od_y_max_spin.value(), padding=0)

        self.show_od_heatmap_window()
        if self.od_heatmap_window is not None:
            self.od_heatmap_window.setWindowTitle(f"OD Time Map - {path.name}")
        self.statusBar().showMessage(f"Loaded DAT: {path.name} ({len(rows)} points)")
        self.logger.info(f"DATA LOAD: Loaded {path} ({len(rows)} points, {len(wavelengths)} wavelengths)")

    def update_analysis_buttons(self):
        busy = self.current_measurement_role is not None or self.analysis_worker is not None
        running = self.data_collection_active or self.collection_paused
        calibrated = self.has_reference and self.has_background
        can_append_blank = self.collection_run is not None and not busy
        self.start_collection_btn.setEnabled(
            not busy and (running or self.blank_schedule is None and (calibrated or self.collection_run is not None))
        )
        self.pause_collection_btn.setEnabled(
            not busy and running and (not self.collection_paused or self.blank_schedule is None)
        )
        self.track_wl_btn.setEnabled(calibrated)
        preparing = not running and not busy and self.blank_schedule is None
        self.measure_ref_btn.setEnabled(preparing)
        self.measure_bg_btn.setEnabled(preparing)
        self.initial_blank_btn.setEnabled(preparing and calibrated)
        self.zero_reference_btn.setEnabled(preparing and calibrated and self.last_sample_pair is not None)
        self.clear_btn.setEnabled(preparing)
        self.continuous_btn.setEnabled(not running and self.blank_schedule is None and self.analysis_worker is None)
        for action in (self.recalculate_action, self.mcr_action):
            action.setEnabled(self.can_analyze_run())
        can_show_mcr = self.collection_run is not None and self.analysis_worker is None
        self.show_mcr_action.setEnabled(can_show_mcr)
        self.show_mcr_btn.setEnabled(can_show_mcr)
        self.geometry_action.setEnabled(self.may_open_collection())
        rate, irradiating = self.exposure_state
        self.irradiation_action.setEnabled(can_show_mcr)
        self.irradiation_action.setText("Mark irradiation off" if irradiating else "Mark irradiation on")
        if api.np.isfinite(rate):
            self.irradiation_action.setToolTip(f"Recording state for {rate:g} Gy/h")
        else:
            self.irradiation_action.setToolTip("Record the state of the external irradiation source")
        self.update_exposure_label()
        self.add_blank_btn.setText("Capture Blank" if self.blank_due else "Add Blank…")
        if self.blank_due:
            can_append_blank = can_append_blank and not self.data_collection_active
        else:
            can_append_blank = self.collection_run is not None and self.blank_schedule is None and (not busy or running)
        self.add_blank_btn.setEnabled(can_append_blank and self.analysis_worker is None)
        self.cancel_blank_btn.setVisible(self.blank_schedule is not None)
        self.cancel_blank_btn.setEnabled(self.current_measurement_role != "blank")
        for widget in (self.spec1_widget, self.spec2_widget):
            widget.connect_btn.setEnabled(not running and not busy)
            widget.integration_spin.setEnabled(not running and not busy)
            widget.trigger_combo.setEnabled(not running and not busy)

    def clear_zero_baseline(self):
        """Clear the stored OD zero baseline."""
        self.zero_baseline_wavelengths = None
        self.zero_baseline_od = None
        self.calibration_blocks.pop("sample_t0", None)

    def reset_od_heatmap(self):
        """Clear OD time map for a new data collection run."""
        self.od_heatmap_rows = []
        self.od_heatmap_times = []
        self.od_heatmap_wavelengths = None
        if self.od_heatmap_window is not None:
            self.od_heatmap_window.detail_range = None
        self.render_od_heatmap()

    def render_od_heatmap(self):
        window = self.od_heatmap_window
        if window is None or self.analysis_worker is not None:
            return
        if self.collection_run is not None:
            try:
                wavelengths, rows, times = self.collection_run.view(
                    window.od_source.currentData(), window.detail_range
                )
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                self.logger.error("Unable to read OD map: %s", api.exc)
                return
        else:
            stride = max(1, (len(self.od_heatmap_rows) + 499) // 500)
            wavelengths = self.od_heatmap_wavelengths
            rows = self.od_heatmap_rows[::stride]
            times = self.od_heatmap_times[::stride]
        window.set_heatmap(wavelengths, rows, times, self.collection_point_index)

    def toggle_od_heatmap_window(self):
        """Open the floating OD time map, or close it if already visible."""
        if self.od_heatmap_window is not None:
            window = self.od_heatmap_window
            self.od_heatmap_window = None
            self.show_od_map_btn.setText("Show DC")
            window.close()
            return

        self.show_od_heatmap_window()

    def show_od_heatmap_window(self):
        """Open or raise the floating OD time map window."""
        if self.od_heatmap_window is None:
            self.od_heatmap_window = api.ODHeatmapWindow(self)
        self.render_od_heatmap()
        self.od_heatmap_window.show()
        self.od_heatmap_window.raise_()
        self.od_heatmap_window.activateWindow()
        self.show_od_map_btn.setText("Hide DC")

    def get_export_base_path(self) -> api.Path:
        """Return base path for manual export files."""
        save_dir = api.Path(self.save_folder_input.text()).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)
        base_name = self.save_name_input.text().strip() or "avantes_measurement"
        return save_dir / base_name

    def open_wavelength_tracker(self):
        """Open wavelength tracking window."""
        if not self.has_reference or not self.has_background:
            api.QMessageBox.warning(self, "Error", "Please measure reference and background first")
            return

        wavelength = self.track_wavelength_spin.value()

        if self.wavelength_tracker_window is None:
            self.wavelength_tracker_window = api.WavelengthTrackerWindow(self, wavelength)
            self.wavelength_tracker_window.show()
        else:
            self.wavelength_tracker_window.set_wavelength(wavelength)
            self.wavelength_tracker_window.show()
            self.wavelength_tracker_window.raise_()
            self.wavelength_tracker_window.activateWindow()

    return {
        "toggle_data_collection": toggle_data_collection,
        "collect_data_point": collect_data_point,
        "schedule_next_collection_point": schedule_next_collection_point,
        "on_collection_rate_changed": on_collection_rate_changed,
        "schedule_collection_due_time": schedule_collection_due_time,
        "prepare_lamp_for_collection": prepare_lamp_for_collection,
        "format_seconds_for_countdown": format_seconds_for_countdown,
        "update_collection_countdown_label": update_collection_countdown_label,
        "browse_save_folder": browse_save_folder,
        "update_loaded_collection_label": update_loaded_collection_label,
        "ask_collection_start_mode": ask_collection_start_mode,
        "suggest_new_collection_file_path": suggest_new_collection_file_path,
        "get_resume_collection_time_offset": get_resume_collection_time_offset,
        "load_collection_dat": load_collection_dat,
        "load_collection_dat_file": load_collection_dat_file,
        "update_analysis_buttons": update_analysis_buttons,
        "clear_zero_baseline": clear_zero_baseline,
        "reset_od_heatmap": reset_od_heatmap,
        "render_od_heatmap": render_od_heatmap,
        "toggle_od_heatmap_window": toggle_od_heatmap_window,
        "show_od_heatmap_window": show_od_heatmap_window,
        "get_export_base_path": get_export_base_path,
        "open_wavelength_tracker": open_wavelength_tracker,
    }
