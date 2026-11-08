"""Implementation for init_ui and related operations."""


def _bind_avantes_dual_viewer_methods_init_ui(api):
    """Bind implementation to the owning module and its runtime state."""

    def init_ui(self):
        """Initialize the main UI."""
        title = "Avantes Dual Spectrometer Viewer"
        if self.emulate_hardware:
            title += " [EMULATOR]"
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1400, 900)
        self.create_menu_bar()

        # Central widget
        central_widget = api.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = api.QVBoxLayout(central_widget)

        # Top control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # Splitter for spectrometer controls
        controls_splitter = api.QSplitter(api.Qt.Horizontal)

        # Spectrometer 1 controls
        self.spec1_widget = api.SpectrometerWidget(1, emulate_hardware=self.emulate_hardware)
        controls_splitter.addWidget(self.spec1_widget)

        # Spectrometer 2 controls
        self.spec2_widget = api.SpectrometerWidget(2, emulate_hardware=self.emulate_hardware)
        controls_splitter.addWidget(self.spec2_widget)
        self.link_detector_averages()

        main_layout.addWidget(controls_splitter)

        # Plot layout: Left side (Ch1 + Ch2), Right side (OD)
        plot_main_splitter = api.QSplitter(api.Qt.Horizontal)

        # Left side: Channel spectra (vertical split)
        left_plot_splitter = api.QSplitter(api.Qt.Vertical)

        # Ch1 plot (top left)
        self.plot1 = api.pg.PlotWidget(title="Channel 1 Spectrum")
        self.plot1.setLabel('left', 'Intensity', units='counts')
        self.plot1.setLabel('bottom', 'Wavelength', units='nm')
        self.plot1.showGrid(x=True, y=True)
        self.curve1 = self.plot1.plot(pen=api.pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve1 = self.plot1.plot(pen=api.pg.mkPen('m', width=2, style=api.Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve1 = self.plot1.plot(pen=api.pg.mkPen('b', width=2, style=api.Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot1)

        # Ch2 plot (bottom left)
        self.plot2 = api.pg.PlotWidget(title="Channel 2 Spectrum")
        self.plot2.setLabel('left', 'Intensity', units='counts')
        self.plot2.setLabel('bottom', 'Wavelength', units='nm')
        self.plot2.showGrid(x=True, y=True)
        self.curve2 = self.plot2.plot(pen=api.pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve2 = self.plot2.plot(pen=api.pg.mkPen('m', width=2, style=api.Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve2 = self.plot2.plot(pen=api.pg.mkPen('b', width=2, style=api.Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot2)

        plot_main_splitter.addWidget(left_plot_splitter)

        # Right side: OD spectrum plot with controls
        od_widget = api.QWidget()
        od_layout = api.QVBoxLayout(od_widget)
        od_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_od = api.pg.PlotWidget(title="Optical Density (OD) Spectrum")
        self.plot_od.setLabel('left', 'OD (Absorbance)', units='AU')
        self.plot_od.setLabel('bottom', 'Wavelength', units='nm')
        self.plot_od.getAxis('bottom').enableAutoSIPrefix(False)
        self.plot_od.showGrid(x=True, y=True)
        self.curve_od = self.plot_od.plot(pen=api.pg.mkPen('w', width=2))  # White for OD
        od_layout.addWidget(self.plot_od)

        # OD plot axis controls
        od_controls = api.QGroupBox("OD Plot Limits")
        od_controls_layout = api.QHBoxLayout()

        # X-axis (Wavelength) controls
        x_group = api.QGroupBox("Wavelength (nm)")
        x_layout = api.QHBoxLayout()

        self.od_x_auto_check = api.QCheckBox("Auto")
        self.od_x_auto_check.setChecked(True)
        self.od_x_auto_check.stateChanged.connect(self.update_od_axis_limits)
        x_layout.addWidget(self.od_x_auto_check)

        x_layout.addWidget(api.QLabel("Min:"))
        self.od_x_min_spin = api.QDoubleSpinBox()
        self.od_x_min_spin.setRange(0, 2000)
        self.od_x_min_spin.setValue(200)
        self.od_x_min_spin.setSingleStep(10)
        self.od_x_min_spin.setEnabled(False)
        self.od_x_min_spin.valueChanged.connect(self.update_od_axis_limits)
        x_layout.addWidget(self.od_x_min_spin)

        x_layout.addWidget(api.QLabel("Max:"))
        self.od_x_max_spin = api.QDoubleSpinBox()
        self.od_x_max_spin.setRange(0, 2000)
        self.od_x_max_spin.setValue(1100)
        self.od_x_max_spin.setSingleStep(10)
        self.od_x_max_spin.setEnabled(False)
        self.od_x_max_spin.valueChanged.connect(self.update_od_axis_limits)
        x_layout.addWidget(self.od_x_max_spin)

        x_group.setLayout(x_layout)
        od_controls_layout.addWidget(x_group)

        # Y-axis (OD) controls
        y_group = api.QGroupBox("OD (AU)")
        y_layout = api.QHBoxLayout()

        self.od_y_auto_check = api.QCheckBox("Auto")
        self.od_y_auto_check.setChecked(True)
        self.od_y_auto_check.stateChanged.connect(self.update_od_axis_limits)
        y_layout.addWidget(self.od_y_auto_check)

        y_layout.addWidget(api.QLabel("Min:"))
        self.od_y_min_spin = api.QDoubleSpinBox()
        self.od_y_min_spin.setRange(-5.0, 5.0)
        self.od_y_min_spin.setValue(-0.5)
        self.od_y_min_spin.setSingleStep(0.1)
        self.od_y_min_spin.setDecimals(2)
        self.od_y_min_spin.setEnabled(False)
        self.od_y_min_spin.valueChanged.connect(self.update_od_axis_limits)
        y_layout.addWidget(self.od_y_min_spin)

        y_layout.addWidget(api.QLabel("Max:"))
        self.od_y_max_spin = api.QDoubleSpinBox()
        self.od_y_max_spin.setRange(-5.0, 5.0)
        self.od_y_max_spin.setValue(2.0)
        self.od_y_max_spin.setSingleStep(0.1)
        self.od_y_max_spin.setDecimals(2)
        self.od_y_max_spin.setEnabled(False)
        self.od_y_max_spin.valueChanged.connect(self.update_od_axis_limits)
        y_layout.addWidget(self.od_y_max_spin)

        y_group.setLayout(y_layout)
        od_controls_layout.addWidget(y_group)

        od_controls.setLayout(od_controls_layout)
        od_layout.addWidget(od_controls)

        plot_main_splitter.addWidget(od_widget)

        # Set initial splitter ratio: 50% left (spectra), 50% right (OD)
        plot_main_splitter.setSizes([700, 700])

        main_layout.addWidget(plot_main_splitter, stretch=3)

        # Store reference and background data
        self.reference_ch1 = None
        self.reference_ch2 = None
        self.background_ch1 = None
        self.background_ch2 = None
        self.reference_wavelengths = None
        self.has_reference = False
        self.has_background = False

        # Status bar
        self.statusBar().showMessage("Ready")

    def create_control_panel(self) -> api.QGroupBox:
        """Create the main control panel."""
        panel = api.QGroupBox("Measurement Controls")
        layout = api.QHBoxLayout()

        # Arduino control section
        arduino_group = api.QGroupBox("Arduino Control")
        arduino_layout = api.QVBoxLayout()

        arduino_btn_layout = api.QHBoxLayout()
        self.lamp_on_btn = api.QPushButton("Lamp ON")
        self.lamp_on_btn.clicked.connect(lambda: self.set_lamp_on())
        arduino_btn_layout.addWidget(self.lamp_on_btn)

        self.lamp_off_btn = api.QPushButton("Lamp OFF")
        self.lamp_off_btn.clicked.connect(lambda: self.set_lamp_off())
        arduino_btn_layout.addWidget(self.lamp_off_btn)

        self.arduino_advanced_btn = api.QPushButton("Advanced")
        advanced_menu = api.QMenu(self)
        advanced_menu.addAction("Collection Settings...", self.open_collection_settings)
        advanced_menu.addSeparator()
        advanced_menu.addAction("Lamp + Avantes", self.set_lamp_and_avantes)
        advanced_menu.addAction("Avantes Only", self.set_avantes_only)
        advanced_menu.addAction("Arduino OFF", self.set_arduino_off)
        self.arduino_advanced_btn.setMenu(advanced_menu)
        arduino_btn_layout.addWidget(self.arduino_advanced_btn)

        arduino_layout.addLayout(arduino_btn_layout)

        self.arduino_status_label = api.QLabel("Status: Unknown")
        arduino_layout.addWidget(self.arduino_status_label)

        if self.emulate_hardware:
            emulator_label = api.QLabel("Mode: Emulator")
            emulator_label.setStyleSheet("color: purple; font-weight: bold;")
            arduino_layout.addWidget(emulator_label)

        arduino_group.setLayout(arduino_layout)
        layout.addWidget(arduino_group)

        # Reference and Background measurement section
        ref_bg_group = api.QGroupBox("Reference & Background")
        ref_bg_layout = api.QVBoxLayout()

        # Averages control (shared by both)
        avg_layout = api.QHBoxLayout()
        avg_layout.addWidget(api.QLabel("Averages:"))
        self.ref_averages_spin = api.QSpinBox()
        self.ref_averages_spin.setRange(1, 100)
        self.ref_averages_spin.setValue(40)
        self.ref_averages_spin.setToolTip("Avantes hardware trigger averages")
        avg_layout.addWidget(self.ref_averages_spin)
        ref_bg_layout.addLayout(avg_layout)

        # Buttons
        btn_layout = api.QHBoxLayout()
        self.measure_ref_btn = api.QPushButton("Measure Reference")
        self.measure_ref_btn.clicked.connect(self.measure_reference)
        self.measure_ref_btn.setToolTip("Measure reference with lamp ON")
        btn_layout.addWidget(self.measure_ref_btn)

        self.measure_bg_btn = api.QPushButton("Measure Background")
        self.measure_bg_btn.clicked.connect(self.measure_background)
        self.measure_bg_btn.setToolTip("Measure background with lamp OFF")
        btn_layout.addWidget(self.measure_bg_btn)

        self.stop_measure_btn = api.QPushButton("Stop Measurement")
        self.stop_measure_btn.clicked.connect(self.stop_measurement)
        self.stop_measure_btn.setEnabled(False)
        self.stop_measure_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_measure_btn.setToolTip("Abort current reference/background measurement")
        btn_layout.addWidget(self.stop_measure_btn)

        ref_bg_layout.addLayout(btn_layout)
        ref_bg_group.setLayout(ref_bg_layout)
        layout.addWidget(ref_bg_group)

        # Data collection section
        data_group = api.QGroupBox("Data Collection")
        data_layout = api.QGridLayout()

        data_layout.addWidget(api.QLabel("Rate (s):"), 0, 0)
        self.collection_rate_spin = api.QDoubleSpinBox()
        self.collection_rate_spin.setRange(0.1, 86400.0)
        self.collection_rate_spin.setValue(1.0)
        self.collection_rate_spin.setSingleStep(1.0)
        self.collection_rate_spin.setToolTip("Time between saved data points")
        self.collection_rate_spin.valueChanged.connect(self.on_collection_rate_changed)
        data_layout.addWidget(self.collection_rate_spin, 0, 1)

        self.start_collection_btn = api.QPushButton("Start DC")
        self.start_collection_btn.clicked.connect(self.toggle_data_collection)
        self.start_collection_btn.setEnabled(False)
        data_layout.addWidget(self.start_collection_btn, 0, 2)

        self.show_od_map_btn = api.QPushButton("Show")
        self.show_od_map_btn.clicked.connect(self.show_od_heatmap_window)
        self.show_od_map_btn.setToolTip("Show OD time map")
        data_layout.addWidget(self.show_od_map_btn, 0, 3)

        self.collection_countdown_label = api.QLabel("Next: -- | Points: 0")
        self.collection_countdown_label.setToolTip("Next data-collection point countdown and saved point count")
        data_layout.addWidget(self.collection_countdown_label, 0, 4)

        data_layout.addWidget(api.QLabel("Folder:"), 1, 0)
        self.save_folder_input = api.QLineEdit(str(api.Path.home() / "AvantesData"))
        data_layout.addWidget(self.save_folder_input, 1, 1, 1, 3)

        self.browse_save_btn = api.QPushButton("Browse")
        self.browse_save_btn.clicked.connect(self.browse_save_folder)
        data_layout.addWidget(self.browse_save_btn, 1, 4)

        data_layout.addWidget(api.QLabel("Name:"), 2, 0)
        self.save_name_input = api.QLineEdit("avantes_measurement")
        self.save_name_input.setToolTip("Base file name without extension")
        data_layout.addWidget(self.save_name_input, 2, 1, 1, 4)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # Wavelength tracking
        wl_group = api.QGroupBox("Wavelength Tracking")
        wl_layout = api.QHBoxLayout()

        wl_layout.addWidget(api.QLabel("Wavelength (nm):"))
        self.track_wavelength_spin = api.QDoubleSpinBox()
        self.track_wavelength_spin.setRange(200, 1100)
        self.track_wavelength_spin.setValue(550)
        self.track_wavelength_spin.setSingleStep(1.0)
        wl_layout.addWidget(self.track_wavelength_spin)

        self.track_wl_btn = api.QPushButton("Track Wavelength")
        self.track_wl_btn.clicked.connect(self.open_wavelength_tracker)
        self.track_wl_btn.setEnabled(False)
        wl_layout.addWidget(self.track_wl_btn)

        wl_group.setLayout(wl_layout)
        layout.addWidget(wl_group)

        layout.addStretch()

        # Live preview control
        self.continuous_btn = api.QPushButton("Start Live Preview")
        self.continuous_btn.clicked.connect(self.toggle_continuous_readout)
        self.continuous_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        layout.addWidget(self.continuous_btn)

        self.settings_btn = api.QPushButton("Settings")
        self.settings_btn.setMenu(self.create_settings_menu(self.settings_btn))
        layout.addWidget(self.settings_btn)

        # Export button
        self.export_btn = api.QPushButton("Export Data")
        self.export_btn.clicked.connect(self.export_data)
        layout.addWidget(self.export_btn)

        # Clear button
        self.clear_btn = api.QPushButton("Clear Plots")
        self.clear_btn.clicked.connect(self.clear_plots)
        layout.addWidget(self.clear_btn)

        panel.setLayout(layout)
        return panel

    def create_menu_bar(self):
        """Create top-level application menus."""
        settings_menu = self.menuBar().addMenu("Settings")
        self.populate_settings_menu(settings_menu)

    def create_settings_menu(self, parent=None):
        """Create settings menu for toolbar button."""
        menu = api.QMenu(parent or self)
        self.populate_settings_menu(menu)
        return menu

    def populate_settings_menu(self, menu):
        """Populate settings actions."""
        menu.addAction("Collection Settings...", self.open_collection_settings)
        menu.addSeparator()
        menu.addAction("Load JSON...", self.load_settings_json)
        menu.addAction("Save JSON As...", self.save_settings_json_as)
        menu.addAction("Update JSON", self.update_settings_json)

    def update_od_axis_limits(self):
        """Update OD plot axis limits based on auto/manual settings."""
        # Enable/disable manual controls based on auto checkboxes
        self.od_x_min_spin.setEnabled(not self.od_x_auto_check.isChecked())
        self.od_x_max_spin.setEnabled(not self.od_x_auto_check.isChecked())
        self.od_y_min_spin.setEnabled(not self.od_y_auto_check.isChecked())
        self.od_y_max_spin.setEnabled(not self.od_y_auto_check.isChecked())

        # Apply limits
        if not self.od_x_auto_check.isChecked():
            self.plot_od.setXRange(self.od_x_min_spin.value(), self.od_x_max_spin.value(), padding=0)
        else:
            self.plot_od.enableAutoRange(axis='x')

        if not self.od_y_auto_check.isChecked():
            self.plot_od.setYRange(self.od_y_min_spin.value(), self.od_y_max_spin.value(), padding=0)
        else:
            self.plot_od.enableAutoRange(axis='y')

    def link_detector_averages(self):
        """Keep detector average and trigger controls synchronized."""
        self._syncing_detector_averages = False
        self._syncing_detector_triggers = False

        def sync_averages(source, target):
            if self._syncing_detector_averages:
                return
            self._syncing_detector_averages = True
            target.averages_spin.setValue(source.averages_spin.value())
            self._syncing_detector_averages = False
            if self.continuous_mode:
                self.update_live_preview_interval()

        def sync_trigger_mode(source, target):
            if self._syncing_detector_triggers:
                return
            self._syncing_detector_triggers = True
            target.trigger_combo.setCurrentIndex(source.trigger_combo.currentIndex())
            self._syncing_detector_triggers = False
            if self.continuous_mode:
                self.update_live_preview_interval()

        self.spec1_widget.averages_spin.valueChanged.connect(
            lambda: sync_averages(self.spec1_widget, self.spec2_widget)
        )
        self.spec2_widget.averages_spin.valueChanged.connect(
            lambda: sync_averages(self.spec2_widget, self.spec1_widget)
        )
        self.spec1_widget.trigger_combo.currentIndexChanged.connect(
            lambda: sync_trigger_mode(self.spec1_widget, self.spec2_widget)
        )
        self.spec2_widget.trigger_combo.currentIndexChanged.connect(
            lambda: sync_trigger_mode(self.spec2_widget, self.spec1_widget)
        )
        self.spec1_widget.integration_spin.valueChanged.connect(self.update_live_preview_interval)
        self.spec2_widget.integration_spin.valueChanged.connect(self.update_live_preview_interval)
        self.spec1_widget.trigger_combo.currentIndexChanged.connect(self.update_live_preview_interval)
        self.spec2_widget.trigger_combo.currentIndexChanged.connect(self.update_live_preview_interval)

    def get_live_preview_interval_ms(self) -> int:
        """Return preview interval for hardware-triggered acquisition."""
        avg = max(self.spec1_widget.averages_spin.value(), self.spec2_widget.averages_spin.value())
        trigger_mode = max(self.spec1_widget.trigger_combo.currentIndex(), self.spec2_widget.trigger_combo.currentIndex())
        if trigger_mode in {1, 2}:
            return max(50, int(avg * 1000.0 / max(self.arduino_frequency_hz, 1.0)))
        integration_ms = max(self.spec1_widget.integration_spin.value(), self.spec2_widget.integration_spin.value())
        return max(50, int(avg * integration_ms))

    def update_live_preview_interval(self):
        """Apply live preview interval if preview is running."""
        if self.continuous_mode:
            self.continuous_timer.start(self.get_live_preview_interval_ms())

    def get_collection_min_rate_s(self) -> float:
        """Return minimum non-overlapping collection rate."""
        avg = self.get_detector_average_count()
        trigger_mode = max(self.spec1_widget.trigger_combo.currentIndex(), self.spec2_widget.trigger_combo.currentIndex())
        if trigger_mode in {1, 2}:
            acquisition_s = avg / max(self.arduino_frequency_hz, 1.0)
        else:
            integration_ms = max(self.spec1_widget.integration_spin.value(), self.spec2_widget.integration_spin.value())
            acquisition_s = avg * integration_ms / 1000.0
        return max(0.1, acquisition_s)

    def get_detector_average_count(self) -> int:
        """Return synced detector average count."""
        return max(self.spec1_widget.averages_spin.value(), self.spec2_widget.averages_spin.value())

    def validate_collection_rate(self, show_warning: bool = False) -> bool:
        """Ensure collection rate is not shorter than one acquisition."""
        min_rate_s = self.get_collection_min_rate_s()
        current_rate_s = self.collection_rate_spin.value()
        if current_rate_s + 1e-9 >= min_rate_s:
            return True

        self.collection_rate_spin.setValue(min_rate_s)
        message = (
            f"Rate cannot be shorter than acquisition time.\n\n"
            f"Detector averages = {self.get_detector_average_count()}\n"
            f"Minimum rate = {min_rate_s:.3g} s\n\n"
            f"Rate was set to {min_rate_s:.3g} s."
        )
        self.logger.warning(f"DATA COLLECTION: {message.replace(chr(10), ' ')}")
        if show_warning:
            api.QMessageBox.warning(self, "Rate Too Short", message)
        return False

    def single_measurement(self, averages_override=None, measurement_role=None):
        """Perform a single parallel measurement."""
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.statusBar().showMessage("Measurement already in progress...")
            return

        spec1 = self.spec1_widget.spec
        spec2 = self.spec2_widget.spec

        # Check both spectrometers are connected
        if not spec1 or not spec2:
            if not self.continuous_mode:
                api.QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            else:
                self.logger.error("Spectrometer connection lost - stopping live preview")
                self.stop_live_preview()
            return

        # Validate connections are still active
        try:
            cfg1 = self.spec1_widget.get_measurement_config()
            cfg2 = self.spec2_widget.get_measurement_config()
            if averages_override is not None:
                cfg1.m_NrAverages = int(averages_override)
                cfg2.m_NrAverages = int(averages_override)
        except Exception as e:
            self.logger.error(f"Failed to get measurement config: {e}")
            if self.continuous_mode:
                self.logger.error("Stopping live preview due to connection error")
                self.stop_live_preview()
            else:
                api.QMessageBox.critical(self, "Error", f"Connection error:\n{str(e)}")
            return

        if not cfg1 or not cfg2:
            if not self.continuous_mode:
                api.QMessageBox.warning(self, "Error", "Failed to create measurement configuration")
            return

        # Disable controls during measurement
        self.set_controls_enabled(False)
        if measurement_role:
            self.current_measurement_role = measurement_role
        else:
            self.current_measurement_role = "preview" if self.continuous_mode else "manual"
        self.statusBar().showMessage("Measuring...")

        # Start measurement thread
        self.measurement_thread = api.MeasurementThread(
            spectrometers=[spec1, spec2],
            configs=[cfg1, cfg2],
            num_measurements=1
        )
        self.measurement_thread.measurement_complete.connect(self.on_measurement_complete)
        self.measurement_thread.measurement_error.connect(self.on_measurement_error)
        self.measurement_thread.finished.connect(self.on_measurement_finished)
        self.measurement_thread.start()

    def continuous_measurement(self):
        """Trigger measurement for live preview mode."""
        # Skip if previous measurement still running
        if self.measurement_thread and self.measurement_thread.isRunning():
            return

        self.single_measurement()

    def get_arduino_state(self):
        """Return current Arduino state from controller."""
        try:
            return self.arduino.get_state()
        except Exception as e:
            self.logger.error(f"ARDUINO: Failed to get state - {e}")
            return False, False

    def set_arduino_frequency_hz(self, frequency_hz: float) -> bool:
        """Set Arduino trigger frequency."""
        frequency = min(max(float(frequency_hz), 1.0), 100.0)
        if self.arduino.set_frequency_hz(frequency):
            self.sync_arduino_frequency_from_controller()
            self.update_live_preview_interval()
            if self.data_collection_active and self.collection_next_due_time:
                self.validate_collection_rate(show_warning=False)
                self.schedule_collection_due_time(self.collection_next_due_time)
            self.logger.info(f"ARDUINO: Frequency set to {self.arduino_frequency_hz:.0f} Hz")
            return True
        self.logger.error(f"ARDUINO: Failed to set frequency to {frequency:.0f} Hz")
        return False

    def sync_arduino_frequency_from_controller(self):
        """Read Arduino trigger frequency if controller supports it."""
        try:
            self.arduino_frequency_hz = float(self.arduino.get_frequency_hz())
        except Exception:
            pass

    def open_collection_settings(self):
        """Open collection settings dialog."""
        dialog = api.CollectionSettingsDialog(self)
        if dialog.exec_() != api.QDialog.Accepted:
            return

        self.lamp_warmup_seconds = float(dialog.warmup_spin.value())
        self.auto_lamp_management_enabled = dialog.auto_lamp_check.isChecked()
        self.lamp_off_between_points_enabled = dialog.lamp_off_between_check.isChecked()
        self.set_arduino_frequency_hz(dialog.frequency_spin.value())

        if self.data_collection_active and self.collection_next_due_time:
            self.schedule_collection_due_time(self.collection_next_due_time)

    def get_settings_dict(self) -> dict:
        """Return current UI settings for JSON export."""
        return {
            "version": 1,
            "arduino": {
                "frequency_hz": float(self.arduino_frequency_hz),
                "lamp_warmup_seconds": float(self.lamp_warmup_seconds),
                "auto_lamp_management_enabled": bool(self.auto_lamp_management_enabled),
                "lamp_off_between_points_enabled": bool(self.lamp_off_between_points_enabled),
            },
            "spectrometers": {
                "1": self.get_spectrometer_settings(self.spec1_widget),
                "2": self.get_spectrometer_settings(self.spec2_widget),
            },
            "reference_background": {
                "averages": int(self.ref_averages_spin.value()),
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

    return {
        "init_ui": init_ui,
        "create_control_panel": create_control_panel,
        "create_menu_bar": create_menu_bar,
        "create_settings_menu": create_settings_menu,
        "populate_settings_menu": populate_settings_menu,
        "update_od_axis_limits": update_od_axis_limits,
        "link_detector_averages": link_detector_averages,
        "get_live_preview_interval_ms": get_live_preview_interval_ms,
        "update_live_preview_interval": update_live_preview_interval,
        "get_collection_min_rate_s": get_collection_min_rate_s,
        "get_detector_average_count": get_detector_average_count,
        "validate_collection_rate": validate_collection_rate,
        "single_measurement": single_measurement,
        "continuous_measurement": continuous_measurement,
        "get_arduino_state": get_arduino_state,
        "set_arduino_frequency_hz": set_arduino_frequency_hz,
        "sync_arduino_frequency_from_controller": sync_arduino_frequency_from_controller,
        "open_collection_settings": open_collection_settings,
        "get_settings_dict": get_settings_dict,
    }
