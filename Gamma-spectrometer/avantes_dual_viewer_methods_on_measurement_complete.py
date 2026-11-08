"""Implementation for on_measurement_complete and related operations."""


def _bind_avantes_dual_viewer_methods_on_measurement_complete(api):
    """Bind implementation to the owning module and its runtime state."""

    def on_measurement_complete(self, results: dict):
        """Handle completed measurement."""
        # Store data for OD calculation
        data1 = None
        data2 = None
        wavelengths1 = None

        # Update plots
        for idx, (success, data) in results.items():
            if success and data is not None:
                if idx == 0:  # Ch1
                    wavelengths1 = self.spec1_widget.wavelengths
                    if wavelengths1 is not None and len(wavelengths1) == len(data):
                        data1 = data
                        self.curve1.setData(wavelengths1, data)
                        self.spec1_widget.update_statistics(data)
                elif idx == 1:  # Ch2
                    wavelengths2 = self.spec2_widget.wavelengths
                    if wavelengths2 is not None and len(wavelengths2) == len(data):
                        data2 = data
                        self.curve2.setData(wavelengths2, data)
                        self.spec2_widget.update_statistics(data)

        measurement_role = getattr(self, "current_measurement_role", None)

        # Handle reference measurement collection
        skip_normal_status = False
        if measurement_role == "reference" and self.measuring_reference and data1 is not None and data2 is not None:
            self.reference_measurements.append({'ch1': data1, 'ch2': data2})
            skip_normal_status = True
            count = len(self.reference_measurements)
            target = max(1, int(self.reference_target_blocks))
            if count < target:
                self.statusBar().showMessage(f"Measuring reference block {count + 1}/{target}...")
                self.logger.info(f"REFERENCE: Block {count}/{target} collected")
                self.pending_ref_bg_role = "reference"
                return
            self.statusBar().showMessage("Reference measured")
            self.measure_reference_complete()
            skip_normal_status = False

        # Handle background measurement collection
        # Check the flag BEFORE appending to avoid collecting after completion
        if measurement_role == "background" and self.measuring_background:
            if data1 is not None and data2 is not None:
                self.background_measurements.append({'ch1': data1, 'ch2': data2})
                skip_normal_status = True
                count = len(self.background_measurements)
                target = max(1, int(self.background_target_blocks))
                if count < target:
                    self.statusBar().showMessage(f"Measuring background block {count + 1}/{target}...")
                    self.logger.info(f"BACKGROUND: Block {count}/{target} collected")
                    self.pending_ref_bg_role = "background"
                    return
                self.statusBar().showMessage("Background measured")
                self.measure_background_complete()
                skip_normal_status = False

        completed_collection_point = measurement_role == "collection" and data1 is not None and data2 is not None
        collection_elapsed = None
        collection_pulses = self.get_detector_average_count() if completed_collection_point else 0
        if completed_collection_point:
            if self.collection_point_index == 0 and self.collection_time_offset_s <= 0:
                collection_elapsed = 0.0
            else:
                collection_elapsed = self.collection_time_offset_s + (api.time.time() - self.collection_start_time)
            skip_normal_status = True

        # Calculate and plot Optical Density (only if both reference AND background exist)
        od_spectrum = None
        if data1 is not None and data2 is not None and wavelengths1 is not None:
            if self.has_reference and self.has_background:
                od_spectrum = self.calculate_optical_density(
                    data1,
                    data2,
                    elapsed_time=collection_elapsed if completed_collection_point else None,
                )
                if od_spectrum is not None:
                    self.curve_od.setData(wavelengths1, od_spectrum)
                    # Apply manual limits if not in auto mode
                    if not self.od_x_auto_check.isChecked():
                        self.plot_od.setXRange(self.od_x_min_spin.value(), self.od_x_max_spin.value(), padding=0)
                    if not self.od_y_auto_check.isChecked():
                        self.plot_od.setYRange(self.od_y_min_spin.value(), self.od_y_max_spin.value(), padding=0)
            else:
                # Clear OD plot if requirements not met
                self.curve_od.setData([], [])

        # Update measurement counter
        if not hasattr(self, '_measurement_count'):
            self._measurement_count = 0
        self._measurement_count += 1
        self.update_analysis_buttons()

        # Update wavelength tracker if active
        if self.wavelength_tracker_window and od_spectrum is not None:
            self.wavelength_tracker_window.update_od_value(od_spectrum, wavelengths1)

        if completed_collection_point:
            self.save_collection_point(
                collection_elapsed,
                wavelengths1,
                od_spectrum,
            )
            self.collection_data.append(
                {
                    'time': collection_elapsed,
                    'ch1': data1,
                    'ch2': data2,
                    'od': od_spectrum,
                    'pulse_average': collection_pulses,
                }
            )
            self.collection_point_index += 1
            self.update_od_heatmap(wavelengths1, od_spectrum, collection_elapsed)
            self.statusBar().showMessage(
                f"Saved point {self.collection_point_index} ({collection_pulses} pulses)"
            )
            self.update_collection_countdown_label()
            self.schedule_next_collection_point()

        # Update status (unless we're in the middle of collecting reference/background)
        if not skip_normal_status:
            if self.continuous_mode:
                status_parts = [f"{self._measurement_count} measurements"]
                if self.has_reference:
                    status_parts.append("REF: ✓")
                if self.has_background:
                    status_parts.append("BG: ✓")
                if self.has_reference and self.has_background:
                    status_parts.append("OD: Active")
                if self.data_collection_active:
                    status_parts.append("Recording")
                self.statusBar().showMessage(" | ".join(status_parts))
            else:
                self.statusBar().showMessage("Measurement complete")

    def on_measurement_error(self, error_msg: str):
        """Handle measurement error."""
        self.logger.error(f"Measurement error: {error_msg}")
        self.pending_ref_bg_role = None

        if getattr(self, "current_measurement_role", None) == "collection" and self.data_collection_active:
            self.statusBar().showMessage(f"Collection warning: {error_msg[:50]}...")
            self.schedule_next_collection_point()
            return

        # Check if it's a recoverable error (data timing issue)
        is_recoverable = "INVALID_MEAS_DATA" in error_msg

        if is_recoverable and self.continuous_mode:
            # Log but continue in live preview for timing issues.
            self.logger.warning("Recoverable error in live preview - will retry next cycle")
            self.statusBar().showMessage(f"Warning: {error_msg[:50]}...")
        else:
            # Fatal error - stop live preview.
            self.statusBar().showMessage(f"Error: {error_msg}")

            if self.continuous_mode:
                self.logger.error("Stopping live preview due to fatal error")
                self.continuous_timer.stop()
                self.continuous_mode = False
            else:
                api.QMessageBox.critical(self, "Measurement Error", error_msg)

    def on_measurement_finished(self):
        """Handle measurement thread finished."""
        pending_role = self.pending_ref_bg_role
        self.pending_ref_bg_role = None
        self.current_measurement_role = None
        if pending_role == "reference" and self.measuring_reference:
            self.single_measurement(measurement_role="reference")
            return
        if pending_role == "background" and self.measuring_background:
            self.single_measurement(measurement_role="background")
            return
        if self.data_collection_active:
            self.update_collection_countdown_label()

    def save_collection_point(
        self,
        elapsed_time: float,
        wavelengths: api.np.ndarray,
        od_spectrum: api.Optional[api.np.ndarray],
    ):
        """Append one OD spectrum row to tab-delimited DAT file."""
        if self.collection_file_path is None or wavelengths is None:
            return

        if od_spectrum is None:
            od_spectrum = api.np.full_like(wavelengths, api.np.nan, dtype=float)

        write_header = not self.collection_file_path.exists()
        row = api.np.concatenate(([elapsed_time], api.np.asarray(od_spectrum, dtype=float)))
        with open(self.collection_file_path, "a", encoding="utf-8") as f:
            if write_header:
                wavelength_header = "\t".join(f"{wl:.3f}" for wl in wavelengths)
                f.write(f"time_s\t{wavelength_header}\n")
            api.np.savetxt(f, row.reshape(1, -1), delimiter="\t", fmt="%.8g")
        self.logger.info(f"DATA COLLECTION: Saved point {self.collection_point_index + 1} to {self.collection_file_path}")

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable measurement controls."""
        # No individual button controls needed in new workflow
        pass

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

    def calculate_optical_density(
        self,
        ch1_current: api.np.ndarray,
        ch2_current: api.np.ndarray,
        elapsed_time: api.Optional[float] = None,
        apply_zero_baseline: bool = True,
    ) -> api.Optional[api.np.ndarray]:
        """Calculate optical density using ratio of ratios method with background subtraction.

        OD = log10((I0_ch1 - BG_ch1) / (I0_ch2 - BG_ch2)) / ((I_ch1 - BG_ch1) / (I_ch2 - BG_ch2)))

        where:
        - I0 are reference measurements (lamp ON)
        - BG are background measurements (lamp OFF)
        - I are current measurements

        Parameters
        ----------
        ch1_current : np.ndarray
            Current Ch1 spectrum intensity
        ch2_current : np.ndarray
            Current Ch2 spectrum intensity

        Returns
        -------
        np.ndarray or None
            Optical density spectrum, or None if calculation fails or reference/background missing
        """
        # Require both reference and background for proper OD calculation
        if not self.has_reference or not self.has_background:
            return None

        try:
            # Avoid division by zero
            with api.np.errstate(divide='ignore', invalid='ignore'):
                # Add small offset to avoid division by zero
                offset = 1.0

                # Background-corrected reference ratio: (I0_ch1 - BG_ch1) / (I0_ch2 - BG_ch2)
                ref_ch1_corrected = self.reference_ch1 - self.background_ch1 + offset
                ref_ch2_corrected = self.reference_ch2 - self.background_ch2 + offset
                ref_ratio = ref_ch1_corrected / ref_ch2_corrected

                # Background-corrected current ratio: (I_ch1 - BG_ch1) / (I_ch2 - BG_ch2)
                curr_ch1_corrected = ch1_current - self.background_ch1 + offset
                curr_ch2_corrected = ch2_current - self.background_ch2 + offset
                curr_ratio = curr_ch1_corrected / curr_ch2_corrected

                # OD = log10(ref_ratio / curr_ratio)
                od = api.np.log10(ref_ratio / curr_ratio)

                if elapsed_time is not None and self.demo_kinetics_enabled:
                    od += self.get_demo_species_od(api.np.asarray(self.spec1_widget.wavelengths), elapsed_time)

                if (
                    apply_zero_baseline
                    and self.zero_baseline_od is not None
                    and len(self.zero_baseline_od) == len(od)
                ):
                    od = od - self.zero_baseline_od

                # Replace inf and nan with 0
                od[~api.np.isfinite(od)] = 0

            return od

        except Exception as e:
            self.logger.error(f"Failed to calculate OD: {e}")
            return None

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

        # Disable buttons that require reference
        self.start_collection_btn.setEnabled(False)
        self.track_wl_btn.setEnabled(False)

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
        count = self._measurement_count if hasattr(self, '_measurement_count') else 0
        self.logger.info("="*60)
        self.logger.info(f"SHUTDOWN: Application closing ({count} measurements completed)")

        # Stop timers
        if self.continuous_mode:
            self.continuous_timer.stop()
        if self.data_collection_active:
            self.collection_timer.stop()
            self.lamp_warmup_timer.stop()
            self.collection_countdown_timer.stop()

        # Stop measurement thread
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.measurement_thread.stop()
            self.measurement_thread.wait()

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
        "save_collection_point": save_collection_point,
        "set_controls_enabled": set_controls_enabled,
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
