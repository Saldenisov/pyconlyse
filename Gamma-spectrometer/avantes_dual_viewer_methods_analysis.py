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

    def load_collection_hdf5_file(self, path, *, show_map=True):
        run = api.AvantesRun(path)
        wavelengths, serials, epoch, count = run.info()
        pending, comment = run.preparation_info()
        if pending:
            if not self.match_run_hardware(wavelengths, serials):
                raise ValueError("Connect the spectrometers used for calibration to continue this run")
            self.new_named_run()
            self.preparation_run = run
            self.exposure_setup = run.exposure_config()
            blocks = run.calibration_blocks()
            if "reference" not in blocks:
                self.exposure_setup.setdefault("reference_same_cell", True)
            self.set_open_collection_path(run.path)
            self.sample_comment_input.setText(comment)
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
        if self.match_run_hardware(wavelengths, serials):
            if show_map:
                self.apply_settings_dict(run.settings(), apply_trigger_frequency=False)
            if {"background", "reference"}.issubset(run.calibration_blocks()):
                self.restore_run_calibration(run)
                self.latest_reference_correction = run.latest_reference_drift()
            self.set_open_collection_path(run.path)
        self.reset_od_heatmap()
        if show_map:
            self.show_od_heatmap_window()

    def set_open_collection_path(self, path):
        self.collection_file_path = path
        self.exposure_state = self.collection_run.irradiation_state() if self.collection_run else (api.np.nan, False)
        self.dose_timeline_interrupted = (
            self.collection_run is not None and self.collection_run.dose_timeline_interrupted()
        )
        self.run_volumes = self.collection_run.sample_volumes() if self.collection_run else (api.np.nan, api.np.nan)
        self.collection_sample_metadata = self.collection_run.sample_metadata() if self.collection_run else {}
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
        dialog.setWindowTitle("Dose and sample geometry")
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
        volume = api.QLabel()
        form.addRow("Geometric probe volume", volume)
        geometry = api.optical_volume_ml(self.exposure_setup.get("window_diameter_mm", api.np.nan),
                                         self.exposure_setup.get("path_length_mm", api.np.nan))
        volume.setText(f"{geometry:.3f} mL" if api.np.isfinite(geometry)
                       else "Enter the sample geometry in the main window")
        buttons = api.QDialogButtonBox(api.QDialogButtonBox.Ok | api.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec_() == api.QDialog.Accepted:
            setup = dict(self.exposure_setup, irradiating_at_start=initially_on.isChecked())
            setup.pop("dose_rate_gy_h", None)
            if has_rate.isChecked():
                setup["dose_rate_gy_h"] = rate.value()
            self.apply_exposure_setup(setup)

    def apply_exposure_setup(self, setup):
        if self.preparation_run is not None:
            try:
                self.preparation_run.set_prepared_exposure(setup)
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                self.update_exposure_label()
                api.QMessageBox.warning(self, "Sample metadata", str(exc))
                return
        self.exposure_setup = setup
        self.update_exposure_label()

    def set_sample_geometry(self):
        if self.collection_run is not None:
            return
        setup = dict(self.exposure_setup)
        before_reference = "reference" not in self.calibration_blocks
        values = {"sample_volume_ml": self.measured_volume_spin.value()}
        if before_reference:
            values["window_diameter_mm"] = self.aperture_diameter_spin.value()
        if before_reference or not setup.get("reference_same_cell", True):
            values["path_length_mm"] = self.sample_path_spin.value()
            values["cell_type"] = self.cell_type_combo.currentText() if self.cell_type_combo.currentIndex() else ""
        for key, value in values.items():
            if value:
                setup[key] = value
            else:
                setup.pop(key, None)
        self.apply_exposure_setup(setup)

    def set_reference_geometry(self):
        if self.collection_run is not None or "reference" in self.calibration_blocks:
            return
        setup = dict(self.exposure_setup, reference_same_cell=self.reference_same_cell_check.isChecked())
        length = self.reference_path_spin.value()
        if length:
            setup["reference_path_length_mm"] = length
        else:
            setup.pop("reference_path_length_mm", None)
        setup["reference_cell_type"] = (
            self.reference_cell_type_combo.currentText() if self.reference_cell_type_combo.currentIndex() else ""
        )
        self.apply_exposure_setup(setup)

    def check_sample_metadata(self, require_reference=False):
        archived = self.collection_run is not None
        setup = self.collection_sample_metadata if archived else self.exposure_setup
        missing = api.missing_sample_fields(setup)
        if require_reference:
            missing += api.missing_reference_fields(setup)
        if not missing:
            return True
        message = "Complete the required sample fields before measuring.\n\n" + "\n".join(missing)
        if archived:
            message += "\n\nUse New Experiment to start a series with complete sample metadata."
        api.QMessageBox.information(self, "Sample metadata", message)
        return False

    def set_probe_volume(self, value):
        if self.collection_run is not None:
            return
        setup = dict(self.exposure_setup)
        if value:
            setup["probe_volume_ml"] = value
        else:
            setup.pop("probe_volume_ml", None)
        self.apply_exposure_setup(setup)

    def update_exposure_label(self):
        if self.collection_run is not None:
            rate, irradiating = self.exposure_state
            optical, _ = self.run_volumes
            probe_value = optical if api.np.isfinite(optical) else 0
            probe_default = "Unknown"
            metadata = self.collection_sample_metadata
            labels = [
                "Click again after switching irradiation off."
                if irradiating else "Click after switching irradiation on."
            ]
            if self.dose_timeline_interrupted:
                labels.append("Dose unknown after interruption")
            if api.np.isfinite(rate):
                labels.append(f"{rate:g} Gy/h")
        else:
            config = self.exposure_setup
            probe_value = config.get("probe_volume_ml", 0)
            geometry = api.optical_volume_ml(config.get("window_diameter_mm", api.np.nan),
                                             config.get("path_length_mm", api.np.nan))
            probe_default = f"Auto ({geometry:.3f} mL)" if api.np.isfinite(geometry) else "Auto"
            metadata = config
            labels = []
        spin = self.probe_volume_spin
        blocked = spin.blockSignals(True)
        spin.setSpecialValueText(probe_default)
        spin.setValue(probe_value)
        spin.blockSignals(blocked)
        for widget, key in ((self.measured_volume_spin, "sample_volume_ml"),
                            (self.aperture_diameter_spin, "window_diameter_mm"),
                            (self.sample_path_spin, "path_length_mm"),
                            (self.reference_path_spin, "reference_path_length_mm")):
            value = metadata.get(key, 0)
            blocked = widget.blockSignals(True)
            widget.setValue(value if api.np.isfinite(value) else 0)
            widget.blockSignals(blocked)
        for cell, key in ((self.cell_type_combo, "cell_type"),
                          (self.reference_cell_type_combo, "reference_cell_type")):
            blocked = cell.blockSignals(True)
            cell.setCurrentIndex(max(0, cell.findText(metadata.get(key, ""))))
            cell.blockSignals(blocked)
        check = self.reference_same_cell_check
        blocked = check.blockSignals(True)
        check.setChecked(metadata.get("reference_same_cell", True))
        check.blockSignals(blocked)
        self.reference_cell_group.setVisible("reference_same_cell" in metadata)
        self.reference_cell_fields.setVisible(not check.isChecked())
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
            self.update_analysis_buttons()
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
            api.QMessageBox.critical(self, title, str(exc))
            return
        self.analysis_worker = api.RunAnalysisThread(lambda: operation(run))
        self.analysis_worker.finished.connect(self.on_run_analysis_finished)
        self.statusBar().showMessage(f"{title} in progress…")
        self.update_analysis_buttons()
        self.analysis_worker.start()

    def recalculate_blank_od(self):
        self.start_run_analysis(lambda run: run.recalculate(), "OD recalculation")

    def inspect_calibration_history(self):
        if self.collection_run is not None and not self.can_analyze_run():
            return
        if self.collection_run is None and not self.may_open_collection():
            return
        try:
            run = self.ensure_standard_run() if self.collection_run is not None else self.preparation_run
            if run is None:
                return
            options = run.calibration_options()
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            api.QMessageBox.warning(self, "Calibration from raw data", str(exc))
            return

        dialog = api.QDialog(self)
        dialog.setWindowTitle("Calibration from raw data")
        dialog.resize(780, 620)
        layout = api.QVBoxLayout(dialog)
        controls = api.QFormLayout()
        layout.addLayout(controls)
        inputs = {}
        preview_role = api.QComboBox()
        zero = api.QComboBox()
        for role, choices in options.items():
            if not choices:
                continue
            select = api.QComboBox()
            for label, capture_id in choices:
                select.addItem(label, capture_id)
            controls.addRow(role.title(), select)
            inputs[role] = select
            preview_role.addItem(role.title(), role)
        for role in ("reference", "empty"):
            if role in inputs:
                zero.addItem(role.title(), role)
        controls.addRow("Preview capture", preview_role)
        controls.addRow("OD zero", zero)
        preview_role.setCurrentIndex(max(0, preview_role.findData("empty")))

        counts_plot = api.pg.PlotWidget(title="Archived detector counts")
        counts_plot.setLabel("bottom", "Wavelength", units="nm")
        counts_plot.getAxis("bottom").enableAutoSIPrefix(False)
        counts_plot.addLegend()
        counts_1 = counts_plot.plot(pen="c", name="Channel 1")
        counts_2 = counts_plot.plot(pen="y", name="Channel 2")
        layout.addWidget(counts_plot, 1)
        od_plot = api.pg.PlotWidget(title="Optical density relative to the selected zero")
        od_plot.setLabel("bottom", "Wavelength", units="nm")
        od_plot.getAxis("bottom").enableAutoSIPrefix(False)
        od_curve = od_plot.plot(pen="w")
        layout.addWidget(od_plot, 1)
        status = api.QLabel()
        status.setWordWrap(True)
        layout.addWidget(status)

        def selected_inputs():
            return {role: field.currentData() for role, field in inputs.items()}

        def show_preview():
            counts_1.setData([], [])
            counts_2.setData([], [])
            od_curve.setData([], [])
            if preview_role.currentData() is None:
                status.setText("No completed calibration captures")
                return
            try:
                wavelengths, counts, od = run.preview_calibration(
                    preview_role.currentData(), selected_inputs(), zero.currentData(),
                )
                counts_1.setData(wavelengths[0], counts[0])
                counts_2.setData(wavelengths[1], counts[1])
                if od is not None:
                    od_curve.setData(wavelengths[0], od)
                status.clear()
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                status.setText(str(exc))

        for field in (*inputs.values(), preview_role, zero):
            field.currentIndexChanged.connect(show_preview)
        buttons = api.QDialogButtonBox(api.QDialogButtonBox.Close)
        recalculate = buttons.addButton("Recalculate OD", api.QDialogButtonBox.AcceptRole)
        recalculate.setEnabled(self.can_analyze_run() and int(self.collection_point_index) > 0
                               and {"background", "reference"}.issubset(inputs))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        show_preview()
        if dialog.exec_() == api.QDialog.Accepted:
            selections = selected_inputs()
            baseline = zero.currentData()
            self.start_run_analysis(lambda run: run.reprocess_raw(selections, baseline), "OD from raw counts")

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
                and self.calibration_capture is None
                and self.analysis_worker is None)

    def on_run_analysis_finished(self):
        worker = self.analysis_worker
        self.analysis_worker = None
        worker.deleteLater()
        self.update_analysis_buttons()
        if self.closing_requested:
            api.QTimer.singleShot(0, self.close)
            return
        if worker.error:
            self.statusBar().showMessage("Run analysis failed.")
            api.QMessageBox.warning(self, "Run analysis", worker.error)
        elif isinstance(worker.result, dict):
            self.statusBar().showMessage("MCR-ALS fit saved.")
            self.show_mcr_result(worker.result)
        else:
            if isinstance(worker.result, str) and worker.result.endswith("_raw_recalculation"):
                self.show_od_heatmap_window()
                source = self.od_heatmap_window.od_source
                source.setCurrentIndex(source.findData("od_reprocessed"))
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
            self.logger.warning("MCR result could not be read: %s", exc)
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
        "apply_exposure_setup": apply_exposure_setup,
        "set_sample_geometry": set_sample_geometry,
        "set_reference_geometry": set_reference_geometry,
        "check_sample_metadata": check_sample_metadata,
        "set_probe_volume": set_probe_volume,
        "update_exposure_label": update_exposure_label,
        "toggle_irradiation_marker": toggle_irradiation_marker,
        "standard_run": standard_run,
        "ensure_standard_run": ensure_standard_run,
        "start_run_analysis": start_run_analysis,
        "recalculate_blank_od": recalculate_blank_od,
        "inspect_calibration_history": inspect_calibration_history,
        "run_mcr": run_mcr,
        "can_analyze_run": can_analyze_run,
        "on_run_analysis_finished": on_run_analysis_finished,
        "show_mcr": show_mcr,
        "load_latest_mcr": load_latest_mcr,
        "show_latest_mcr": show_latest_mcr,
        "show_mcr_result": show_mcr_result,
    }
