"""Implementation for analysis and related operations."""


def _bind_avantes_dual_viewer_methods_analysis(api):
    """Bind implementation to the owning module and its runtime state."""

    def may_open_collection(self):
        return not (self.data_collection_active or self.collection_paused
                    or self.calibration_capture is not None or self.current_measurement_role is not None
                    or self.analysis_worker is not None)

    def load_collection_hdf5(self):
        if not self.may_open_collection():
            return
        filename, _ = api.QFileDialog.getOpenFileName(
            self, "Open Avantes HDF5", self.save_folder_input.text(), "Avantes HDF5 (*.h5 *.hdf5)"
        )
        if not filename:
            return
        try:
            self.load_collection_hdf5_file(api.Path(filename))
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            api.QMessageBox.critical(self, "Open HDF5", str(exc))

    def load_collection_hdf5_file(self, path):
        run = api.AvantesRun(path)
        wavelengths, serials, epoch, count = run.info()
        pending, comment = run.preparation_info()
        if pending:
            if not self.match_run_hardware(wavelengths, serials):
                raise ValueError("Connect the spectrometers used for calibration to continue this run")
            self.new_named_run()
            self.preparation_run = run
            self.set_open_collection_path(run.path)
            self.sample_comment_input.setText(comment)
            blocks = run.calibration_blocks()
            for role in ("background", "empty", "reference"):
                if role in blocks:
                    self.complete_spectral_capture(role, blocks[role])
            for role in ("empty", "reference"):
                if run.has_preparation_zero(role):
                    self.set_calibration_zero(role)
            self.update_analysis_buttons()
            return
        self.new_named_run()
        self.collection_run = run
        self.collection_start_time = epoch
        self.collection_point_index = count
        self.set_open_collection_path(run.path)
        self.sample_comment_input.setText(comment)
        self.reset_od_heatmap()
        self.show_od_heatmap_window()

    def set_open_collection_path(self, path):
        self.collection_file_path = path
        self.exposure_state = self.collection_run.irradiation_state() if self.collection_run else (api.np.nan, False)
        self.run_volumes = self.collection_run.sample_volumes() if self.collection_run else (api.np.nan, api.np.nan)
        self.save_folder_input.setText(str(path.parent))
        self.save_name_input.setText(path.stem)
        self.blank_status.clear()
        self.update_loaded_collection_label(path)
        self.update_collection_countdown_label()
        self.update_analysis_buttons()

    def edit_exposure_setup(self):
        if not self.may_open_collection():
            return
        dialog = api.QDialog(self)
        dialog.setWindowTitle("Dose and sample geometry for the next run")
        form = api.QFormLayout(dialog)
        has_rate = api.QCheckBox("Dose rate is known")
        has_rate.setChecked("dose_rate_gy_h" in self.exposure_setup)
        form.addRow(has_rate)

        def spin(label, key, minimum, maximum, default, decimals=3):
            widget = api.QDoubleSpinBox()
            widget.setDecimals(decimals)
            widget.setRange(minimum, maximum)
            widget.setValue(self.exposure_setup.get(key, default))
            form.addRow(label, widget)
            return widget

        rate = spin("Dose rate (Gy/h)", "dose_rate_gy_h", 0, 1e9, 0, 6)
        initially_on = api.QCheckBox("Irradiation on at collection start")
        initially_on.setChecked(self.exposure_setup.get("irradiating_at_start", True))
        initially_on.setToolTip("Records irradiation status. It does not control the source.")
        form.addRow(initially_on)
        has_rate.toggled.connect(rate.setEnabled)
        rate.setEnabled(has_rate.isChecked())
        diameter = spin("Window diameter (mm)", "window_diameter_mm", 0.001, 1000, 8)
        length = spin("Optical path (mm)", "path_length_mm", 0.001, 1000, 10)
        total = spin("Filled volume (mL)", "sample_volume_ml", 0, 1000, 0)
        total.setSpecialValueText("Unknown")
        volume = api.QLabel()
        form.addRow("Geometric probe volume", volume)

        def update_volume():
            volume.setText(f"{api.optical_volume_ml(diameter.value(), length.value()):.3f} mL")

        diameter.valueChanged.connect(update_volume)
        length.valueChanged.connect(update_volume)
        update_volume()
        buttons = api.QDialogButtonBox(api.QDialogButtonBox.Ok | api.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec_() == api.QDialog.Accepted:
            self.exposure_setup = dict(window_diameter_mm=diameter.value(), path_length_mm=length.value(),
                                       irradiating_at_start=initially_on.isChecked())
            if has_rate.isChecked():
                self.exposure_setup["dose_rate_gy_h"] = rate.value()
            if total.value() > 0:
                self.exposure_setup["sample_volume_ml"] = total.value()
            self.update_exposure_label()

    def update_exposure_label(self):
        if self.collection_run is not None:
            rate, irradiating = self.exposure_state
            optical, filled = self.run_volumes
            labels = [f"Irradiation marked {'on' if irradiating else 'off'}"]
            if api.np.isfinite(rate):
                labels.append(f"{rate:g} Gy/h")
        else:
            config = self.exposure_setup
            optical = api.optical_volume_ml(config["window_diameter_mm"], config["path_length_mm"])
            filled = config.get("sample_volume_ml", api.np.nan)
            labels = ["Next run"]
        if api.np.isfinite(optical):
            labels.append(f"Probe volume {optical:.3f} mL")
        if api.np.isfinite(filled):
            labels.append(f"Filled {filled:g} mL")
        self.exposure_label.setText(" | ".join(labels))

    def toggle_irradiation_marker(self):
        if self.collection_run is None or self.analysis_worker is not None:
            return
        try:
            run = self.ensure_standard_run()
            rate, enabled = run.irradiation_state()
            run.mark_irradiation(not enabled, api.time.time())
            self.exposure_state = (rate, not enabled)
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            api.QMessageBox.warning(self, "Irradiation marker", str(exc))
            return
        self.update_analysis_buttons()

    def standard_run(self, run):
        if run.schema_version() == api.SCHEMA_VERSION:
            return run
        path = run.path.with_name(f"{run.path.stem}_v2.h5")
        if path.exists():
            path = self.suggest_new_collection_file_path(path)
        return run.upgrade(path)

    def ensure_standard_run(self):
        run = self.standard_run(self.collection_run)
        if run.path != self.collection_run.path:
            self.collection_run = run
            self.set_open_collection_path(run.path)
        return run

    def start_run_analysis(self, operation, title):
        if not self.can_analyze_run():
            return
        if self.continuous_mode:
            self.stop_live_preview()
        try:
            run = self.ensure_standard_run()
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            api.QMessageBox.critical(self, title, str(api.exc))
            return
        self.analysis_worker = api.RunAnalysisThread(lambda: operation(run))
        self.analysis_worker.finished.connect(self.on_run_analysis_finished)
        self.statusBar().showMessage(f"{title} in progress…")
        self.update_analysis_buttons()
        self.analysis_worker.start()

    def recalculate_blank_od(self):
        self.start_run_analysis(lambda run: run.recalculate(), "OD recalculation")

    def run_mcr(self):
        if not self.can_analyze_run():
            return
        options = api.ask_mcr_options(self, self.mcr_options)
        if options is not None:
            self.mcr_options = options
            self.start_run_analysis(lambda run: api.read_mcr(run, api.fit_mcr(run, **options)), "MCR-ALS")

    def can_analyze_run(self):
        return (self.collection_run is not None and not self.data_collection_active
                and self.current_measurement_role is None
                and self.analysis_worker is None)

    def on_run_analysis_finished(self):
        worker = self.analysis_worker
        self.analysis_worker = None
        self.update_analysis_buttons()
        if self.closing_requested:
            api.QTimer.singleShot(0, self.close)
            return
        if worker.error:
            api.QMessageBox.warning(self, "Run analysis", worker.error)
        elif isinstance(worker.result, dict):
            self.show_mcr_result(worker.result)
        else:
            self.render_od_heatmap()
            self.statusBar().showMessage(f"OD recalculation saved: {worker.result}")

    def show_mcr(self):
        result = self.load_latest_mcr()
        if (result is None or result["stale"]) and self.can_analyze_run():
            if result is not None:
                self.mcr_options = dict(components=len(result["spectra"]), signed_spectra=result["signed_spectra"],
                                        signed_amplitudes=result["signed_amplitudes"])
            self.run_mcr()
        elif result is not None:
            self.show_mcr_result(result)
        else:
            self.statusBar().showMessage("Pause or stop collection to fit MCR-ALS.")

    def load_latest_mcr(self):
        if self.collection_run is None or self.analysis_worker is not None:
            return None
        try:
            if self.collection_run.schema_version() == api.SCHEMA_VERSION:
                return api.read_mcr(self.collection_run)
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            self.logger.warning("MCR result could not be read: %s", api.exc)
        return None

    def show_latest_mcr(self):
        result = self.load_latest_mcr()
        if result is None:
            self.statusBar().showMessage("No MCR-ALS fit has been saved for this run.")
        else:
            self.show_mcr_result(result)

    def show_mcr_result(self, result):
        if api.show_mcr_dialog(self, result, self.can_analyze_run()):
            self.mcr_options = dict(components=len(result["spectra"]), signed_spectra=result["signed_spectra"],
                                    signed_amplitudes=result["signed_amplitudes"])
            self.run_mcr()

    return {
        "may_open_collection": may_open_collection,
        "load_collection_hdf5": load_collection_hdf5,
        "load_collection_hdf5_file": load_collection_hdf5_file,
        "set_open_collection_path": set_open_collection_path,
        "edit_exposure_setup": edit_exposure_setup,
        "update_exposure_label": update_exposure_label,
        "toggle_irradiation_marker": toggle_irradiation_marker,
        "standard_run": standard_run,
        "ensure_standard_run": ensure_standard_run,
        "start_run_analysis": start_run_analysis,
        "recalculate_blank_od": recalculate_blank_od,
        "run_mcr": run_mcr,
        "can_analyze_run": can_analyze_run,
        "on_run_analysis_finished": on_run_analysis_finished,
        "show_mcr": show_mcr,
        "load_latest_mcr": load_latest_mcr,
        "show_latest_mcr": show_latest_mcr,
        "show_mcr_result": show_mcr_result,
    }
