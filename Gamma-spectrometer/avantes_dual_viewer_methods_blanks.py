"""Implementation for blanks and related operations."""


def _bind_avantes_dual_viewer_methods_blanks(api):
    """Bind implementation to the owning module and its runtime state."""

    def current_hardware(self):
        widgets = self.spec1_widget, self.spec2_widget
        return (
            tuple(api.np.asarray(widget.wavelengths, dtype=float) for widget in widgets),
            [widget.serial_input.text().strip() for widget in widgets],
        )

    def match_run_hardware(self, wavelengths, serials):
        current_wavelengths, current_serials = self.current_hardware()
        return current_serials == serials and all(
            api.np.array_equal(current, saved) for current, saved in zip(current_wavelengths, wavelengths)
        )

    def calibration_matches_detector_setup(self):
        current = self.current_detector_setup()
        return all(self.same_detector_setup(current, block["metadata"]["channels"])
                   for blocks in self.calibration_blocks.values() for block in blocks)

    def current_detector_setup(self):
        return [self.get_spectrometer_settings(widget) for widget in (self.spec1_widget, self.spec2_widget)]

    @staticmethod
    def same_detector_setup(current, saved):
        keys = ("serial", "integration_ms", "trigger_mode")
        return all(all(a[key] == b[key] for key in keys) for a, b in zip(current, saved))

    def restore_run_calibration(self, run):
        blocks = run.calibration_blocks()
        dark, reference = api.mean_counts(blocks["background"]), api.mean_counts(blocks["reference"])
        self.background_ch1, self.background_ch2 = dark
        self.reference_ch1, self.reference_ch2 = reference
        self.reference_wavelengths = self.spec1_widget.wavelengths
        self.has_background = self.has_reference = True
        self.clear_zero_baseline()
        if "sample_t0" in blocks:
            self.zero_baseline_od = api.optical_density(*api.mean_counts(blocks["sample_t0"]), reference, dark,
                                                    self.current_hardware()[0])
            self.zero_baseline_wavelengths = self.reference_wavelengths
        self.calibration_blocks = blocks
        self.ref_curve1.setData(self.spec1_widget.wavelengths, reference[0])
        self.ref_curve2.setData(self.spec2_widget.wavelengths, reference[1])
        self.bg_curve1.setData(self.spec1_widget.wavelengths, dark[0])
        self.bg_curve2.setData(self.spec2_widget.wavelengths, dark[1])

    def set_collection_state(self, *, active, paused):
        self.data_collection_active = active
        self.collection_paused = paused
        self.collection_next_due_time = None
        if active:
            self.collection_countdown_timer.start()
        else:
            self.collection_timer.stop()
            self.lamp_warmup_timer.stop()
            self.collection_countdown_timer.stop()
        self.start_collection_btn.setText("Stop DC" if active or paused else "Start DC")
        self.pause_collection_btn.setText("Resume DC" if paused else "Pause DC")
        self.update_collection_countdown_label()
        self.update_analysis_buttons()

    def log_run_event(self, event, **details):
        try:
            self.collection_run.append_event(event, api.time.time(), **details)
        except (OSError, ValueError, RuntimeError) as exc:
            self.fail_run_write(exc)
            return False
        return True

    def fail_run_write(self, exc):
        self.logger.error("HDF5 write failed: %s", exc)
        self.set_collection_state(active=False, paused=False)
        api.QMessageBox.critical(self, "HDF5 write failed", str(exc))

    def toggle_collection_pause(self):
        if self.current_measurement_role is not None or self.analysis_worker is not None:
            return
        if self.data_collection_active:
            self.set_collection_state(active=False, paused=True)
            if self.log_run_event("pause"):
                self.statusBar().showMessage("Collection paused. Add Reference or Resume DC.")
        elif self.collection_paused:
            if not self.validate_collection_rate(show_warning=True):
                return
            if self.log_run_event("resume"):
                self.set_collection_state(active=True, paused=False)
                self.collect_data_point()

    def add_reference(self):
        if not self.may_open_collection() and not self.collection_paused:
            return
        if (self.collection_run is None or self.data_collection_active or self.current_measurement_role is not None
                or self.analysis_worker is not None):
            return
        if not self.check_sample_metadata(require_reference=True):
            return
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            self.blank_status.setText("Connect both spectrometers to capture a reference.")
            return
        try:
            self.ensure_standard_run()
            wavelengths, serials, _, _ = self.collection_run.info()
            if not self.match_run_hardware(wavelengths, serials):
                raise ValueError("Connect the same spectrometers used in the run")
            if not self.same_detector_setup(self.current_detector_setup(), self.collection_run.detector_setup()):
                raise ValueError("Use the same integration times and trigger modes as the run")
            self.blank_status.setText("Capturing reference…")
            self.start_spectral_capture(self.collection_run, "blank")
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.blank_status.setText(str(exc))

    def save_blank(self, blocks):
        try:
            calibration = self.collection_run.calibration()
            wavelengths, _, epoch, _ = self.collection_run.info()
            od = api.optical_density(*api.mean_counts(blocks), calibration["reference"],
                                     calibration["background"], wavelengths)
            elapsed = api.np.mean([block["metadata"]["utc_s"] for block in blocks]) - epoch
            bracketed = self.collection_run.add_blank(elapsed, blocks, od)
            self.latest_reference_correction = self.collection_run.latest_reference_drift()
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.blank_status.setText(f"Raw reference saved. Correction failed: {exc}")
            return
        self.blank_status.setText(
            f"Reference saved at {elapsed:.1f} s. OD correction updated." if bracketed else
            f"Reference saved at {elapsed:.1f} s as first drift anchor."
        )
        self.plot_od.setTitle("Reference OD vs Initial Reference")
        self.curve_od.setData(wavelengths[0], od)
        self.statusBar().showMessage(f"Reference capture complete ({len(blocks)} blocks)")
        self.render_od_heatmap()

    return {
        "current_hardware": current_hardware,
        "match_run_hardware": match_run_hardware,
        "calibration_matches_detector_setup": calibration_matches_detector_setup,
        "current_detector_setup": current_detector_setup,
        "same_detector_setup": same_detector_setup,
        "restore_run_calibration": restore_run_calibration,
        "set_collection_state": set_collection_state,
        "log_run_event": log_run_event,
        "fail_run_write": fail_run_write,
        "toggle_collection_pause": toggle_collection_pause,
        "add_reference": add_reference,
        "save_blank": save_blank,
    }
