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
        self.calibration_blocks = {role: blocks[role] for role in ("reference", "background")}
        self.last_sample_pair = None
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
            self.fail_run_write(api.exc)
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
                self.statusBar().showMessage("Collection paused. Add Blank or Resume DC.")
        elif self.collection_paused:
            if self.blank_schedule is not None or not self.validate_collection_rate(show_warning=True):
                return
            if self.log_run_event("resume"):
                self.set_collection_state(active=True, paused=False)
                self.collect_data_point()

    def measure_initial_blank(self):
        if self.data_collection_active or self.collection_paused or self.current_measurement_role is not None:
            return
        self.start_blank_measurement("initial_blank")

    def schedule_blank(self):
        if self.collection_run is None or self.analysis_worker is not None:
            return
        if self.blank_due:
            self.start_blank_measurement("blank")
            return
        if self.blank_schedule is not None:
            return

        description = (
            "Minutes until blank is due. Pause the series and insert the blank before clicking Capture Blank."
            if self.data_collection_active else
            "Insert the blank before confirming. Capture will start after the delay while DC is stopped or paused."
        )
        delay, accepted = api.QInputDialog.getDouble(self, "Add Blank", description, 0, 0, 1440, 2)
        if not accepted:
            return
        try:
            self.ensure_standard_run()
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            api.QMessageBox.critical(self, "Upgrade run", str(api.exc))
            return
        requested = api.time.time()
        schedule = {
            "requested_utc_s": requested,
            "due_utc_s": requested + delay * 60,
            "delay_minutes": delay,
            "auto_capture": not self.data_collection_active,
        }
        if not self.log_run_event("blank_scheduled", **schedule):
            return
        self.blank_schedule = schedule
        self.blank_due = False
        due = api.datetime.fromtimestamp(schedule["due_utc_s"])
        self.blank_status.setText(f"Blank due at {due:%H:%M:%S} ({delay:g} min)")
        self.blank_timer.start(round(delay * 60_000))
        self.update_analysis_buttons()

    def on_blank_due(self):
        if self.blank_schedule is None:
            return
        self.blank_due = True
        if not self.log_run_event("blank_due", due_utc_s=self.blank_schedule["due_utc_s"]):
            return
        if (self.blank_schedule["auto_capture"] and not self.data_collection_active
                and self.current_measurement_role is None):
            self.start_blank_measurement("blank")
        else:
            self.blank_status.setText("Blank due. Pause or stop DC, insert blank, then click Capture Blank.")
            self.update_analysis_buttons()

    def cancel_blank(self):
        if self.blank_schedule is None or self.current_measurement_role == "blank":
            return
        self.blank_timer.stop()
        self.log_run_event("blank_cancelled", due_utc_s=self.blank_schedule["due_utc_s"])
        self.blank_schedule = None
        self.blank_due = False
        self.blank_status.clear()
        self.update_analysis_buttons()

    def start_blank_measurement(self, role):
        if self.data_collection_active or self.current_measurement_role is not None:
            return
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            self.blank_status.setText("Connect both spectrometers to capture blank.")
            self.update_analysis_buttons()
            return
        if self.continuous_mode:
            self.stop_live_preview()
        if role == "blank":
            try:
                wavelengths, serials, _, _ = self.collection_run.info()
                if not self.match_run_hardware(wavelengths, serials):
                    raise ValueError("Connect the same spectrometers used in the run")
                if not self.same_detector_setup(self.current_detector_setup(), self.collection_run.detector_setup()):
                    raise ValueError("Use the same integration times and trigger modes as the run")
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                self.blank_status.setText(str(api.exc))
                self.update_analysis_buttons()
                return
        if not self.set_lamp_and_avantes():
            self.blank_status.setText("Unable to enable lamp and Avantes triggers.")
            self.update_analysis_buttons()
            return
        self.blank_status.setText("Capturing blank…")
        if not self.single_measurement(measurement_role=role):
            self.blank_status.setText("Blank capture could not start. Check the spectrometers and retry.")
            self.update_analysis_buttons()

    def save_blank(self, role, block):
        if role == "initial_blank":
            self.calibration_blocks["initial_blank"] = [block]
            self.last_sample_pair = None
            self.blank_status.setText("Initial blank captured. Insert the sample.")
            return
        try:
            calibration = self.collection_run.calibration()
            wavelengths, _, epoch, _ = self.collection_run.info()
            od = api.optical_density(*api.valid_counts(block), calibration["reference"],
                                 calibration["background"], wavelengths)
            block["metadata"]["blank_schedule"] = self.blank_schedule
            elapsed = block["metadata"]["utc_s"] - epoch
            bracketed = self.collection_run.add_blank(elapsed, [block], od)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.fail_run_write(api.exc)
            return
        self.blank_status.setText(
            f"Blank saved at {elapsed / 60:.2f} min. Bracketed OD updated." if bracketed else
            f"Blank saved at {elapsed / 60:.2f} min as first anchor."
        )
        self.blank_schedule = None
        self.blank_due = False
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
        "measure_initial_blank": measure_initial_blank,
        "schedule_blank": schedule_blank,
        "on_blank_due": on_blank_due,
        "cancel_blank": cancel_blank,
        "start_blank_measurement": start_blank_measurement,
        "save_blank": save_blank,
    }
