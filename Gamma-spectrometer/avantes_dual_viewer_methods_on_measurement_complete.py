"""Implementation for on_measurement_complete and related operations."""


def _bind_avantes_dual_viewer_methods_on_measurement_complete(api):
    """Bind implementation to the owning module and its runtime state."""

    def on_measurement_complete(self, results):
        role = self.current_measurement_role
        metadata = dict(self.measurement_metadata, completed_utc_s=api.time.time())
        metadata["readout"] = {str(i): info for i, info in self.measurement_thread.diagnostics.items()}
        widgets = self.spec1_widget, self.spec2_widget
        spectra = []
        for idx, (widget, curve) in enumerate(zip(widgets, (self.curve1, self.curve2))):
            success, data = results.get(idx, (False, None))
            if success and data is not None and widget.wavelengths is not None and len(data) == len(widget.wavelengths):
                spectrum = api.np.array(data, dtype=float, copy=True)
                curve.setData(widget.wavelengths, spectrum)
                widget.update_statistics(spectrum)
            else:
                spectrum = None
            spectra.append(spectrum)

        ch1, ch2 = spectra
        paired = ch1 is not None and ch2 is not None
        metadata["channel_ok"] = [ch1 is not None, ch2 is not None]
        block = dict(ch1=ch1, ch2=ch2, metadata=metadata)
        self._measurement_count += 1

        if role in {"reference", "empty", "background", "blank"}:
            capture = self.calibration_capture
            if capture is None:
                return
            try:
                count = capture["run"].append_capture_block(capture["name"], block)
                if capture["aborted"] or not paired:
                    self.calibration_capture = None
                    if not paired:
                        self.statusBar().showMessage("Incomplete readout retained in HDF5. Retry the capture.")
                elif count == capture["target"]:
                    blocks = capture["run"].finish_capture(capture["name"])
                    self.calibration_capture = None
                    self.complete_spectral_capture(role, blocks)
                else:
                    self.pending_ref_bg_role = role
                    self.statusBar().showMessage(f"{role.title()} block {count}/{capture['target']} saved")
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                self.calibration_capture = None
                api.QMessageBox.critical(self, "Save spectral capture", str(exc))
            if self.calibration_capture is None:
                self.stop_measure_btn.setEnabled(False)
            return

        elapsed = None
        if role == "collection":
            elapsed = metadata["utc_s"] - self.collection_start_time
        od_raw = self.calculate_optical_density(*api.valid_counts(block),
                                               apply_zero_baseline=False) if paired else None
        od = self.apply_kinetic_zero(od_raw)
        if od is not None:
            plotted = od
            if role == "collection" and self.latest_reference_correction is not None:
                plotted = od - self.latest_reference_correction
            self.curve_od.setData(widgets[0].wavelengths, plotted)
            self.plot_od.setTitle(
                "Optical Density (latest reference correction)"
                if plotted is not od else "Optical Density (OD) Spectrum"
            )
            if self.wavelength_tracker_window:
                self.wavelength_tracker_window.update_od_value(plotted, widgets[0].wavelengths)

        if role == "collection":
            try:
                self.collection_point_index = self.collection_run.append(
                    elapsed, metadata["utc_s"], ch1, ch2, od_raw, od, metadata
                )
            except (OSError, ValueError, RuntimeError) as exc:
                self.fail_run_write(exc)
                return
            if self.od_heatmap_window is not None and not self.map_refresh_timer.isActive():
                self.map_refresh_timer.start()
            suffix = "" if paired else " (incomplete readout)"
            self.statusBar().showMessage(f"Saved point {self.collection_point_index}{suffix}")
            if not self.closing_requested:
                self.schedule_next_collection_point()
        elif self.continuous_mode:
            self.statusBar().showMessage(f"{self._measurement_count} preview measurements")
        else:
            self.statusBar().showMessage("Measurement complete")

    def on_measurement_error(self, error_msg):
        self.logger.error("Measurement error: %s", error_msg)
        role = self.current_measurement_role
        if role in {"collection", "blank", "reference", "empty", "background"}:
            self.measurement_metadata["error"] = error_msg
            self.on_measurement_complete({})
        elif "INVALID_MEAS_DATA" not in error_msg and self.continuous_mode:
            self.stop_live_preview()
            self.statusBar().showMessage(f"Error: {error_msg}")
        else:
            self.statusBar().showMessage(f"Error: {error_msg}")

    def on_measurement_finished(self):
        pending_role = self.pending_ref_bg_role
        self.pending_ref_bg_role = None
        self.current_measurement_role = None
        if self.closing_requested:
            self.calibration_capture = None
            api.QTimer.singleShot(0, self.close)
            return
        if pending_role is not None and not self.single_measurement(measurement_role=pending_role):
            self.stop_measurement()
            self.calibration_capture = None
        self.update_collection_countdown_label()
        self.update_analysis_buttons()

    def export_data(self):
        """Export current data to CSV files."""
        data1 = self.spec1_widget.last_data
        data2 = self.spec2_widget.last_data
        wl1 = self.spec1_widget.wavelengths
        wl2 = self.spec2_widget.wavelengths

        if data1 is None and data2 is None:
            api.QMessageBox.warning(self, "No Data", "No measurement data to export")
            return

        try:
            base_filename = str(self.get_export_base_path())

            # Export spec 1
            if data1 is not None and wl1 is not None:
                filename1 = f"{base_filename}_spec1.csv"
                api.np.savetxt(
                    filename1,
                    api.np.column_stack((wl1, data1)),
                    delimiter=',',
                    header='Wavelength(nm),Intensity(counts)',
                    comments=''
                )

            # Export spec 2
            if data2 is not None and wl2 is not None:
                filename2 = f"{base_filename}_spec2.csv"
                api.np.savetxt(
                    filename2,
                    api.np.column_stack((wl2, data2)),
                    delimiter=',',
                    header='Wavelength(nm),Intensity(counts)',
                    comments=''
                )

            # Calculate and export OD if both datasets available
            if data1 is not None and data2 is not None and wl1 is not None:
                od = self.calculate_optical_density(data1, data2)
                if od is not None:
                    filename_od = f"{base_filename}_OD.csv"
                    api.np.savetxt(
                        filename_od,
                        api.np.column_stack((wl1, od)),
                        delimiter=',',
                        header='Wavelength(nm),OpticalDensity(AU)',
                        comments=''
                    )

            self.logger.info(f"EXPORT: Data saved to {base_filename}_*.csv (spec1, spec2, OD)")

            api.QMessageBox.information(self, "Export Complete", f"Data exported to {base_filename}_*.csv")

        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            api.QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")

    def calculate_optical_density(self, ch1_current, ch2_current, apply_zero_baseline=True):
        if not self.has_reference or not self.has_background:
            return None
        wavelengths, _ = self.current_hardware()
        od = api.optical_density(
            ch1_current, ch2_current,
            (self.reference_ch1, self.reference_ch2),
            (self.background_ch1, self.background_ch2), wavelengths,
        )
        return self.apply_kinetic_zero(od) if apply_zero_baseline else od

    def get_demo_species_od(self, wavelengths: api.np.ndarray, elapsed_time: float) -> api.np.ndarray:
        """Return a synthetic growing UV-visible species OD spectrum."""
        if wavelengths is None:
            return 0.0

        duration_s = max(1.0, self.demo_kinetics_duration_s)
        progress = api.np.clip(float(elapsed_time) / duration_s, 0.0, 1.0)
        growth = 1.0 - api.np.exp(-4.2 * progress)
        slow_growth = progress * progress * (3.0 - 2.0 * progress)
        wl = api.np.asarray(wavelengths, dtype=float)

        # Broad product bands spanning UV to visible, with a later visible shoulder.
        species_shape = (
            0.32 * api.np.exp(-0.5 * ((wl - 285.0) / 34.0) ** 2)
            + 0.46 * api.np.exp(-0.5 * ((wl - 365.0) / 58.0) ** 2)
            + 0.58 * api.np.exp(-0.5 * ((wl - 525.0) / 120.0) ** 2)
            + 0.25 * api.np.exp(-0.5 * ((wl - 705.0) / 170.0) ** 2)
        )
        late_visible = 0.24 * slow_growth * api.np.exp(-0.5 * ((wl - 610.0) / 95.0) ** 2)
        baseline = 0.025 * growth * api.np.exp(-0.5 * ((wl - 480.0) / 360.0) ** 2)
        species_shape = species_shape / max(float(api.np.max(species_shape)), 1e-12)
        return self.demo_kinetics_max_od * growth * species_shape + late_visible + baseline

    def clear_plots(self):
        """Clear all plots and reset reference and background."""
        self.curve1.setData([], [])
        self.curve2.setData([], [])
        self.curve_od.setData([], [])
        self.plot_od.setTitle("Optical Density (OD) Spectrum")
        self.ref_curve1.setData([], [])
        self.ref_curve2.setData([], [])
        self.bg_curve1.setData([], [])
        self.bg_curve2.setData([], [])
        self.reset_od_heatmap()

        self.spec1_widget.last_data = None
        self.spec2_widget.last_data = None
        self.spec1_widget.mean_label.setText("---")
        self.spec1_widget.max_label.setText("---")
        self.spec2_widget.mean_label.setText("---")
        self.spec2_widget.max_label.setText("---")

        # Clear reference and background
        self.reference_ch1 = None
        self.reference_ch2 = None
        self.background_ch1 = None
        self.background_ch2 = None
        self.reference_wavelengths = None
        self.clear_zero_baseline()
        self.has_reference = False
        self.has_background = False
        self.calibration_blocks.clear()
        self.update_analysis_buttons()

        self.statusBar().showMessage("Plots cleared")

    def setup_logging(self):
        """Setup logging to file and console.

        Both handlers are configured to use UTF-8 so Unicode characters
        (e.g. the Greek letter lambda used in wavelength messages) can be
        emitted without UnicodeEncodeError on Windows (default cp1252).
        """
        # Create logs directory if it doesn't exist
        log_dir = api.Path(api.__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create log filename with timestamp
        timestamp = api.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"avantes_dual_{timestamp}.log"

        # File handler with UTF-8 encoding
        file_handler = api.logging.FileHandler(log_file, encoding="utf-8")

        # Stream handler: try to reconfigure stdout to UTF-8 (Python 3.7+);
        # fall back to replacing un-encodable characters so logging never crashes.
        try:
            api.sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            stream_handler = api.logging.StreamHandler(api.sys.stdout)
        except Exception:
            import io
            utf8_stream = io.TextIOWrapper(
                api.sys.stdout.buffer if hasattr(api.sys.stdout, "buffer") else api.sys.stdout,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )
            stream_handler = api.logging.StreamHandler(utf8_stream)

        formatter = api.logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        # Configure root logger (force=True clears any pre-existing handlers
        # so we don't end up with duplicate non-UTF-8 handlers).
        api.logging.basicConfig(
            level=api.logging.INFO,
            handlers=[file_handler, stream_handler],
            force=True,
        )

        self.logger = api.logging.getLogger(api.__name__)
        self.logger.info("="*60)
        self.logger.info("INIT: Avantes Dual Spectrometer Viewer")
        self.logger.info(f"INIT: Log file = {log_file}")
        self.logger.info("INIT: Ready")
        self.logger.info("="*60)

    def auto_connect_spectrometers(self):
        """Automatically connect to both spectrometers on startup."""
        self.logger.info("="*60)
        self.logger.info("AUTO-CONNECT: Starting sequence...")

        # Connect spectrometer 1
        self.spec1_widget.connect_spectrometer()

        # Small delay between connections
        api.QTimer.singleShot(1000, self.auto_connect_spec2)

    def auto_connect_spec2(self):
        """Connect to spectrometer 2."""
        self.spec2_widget.connect_spectrometer()

        if self.spec1_widget.spec and self.spec2_widget.spec:
            self.logger.info("AUTO-CONNECT: Both spectrometers connected")
            self.logger.info("="*60)

            # Keep idle after connection; measurements are user-triggered.
        else:
            self.logger.error("AUTO-CONNECT: Failed to connect both spectrometers")

    def auto_start_continuous(self):
        """Check Arduino after connection without starting measurements."""
        self.logger.info("AUTO-START: Checking Arduino")

        if self.arduino.is_connected():
            self.sync_arduino_frequency_from_controller()
            lamp_on, avantes_on = self.get_arduino_state()
            if lamp_on and avantes_on:
                self.arduino_status_label.setText("Status: Lamp + Avantes")
                self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            elif avantes_on:
                self.arduino_status_label.setText("Status: Avantes Only")
                self.arduino_status_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.arduino_status_label.setText("Status: OFF")
                self.arduino_status_label.setStyleSheet("color: gray; font-weight: bold;")
            self.logger.info("AUTO-START: Arduino reachable")
        else:
            self.logger.warning("AUTO-START: Arduino not reachable")
            self.arduino_status_label.setText("Status: Not Connected")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")

        self.statusBar().showMessage("Ready")
        self.logger.info("AUTO-START: Ready")

    def closeEvent(self, event):
        """Handle window close event."""
        self.map_refresh_timer.stop()
        self.continuous_timer.stop()
        self.collection_timer.stop()
        self.lamp_warmup_timer.stop()
        self.collection_countdown_timer.stop()
        if self.current_measurement_role is not None or self.calibration_capture is not None or self.analysis_worker is not None:
            self.closing_requested = True
            self.statusBar().showMessage("Finishing the current operation before closing…")
            event.ignore()
            return

        if self.collection_run is not None:
            try:
                if self.data_collection_active or self.collection_paused:
                    self.collection_run.append_event("stop", api.time.time(), reason="application closed")
            except (OSError, ValueError, RuntimeError) as exc:
                self.logger.error("Failed to save shutdown event: %s", exc)

        count = self._measurement_count if hasattr(self, '_measurement_count') else 0
        self.logger.info("="*60)
        self.logger.info(f"SHUTDOWN: Application closing ({count} measurements completed)")

        # Close wavelength tracker
        if self.wavelength_tracker_window:
            self.wavelength_tracker_window.close()
        if self.od_heatmap_window:
            self.od_heatmap_window.close()

        # Disconnect spectrometers
        if self.spec1_widget and self.spec1_widget.spec:
            self.spec1_widget.disconnect_spectrometer()
        if self.spec2_widget and self.spec2_widget.spec:
            self.spec2_widget.disconnect_spectrometer()

        self.logger.info("SHUTDOWN: Complete")
        self.logger.info("="*60)

        event.accept()

    return {
        "on_measurement_complete": on_measurement_complete,
        "on_measurement_error": on_measurement_error,
        "on_measurement_finished": on_measurement_finished,
        "export_data": export_data,
        "calculate_optical_density": calculate_optical_density,
        "get_demo_species_od": get_demo_species_od,
        "clear_plots": clear_plots,
        "setup_logging": setup_logging,
        "auto_connect_spectrometers": auto_connect_spectrometers,
        "auto_connect_spec2": auto_connect_spec2,
        "auto_start_continuous": auto_start_continuous,
        "closeEvent": closeEvent,
    }
