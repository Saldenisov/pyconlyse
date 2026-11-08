"""Implementation for toggle_data_collection and related operations."""


def _bind_avantes_dual_viewer_methods_toggle_data_collection(api):
    """Bind implementation to the owning module and its runtime state."""

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
            previous_collection_file_path = self.collection_file_path
            self.collection_file_path = save_dir / f"{base_name}.dat"
            resume_collection = False
            has_loaded_points = bool(self.collection_data)
            target_is_loaded = (
                self.loaded_collection_file_path is not None
                and self.collection_file_path == self.loaded_collection_file_path
            )
            target_is_current = (
                self.collection_file_path.exists()
                and has_loaded_points
                and previous_collection_file_path is not None
                and self.collection_file_path == previous_collection_file_path
            )
            if target_is_loaded or target_is_current:
                start_mode = self.ask_collection_start_mode(self.collection_file_path, len(self.collection_data))
                if start_mode is None:
                    return
                resume_collection = start_mode == "resume"
                if resume_collection and not self.can_resume_collection_wavelengths():
                    return
                if not resume_collection:
                    new_path = self.choose_new_collection_file_path(self.collection_file_path)
                    if new_path is None:
                        return
                    self.collection_file_path = new_path
                    self.save_folder_input.setText(str(new_path.parent))
                    self.save_name_input.setText(new_path.stem)

            if self.continuous_mode:
                self.stop_live_preview()

            self.data_collection_active = True
            if resume_collection:
                self.collection_point_index = len(self.collection_data)
                existing_times = [float(point.get("time", 0.0)) for point in self.collection_data]
                self.collection_time_offset_s = self.get_resume_collection_time_offset(existing_times)
                self.loaded_collection_file_path = self.collection_file_path
                self.update_loaded_collection_label(self.collection_file_path)
            else:
                self.collection_data = []
                self.collection_point_index = 0
                self.collection_time_offset_s = 0.0
                self.loaded_collection_file_path = None
                self.update_loaded_collection_label(None)
                self.reset_od_heatmap()
                if self.collection_file_path.exists():
                    self.collection_file_path.unlink()
            self.collection_start_time = api.time.time()
            self.collection_point_start_time = None
            self.collection_next_due_time = None

            self.start_collection_btn.setText("Stop DC")
            self.collection_countdown_timer.start()
            self.update_collection_countdown_label()
            self.logger.info(
                f"DATA COLLECTION: Started ({'resume' if resume_collection else 'new'}, "
                f"rate={self.collection_rate_spin.value()}s, detector_avg={self.get_detector_average_count()}, "
                f"file={self.collection_file_path})"
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
            api.QTimer.singleShot(50, self.collect_data_point)
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
            self.loaded_collection_label.setText("No DAT loaded")
            self.loaded_collection_label.setToolTip("")
            return
        text = str(path)
        self.loaded_collection_label.setText(text)
        self.loaded_collection_label.setToolTip(text)

    def ask_collection_start_mode(self, path: api.Path, n_points: int) -> api.Optional[str]:
        """Ask whether to append to a loaded DAT file or start from scratch."""
        msg = api.QMessageBox(self)
        msg.setIcon(api.QMessageBox.Question)
        msg.setWindowTitle("Start Data Collection")
        msg.setText(f"DAT file already loaded:\n{path}")
        msg.setInformativeText(f"{n_points} existing points found. Continue writing this file?")
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

    def suggest_new_collection_file_path(self, path: api.Path) -> api.Path:
        """Return an unused DAT path next to the loaded file."""
        for index in range(1, 1000):
            suffix = "_new" if index == 1 else f"_new_{index}"
            candidate = path.with_name(f"{path.stem}{suffix}.dat")
            if not candidate.exists():
                return candidate
        return path.with_name(f"{path.stem}_{api.datetime.now():%Y%m%d_%H%M%S}.dat")

    def choose_new_collection_file_path(self, current_path: api.Path) -> api.Optional[api.Path]:
        """Choose a new DAT path and reflect it in the main collection controls."""
        default_path = self.suggest_new_collection_file_path(current_path)
        filename, _ = api.QFileDialog.getSaveFileName(
            self,
            "Start New DAT",
            str(default_path),
            "Avantes DAT (*.dat);;All Files (*)",
        )
        if not filename:
            return None

        path = api.Path(filename).expanduser()
        if path.suffix.lower() != ".dat":
            path = path.with_suffix(".dat")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            api.QMessageBox.critical(self, "Save Folder Error", f"Cannot use save folder:\n{e}")
            return None

        if path.exists():
            reply = api.QMessageBox.question(
                self,
                "Overwrite DAT?",
                f"File exists:\n{path}\n\nOverwrite it?",
                api.QMessageBox.Yes | api.QMessageBox.No,
                api.QMessageBox.No,
            )
            if reply != api.QMessageBox.Yes:
                return None

        self.save_folder_input.setText(str(path.parent))
        self.save_name_input.setText(path.stem)
        return path

    def can_resume_collection_wavelengths(self) -> bool:
        """Ensure current spectrometer wavelengths match loaded DAT columns."""
        current = self.spec1_widget.wavelengths if self.spec1_widget else None
        loaded = self.od_heatmap_wavelengths
        if current is None or loaded is None:
            return True

        current = api.np.asarray(current, dtype=float)
        loaded = api.np.asarray(loaded, dtype=float)
        if current.shape != loaded.shape or not api.np.allclose(current, loaded, atol=1e-3, rtol=0):
            api.QMessageBox.warning(
                self,
                "Resume Error",
                "Cannot resume this DAT file: current wavelength grid differs from loaded file.",
            )
            return False
        return True

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
        self.collection_data = [
            {"time": float(t), "od": api.np.array(row, dtype=float)}
            for t, row in zip(times, rows)
        ]
        self.collection_point_index = len(self.collection_data)
        self.collection_time_offset_s = self.get_resume_collection_time_offset(self.od_heatmap_times)
        self.collection_file_path = path
        self.loaded_collection_file_path = path
        self.save_folder_input.setText(str(path.parent))
        self.save_name_input.setText(path.stem)
        self.update_loaded_collection_label(path)

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
        """Enable controls that require complete OD prerequisites."""
        enabled = self.has_reference and self.has_background
        self.start_collection_btn.setEnabled(enabled)
        self.track_wl_btn.setEnabled(enabled)
        has_current = self.spec1_widget.last_data is not None and self.spec2_widget.last_data is not None
        self.zero_reference_btn.setEnabled(enabled and has_current)

    def clear_zero_baseline(self):
        """Clear the stored OD zero baseline."""
        self.zero_baseline_wavelengths = None
        self.zero_baseline_od = None

    def reset_od_heatmap(self):
        """Clear OD time map for a new data collection run."""
        self.od_heatmap_rows = []
        self.od_heatmap_times = []
        self.od_heatmap_wavelengths = None
        self.render_od_heatmap()

    def update_od_heatmap(
        self,
        wavelengths: api.np.ndarray,
        od_spectrum: api.Optional[api.np.ndarray],
        elapsed_time: api.Optional[float] = None,
    ):
        """Append one OD spectrum to the time map."""
        if wavelengths is None or od_spectrum is None:
            return

        self.od_heatmap_wavelengths = wavelengths
        self.od_heatmap_rows.append(api.np.array(od_spectrum, dtype=float))
        if elapsed_time is None:
            elapsed_time = float(len(self.od_heatmap_rows))
        self.od_heatmap_times.append(float(elapsed_time))
        self.render_od_heatmap()

    def render_od_heatmap(self):
        """Render heatmap data if floating window exists."""
        if self.od_heatmap_window is not None:
            self.od_heatmap_window.set_heatmap(
                self.od_heatmap_wavelengths,
                self.od_heatmap_rows,
                self.od_heatmap_times,
            )

    def toggle_od_heatmap_window(self):
        """Open the floating OD time map, or close it if already visible."""
        if self.od_heatmap_window is not None:
            window = self.od_heatmap_window
            self.od_heatmap_window = None
            self.show_od_map_btn.setText("Show")
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
        self.show_od_map_btn.setText("Hide")

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
        "choose_new_collection_file_path": choose_new_collection_file_path,
        "can_resume_collection_wavelengths": can_resume_collection_wavelengths,
        "get_resume_collection_time_offset": get_resume_collection_time_offset,
        "load_collection_dat": load_collection_dat,
        "load_collection_dat_file": load_collection_dat_file,
        "update_analysis_buttons": update_analysis_buttons,
        "clear_zero_baseline": clear_zero_baseline,
        "reset_od_heatmap": reset_od_heatmap,
        "update_od_heatmap": update_od_heatmap,
        "render_od_heatmap": render_od_heatmap,
        "toggle_od_heatmap_window": toggle_od_heatmap_window,
        "show_od_heatmap_window": show_od_heatmap_window,
        "get_export_base_path": get_export_base_path,
        "open_wavelength_tracker": open_wavelength_tracker,
    }
