"""Implementation for init_ui and related operations."""


def _bind_avantes_dual_viewer_methods_init_ui(api):
    """Bind implementation to the owning module and its runtime state."""

    def init_ui(self):
        """Initialize the main UI."""
        title = "Avantes Dual Spectrometer Viewer"
        if self.emulate_hardware:
            title += " [EMULATOR]"
        if self.demo_kinetics_enabled:
            title += " [DEMO KINETICS]"
        self.setWindowTitle(title)
        desktop = api.QApplication.primaryScreen().availableGeometry()
        self.resize(min(1160, desktop.width() - 24), min(720, desktop.height() - 48))
        self.move(desktop.center() - self.rect().center())
        self.create_menu_bar()

        # Central widget
        central_widget = api.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = api.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(5)

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
        controls_splitter.setSizes([590, 590])
        self.link_detector_averages()

        main_layout.addWidget(controls_splitter)
        controls_splitter.hide()
        self.detector_controls_btn.toggled.connect(controls_splitter.setVisible)

        # Plot layout: Left side (Ch1 + Ch2), Right side (OD)
        plot_main_splitter = api.QSplitter(api.Qt.Horizontal)

        # Left side: Channel spectra (vertical split)
        left_plot_splitter = api.QSplitter(api.Qt.Vertical)
        left_plot_splitter.setMinimumWidth(260)

        # Ch1 plot (top left)
        self.plot1 = api.pg.PlotWidget(title="Channel 1 Spectrum")
        self.plot1.setLabel('left', 'Intensity', units='counts')
        self.plot1.setLabel('bottom', 'Wavelength', units='nm')
        self.plot1.getAxis('bottom').enableAutoSIPrefix(False)
        self.plot1.showGrid(x=True, y=True)
        self.plot1.setMinimumWidth(260)
        self.curve1 = self.plot1.plot(pen=api.pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve1 = self.plot1.plot(pen=api.pg.mkPen('m', width=2, style=api.Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve1 = self.plot1.plot(pen=api.pg.mkPen('b', width=2, style=api.Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot1)

        # Ch2 plot (bottom left)
        self.plot2 = api.pg.PlotWidget(title="Channel 2 Spectrum")
        self.plot2.setLabel('left', 'Intensity', units='counts')
        self.plot2.setLabel('bottom', 'Wavelength', units='nm')
        self.plot2.getAxis('bottom').enableAutoSIPrefix(False)
        self.plot2.showGrid(x=True, y=True)
        self.plot2.setMinimumWidth(260)
        self.curve2 = self.plot2.plot(pen=api.pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve2 = self.plot2.plot(pen=api.pg.mkPen('m', width=2, style=api.Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve2 = self.plot2.plot(pen=api.pg.mkPen('b', width=2, style=api.Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot2)

        plot_main_splitter.addWidget(left_plot_splitter)

        # Right side: OD spectrum plot with controls
        od_widget = api.QWidget()
        od_widget.setMinimumWidth(310)
        od_layout = api.QVBoxLayout(od_widget)
        od_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_od = api.pg.PlotWidget(title="Optical Density (OD) Spectrum")
        self.plot_od.setLabel('left', 'OD (Absorbance)', units='AU')
        self.plot_od.setLabel('bottom', 'Wavelength', units='nm')
        self.plot_od.getAxis('bottom').enableAutoSIPrefix(False)
        self.plot_od.getAxis('left').enableAutoSIPrefix(False)
        self.plot_od.showGrid(x=True, y=True)
        self.curve_od = self.plot_od.plot(pen=api.pg.mkPen('w', width=2))  # White for OD
        od_layout.addWidget(self.plot_od)

        # OD plot axis controls
        od_controls = api.QWidget()
        od_controls_layout = api.QVBoxLayout()
        od_controls_layout.setContentsMargins(0, 0, 0, 0)

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
        od_limits_btn = api.QPushButton("OD Plot Limits")
        od_limits_btn.setCheckable(True)
        od_limits_btn.toggled.connect(od_controls.setVisible)
        od_layout.addWidget(od_limits_btn, alignment=api.Qt.AlignLeft)
        od_layout.addWidget(od_controls)
        od_controls.hide()

        plot_main_splitter.addWidget(od_widget)

        plot_main_splitter.setStretchFactor(0, 1)
        plot_main_splitter.setStretchFactor(1, 2)
        plot_main_splitter.setSizes([490, 640])

        main_layout.addWidget(plot_main_splitter, stretch=3)

        # Store reference and background data
        self.reference_ch1 = None
        self.reference_ch2 = None
        self.background_ch1 = None
        self.background_ch2 = None
        self.reference_wavelengths = None
        self.zero_baseline_wavelengths = None
        self.zero_baseline_od = None
        self.has_reference = False
        self.has_background = False

        # Status bar
        self.statusBar().showMessage("Ready")

    def create_control_panel(self) -> api.QWidget:
        """Create the main control panel."""
        panel = api.QWidget()
        layout = api.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        calibration_layout = api.QVBoxLayout()
        calibration_layout.setSpacing(4)
        layout.addLayout(calibration_layout, 0, 0)
        layout.setColumnStretch(1, 1)

        # Arduino control section
        arduino_group = api.QGroupBox("Arduino Control")
        arduino_btn_layout = api.QHBoxLayout()
        arduino_btn_layout.setContentsMargins(6, 4, 6, 4)
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

        self.arduino_status_label = api.QLabel("Status: Unknown")
        self.arduino_status_label.setStyleSheet("font-weight: bold;")
        self.arduino_status_label.setMinimumWidth(
            self.arduino_status_label.fontMetrics().horizontalAdvance("Status: Lamp + Avantes")
        )
        arduino_btn_layout.addWidget(self.arduino_status_label, 1)

        arduino_group.setLayout(arduino_btn_layout)
        calibration_layout.addWidget(arduino_group)

        # Reference and Background measurement section
        ref_bg_group = api.QGroupBox("Calibration")
        ref_bg_layout = api.QVBoxLayout()

        # Block averaging for reference/background. Avantes hardware averages
        # are controlled in the spectrometer panels.
        avg_layout = api.QHBoxLayout()
        avg_layout.addWidget(api.QLabel("Repeats:"))
        self.ref_repeats_spin = api.QSpinBox()
        self.ref_repeats_spin.setRange(1, 100)
        self.ref_repeats_spin.setValue(1)
        avg_layout.addWidget(self.ref_repeats_spin)
        avg_layout.addWidget(api.QLabel("Blocks / repeat:"))
        self.ref_blocks_spin = api.QSpinBox()
        self.ref_blocks_spin.setRange(1, 100)
        self.ref_blocks_spin.setValue(3)
        self.ref_blocks_spin.setToolTip("Number of spectra, already averaged by Avantes, to average in Python")
        avg_layout.addWidget(self.ref_blocks_spin)
        ref_bg_layout.addLayout(avg_layout)

        # Buttons
        btn_layout = api.QHBoxLayout()
        self.measure_ref_btn = api.QPushButton("Reference")
        self.measure_ref_btn.clicked.connect(self.measure_reference)
        self.measure_ref_btn.setToolTip("Measure reference with lamp ON")

        self.measure_bg_btn = api.QPushButton("Background")
        self.measure_bg_btn.clicked.connect(self.measure_background)
        self.measure_bg_btn.setToolTip("Measure background with lamp OFF")
        btn_layout.addWidget(self.measure_bg_btn)
        self.measure_empty_btn = api.QPushButton("Empty")
        self.measure_empty_btn.setToolTip("Measure the illuminated empty optical path")
        self.measure_empty_btn.clicked.connect(lambda: self.measure_calibration("empty"))
        btn_layout.addWidget(self.measure_empty_btn)
        btn_layout.addWidget(self.measure_ref_btn)

        self.stop_measure_btn = api.QPushButton("Abort")
        self.stop_measure_btn.clicked.connect(self.stop_measurement)
        self.stop_measure_btn.setEnabled(False)
        self.stop_measure_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_measure_btn.setToolTip("Abort current reference/background measurement")
        btn_layout.addWidget(self.stop_measure_btn)

        ref_bg_layout.addLayout(btn_layout)
        zero_layout = api.QHBoxLayout()
        self.zero_empty_btn = api.QPushButton("Set Empty Zero")
        self.zero_empty_btn.setToolTip("Optional. Display the selected Empty as zero OD.")
        self.zero_empty_btn.clicked.connect(lambda: self.set_calibration_zero("empty"))
        zero_layout.addWidget(self.zero_empty_btn)
        self.zero_reference_btn = api.QPushButton("Set Reference Zero")
        self.zero_reference_btn.setToolTip("Optional. Display the measured reference as zero OD.")
        self.zero_reference_btn.clicked.connect(lambda: self.set_calibration_zero("reference"))
        zero_layout.addWidget(self.zero_reference_btn)
        ref_bg_layout.addLayout(zero_layout)
        ref_bg_group.setLayout(ref_bg_layout)
        calibration_layout.addWidget(ref_bg_group)

        sample_group = api.QGroupBox("Required sample metadata")
        sample_layout = api.QGridLayout(sample_group)
        sample_layout.setContentsMargins(6, 4, 6, 4)
        self.measured_volume_spin = api.QDoubleSpinBox()
        self.aperture_diameter_spin = api.QDoubleSpinBox()
        self.sample_path_spin = api.QDoubleSpinBox()
        for row, label, spin, unit, maximum in (
            (0, "Measured volume:", self.measured_volume_spin, "mL", 1_000_000),
            (1, "Entrance aperture diameter:", self.aperture_diameter_spin, "mm", 1000),
            (2, "Sample optical path:", self.sample_path_spin, "mm", 1000),
        ):
            spin.setDecimals(3)
            spin.setRange(0, maximum)
            spin.setSingleStep(0.1)
            spin.setSuffix(f" {unit}")
            spin.setSpecialValueText("Required")
            spin.setKeyboardTracking(False)
            spin.setAccessibleName(label.rstrip(":"))
            spin.valueChanged.connect(self.set_sample_geometry)
            sample_layout.addWidget(api.QLabel(label), row, 0)
            sample_layout.addWidget(spin, row, 1)
        self.cell_type_combo = api.QComboBox()
        self.cell_type_combo.setAccessibleName("Quartz cell type")
        self.cell_type_combo.addItem("Select QZ or QS", "")
        self.cell_type_combo.addItems(api.QUARTZ_CELL_TYPES)
        self.cell_type_combo.currentIndexChanged.connect(self.set_sample_geometry)
        sample_layout.addWidget(api.QLabel("Quartz cell type:"), 3, 0)
        sample_layout.addWidget(self.cell_type_combo, 3, 1)
        calibration_layout.addWidget(sample_group)
        calibration_layout.addStretch()

        # Data collection section
        data_group = api.QGroupBox("Data Collection")
        data_layout = api.QGridLayout()

        data_layout.addWidget(api.QLabel("Rate (s):"), 0, 0)
        self.collection_rate_spin = api.QDoubleSpinBox()
        self.collection_rate_spin.setRange(0.1, 86400.0)
        self.collection_rate_spin.setValue(15.0)
        self.collection_rate_spin.setSingleStep(1.0)
        self.collection_rate_spin.setToolTip("Time between saved data points")
        self.collection_rate_spin.valueChanged.connect(self.on_collection_rate_changed)
        data_layout.addWidget(self.collection_rate_spin, 0, 1)

        self.start_collection_btn = api.QPushButton("Start DC")
        self.start_collection_btn.clicked.connect(self.toggle_data_collection)
        self.start_collection_btn.setEnabled(False)
        data_layout.addWidget(self.start_collection_btn, 0, 2)

        self.show_od_map_btn = api.QPushButton("Show DC")
        self.show_od_map_btn.clicked.connect(self.toggle_od_heatmap_window)
        self.show_od_map_btn.setToolTip("Show OD time map")
        data_layout.addWidget(self.show_od_map_btn, 0, 3)

        self.show_mcr_btn = api.QPushButton("Show MCR")
        self.show_mcr_btn.setEnabled(False)
        self.show_mcr_btn.clicked.connect(self.show_mcr)
        data_layout.addWidget(self.show_mcr_btn, 0, 4)

        self.collection_countdown_label = api.QLabel("Next: -- | Points: 0")
        self.collection_countdown_label.setToolTip("Next data-collection point countdown and saved point count")
        data_layout.addWidget(self.collection_countdown_label, 6, 0, 1, 2)

        data_layout.addWidget(api.QLabel("Folder:"), 1, 0)
        self.save_folder_input = api.QLineEdit(str(api.Path.home() / "AvantesData"))
        data_layout.addWidget(self.save_folder_input, 1, 1, 1, 3)

        self.browse_save_btn = api.QPushButton("Browse")
        self.browse_save_btn.clicked.connect(self.browse_save_folder)
        data_layout.addWidget(self.browse_save_btn, 1, 4)

        data_layout.addWidget(api.QLabel("Sample name:"), 2, 0)
        self.save_name_input = api.QLineEdit()
        self.save_name_input.setPlaceholderText("Required before Background")
        self.save_name_input.setToolTip("Base file name without extension")
        self.save_name_input.textChanged.connect(lambda: self.update_analysis_buttons())
        data_layout.addWidget(self.save_name_input, 2, 1, 1, 3)
        self.new_run_btn = api.QPushButton("New Experiment")
        self.new_run_btn.setToolTip("Prepare a separate HDF5 file for another experiment")
        self.new_run_btn.clicked.connect(self.new_named_run)
        data_layout.addWidget(self.new_run_btn, 2, 4)
        data_layout.addWidget(api.QLabel("Sample:"), 3, 0)
        self.sample_comment_input = api.QLineEdit()
        self.sample_comment_input.setPlaceholderText("Sample description or notes")
        data_layout.addWidget(self.sample_comment_input, 3, 1, 1, 4)

        data_layout.addWidget(api.QLabel("Run:"), 4, 0)
        self.loaded_collection_label = api.QLabel("No run opened")
        self.loaded_collection_label.setWordWrap(True)
        data_layout.addWidget(self.loaded_collection_label, 4, 1, 1, 2)
        probe_label = api.QLabel("Probe volume:")
        self.probe_volume_spin = api.QDoubleSpinBox()
        self.probe_volume_spin.setDecimals(3)
        self.probe_volume_spin.setRange(0, 1_000_000)
        self.probe_volume_spin.setSingleStep(0.01)
        self.probe_volume_spin.setSuffix(" mL")
        self.probe_volume_spin.setKeyboardTracking(False)
        self.probe_volume_spin.setAccessibleName("Probe volume")
        probe_label.setBuddy(self.probe_volume_spin)
        self.probe_volume_spin.valueChanged.connect(self.set_probe_volume)
        data_layout.addWidget(probe_label, 4, 3)
        data_layout.addWidget(self.probe_volume_spin, 4, 4)

        blank_controls = api.QHBoxLayout()
        self.pause_collection_btn = api.QPushButton("Pause DC")
        self.pause_collection_btn.setEnabled(False)
        self.pause_collection_btn.clicked.connect(self.toggle_collection_pause)
        blank_controls.addWidget(self.pause_collection_btn)

        self.add_blank_btn = api.QPushButton("Add Reference")
        self.add_blank_btn.setEnabled(False)
        self.add_blank_btn.clicked.connect(self.add_reference)
        blank_controls.addWidget(self.add_blank_btn)

        self.irradiation_btn = api.QPushButton("Irradiation marker")
        self.irradiation_btn.setCheckable(True)
        self.irradiation_btn.setToolTip("Record the state of the external irradiation source")
        self.irradiation_btn.clicked.connect(self.toggle_irradiation_marker)
        blank_controls.addWidget(self.irradiation_btn)
        blank_controls.addStretch()
        data_layout.addLayout(blank_controls, 5, 0, 1, 5)
        self.blank_status = api.QLabel()
        self.blank_status.setWordWrap(True)
        data_layout.addWidget(self.blank_status, 7, 0, 1, 5)
        self.exposure_label = api.QLabel()
        self.exposure_label.setWordWrap(True)
        data_layout.addWidget(self.exposure_label, 6, 2, 1, 3)

        self.reference_cell_group = api.QGroupBox("Reference cell")
        reference_layout = api.QVBoxLayout(self.reference_cell_group)
        reference_layout.setContentsMargins(6, 4, 6, 4)
        self.reference_same_cell_check = api.QCheckBox("Same cell as sample")
        self.reference_same_cell_check.setToolTip("Use the sample's optical path length and quartz type")
        self.reference_same_cell_check.toggled.connect(self.set_reference_geometry)
        reference_layout.addWidget(self.reference_same_cell_check)

        self.reference_cell_fields = api.QWidget()
        fields = api.QHBoxLayout(self.reference_cell_fields)
        fields.setContentsMargins(0, 0, 0, 0)
        self.reference_path_spin = api.QDoubleSpinBox()
        self.reference_path_spin.setDecimals(3)
        self.reference_path_spin.setRange(0, 1000)
        self.reference_path_spin.setSuffix(" mm")
        self.reference_path_spin.setSpecialValueText("Required")
        self.reference_path_spin.setKeyboardTracking(False)
        self.reference_path_spin.setAccessibleName("Reference optical path")
        self.reference_path_spin.valueChanged.connect(self.set_reference_geometry)
        fields.addWidget(api.QLabel("Optical path:"))
        fields.addWidget(self.reference_path_spin)
        self.reference_cell_type_combo = api.QComboBox()
        self.reference_cell_type_combo.setAccessibleName("Reference quartz cell type")
        self.reference_cell_type_combo.addItem("Select QZ or QS", "")
        self.reference_cell_type_combo.addItems(api.QUARTZ_CELL_TYPES)
        self.reference_cell_type_combo.currentIndexChanged.connect(self.set_reference_geometry)
        fields.addWidget(api.QLabel("Quartz cell type:"))
        fields.addWidget(self.reference_cell_type_combo)
        reference_layout.addWidget(self.reference_cell_fields)
        data_layout.addWidget(self.reference_cell_group, 8, 0, 1, 5)
        self.update_exposure_label()

        data_group.setLayout(data_layout)
        layout.addWidget(data_group, 0, 1)

        tools_layout = api.QHBoxLayout()
        self.detector_controls_btn = api.QPushButton("Spectrometer Settings")
        self.detector_controls_btn.setCheckable(True)
        tools_layout.addWidget(self.detector_controls_btn)
        tools_layout.addStretch()
        self.track_wavelength_spin = api.QDoubleSpinBox()
        self.track_wavelength_spin.setRange(200, 1100)
        self.track_wavelength_spin.setValue(550)
        self.track_wavelength_spin.setSingleStep(1.0)
        self.track_wavelength_spin.setSuffix(" nm")
        tools_layout.addWidget(self.track_wavelength_spin)

        self.track_wl_btn = api.QPushButton("Track Wavelength")
        self.track_wl_btn.clicked.connect(self.open_wavelength_tracker)
        self.track_wl_btn.setEnabled(False)
        tools_layout.addWidget(self.track_wl_btn)

        # Live preview control
        self.continuous_btn = api.QPushButton("Start Live Preview")
        self.continuous_btn.setToolTip("Preview spectra and save their raw counts separately in HDF5")
        self.continuous_btn.clicked.connect(self.toggle_continuous_readout)
        self.continuous_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        tools_layout.addWidget(self.continuous_btn)

        # Export button
        self.export_btn = api.QPushButton("Export Data")
        self.export_btn.clicked.connect(self.export_data)
        tools_layout.addWidget(self.export_btn)

        # Clear button
        self.clear_btn = api.QPushButton("Clear Plots")
        self.clear_btn.clicked.connect(self.clear_plots)
        tools_layout.addWidget(self.clear_btn)

        layout.addLayout(tools_layout, 1, 0, 1, 2)
        panel.setLayout(layout)
        return panel

    def create_menu_bar(self):
        """Create top-level application menus."""
        data_menu = self.menuBar().addMenu("Data")
        data_menu.addAction("Open HDF5…", self.load_collection_hdf5)
        data_menu.addAction("Load DAT...", self.load_collection_dat)

        analysis = self.menuBar().addMenu("Analysis")
        self.calibration_history_action = analysis.addAction("Calibration from raw data…", self.inspect_calibration_history)
        self.recalculate_action = analysis.addAction("Recalculate OD from blanks", self.recalculate_blank_od)
        self.mcr_action = analysis.addAction("Run MCR-ALS…", self.run_mcr)
        self.show_mcr_action = analysis.addAction("Show latest MCR-ALS", self.show_latest_mcr)
        for action in (self.recalculate_action, self.mcr_action, self.show_mcr_action):
            action.setEnabled(False)

        experiment = self.menuBar().addMenu("Experiment")
        self.geometry_action = experiment.addAction("Dose and sample geometry…", self.edit_exposure_setup)
        self.irradiation_action = experiment.addAction("Mark irradiation on", self.toggle_irradiation_marker)
        self.irradiation_action.setEnabled(False)

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
        if self.closing_requested or self.current_measurement_role is not None:
            self.statusBar().showMessage("Measurement already in progress...")
            return False

        role = measurement_role or ("preview" if self.continuous_mode else "manual")
        widgets = (self.spec1_widget, self.spec2_widget)
        devices = [widget.spec for widget in widgets]
        thread = None
        try:
            if not all(devices):
                raise RuntimeError("Both spectrometers must be connected")
            configs = [widget.get_measurement_config() for widget in widgets]
            if not all(configs):
                raise RuntimeError("Failed to create measurement configuration")
            if averages_override is not None:
                for cfg in configs:
                    cfg.m_NrAverages = int(averages_override)
            channels = [
                dict(self.get_spectrometer_settings(w),
                     integration_ms=float(cfg.m_IntegrationTime),
                     averages=int(cfg.m_NrAverages),
                     trigger_mode=int(cfg.m_Trigger.m_Mode),
                     trigger_source=int(cfg.m_Trigger.m_Source),
                     integration_delay=int(getattr(cfg, "m_IntegrationDelay", 0)),
                     start_pixel=int(getattr(cfg, "m_StartPixel", 0)),
                     stop_pixel=int(cfg.m_StopPixel))
                for w, cfg in zip(widgets, configs)
            ]
            metadata = dict(
                utc_s=api.time.time(), role=role, channels=channels,
                arduino_frequency_hz=self.arduino_frequency_hz, lamp_on=self.is_lamp_enabled(),
                avantes_trigger_on=self.is_avantes_enabled(), collection_interval_s=self.collection_rate_spin.value(),
            )
            if self.demo_kinetics_enabled:
                apply_demo_optical_density(self, devices[0], metadata)

            trigger_period = 1.0 / max(self.arduino_frequency_hz, 1.0)
            acquisition_s = max(
                (channel["integration_ms"] / 1000.0
                 + (trigger_period if channel["trigger_mode"] in {1, 2} else 0.0))
                * channel["averages"] for channel in channels
            )
            thread = api.MeasurementThread(
                spectrometers=devices, configs=configs, num_measurements=1,
                timeout=max(10.0, acquisition_s + 5.0),
            )
            thread.measurement_complete.connect(self.on_measurement_complete)
            thread.measurement_error.connect(self.on_measurement_error)
            thread.finished.connect(self.on_measurement_finished)
            self.measurement_thread = thread
            self.current_measurement_role = role
            self.measurement_metadata = metadata
            self.update_analysis_buttons()
            self.statusBar().showMessage("Measuring…")
            thread.start()
        except Exception as exc:
            self.logger.exception("Could not start %s acquisition", role)
            if thread is not None:
                thread.deleteLater()
            self.measurement_thread = None
            self.current_measurement_role = None
            self.measurement_metadata = None
            self.update_analysis_buttons()
            if self.continuous_mode:
                self.stop_live_preview()
                self.statusBar().showMessage(f"Could not start acquisition: {exc}")
            else:
                api.QMessageBox.critical(self, "Acquisition could not start", str(exc))
            return False

        if role in {"reference", "empty", "background", "blank", "collection"}:
            self.logger.info(
                "MEASUREMENT: role=%s, Avantes averages ch1=%s, ch2=%s",
                role, channels[0]["averages"], channels[1]["averages"],
            )
        return True

    def apply_demo_optical_density(self, spectrometer, metadata):
        role = metadata["role"]
        wavelengths = self.spec1_widget.wavelengths
        has_empty = "empty" in self.calibration_blocks
        od = 0.0
        if has_empty and role in {"reference", "collection", "blank", "preview", "manual"}:
            od = 0.03 + 0.02 * api.np.exp(-0.5 * ((wavelengths - 320.0) / 120.0) ** 2)
        if role in {"collection", "blank"}:
            elapsed = metadata["utc_s"] - self.collection_start_time
            if has_empty:
                elapsed = self.collection_run.irradiation_seconds(elapsed)
            progress = 1.0 - api.np.exp(-max(0.0, elapsed) / max(1.0, self.demo_kinetics_duration_s))
            # The sample and water blank include the same simulated fiber loss.
            uv_band = api.np.exp(-0.5 * ((wavelengths - 285.0) / 43.0) ** 2)
            od += 0.24 * progress * uv_band
            if role == "collection":
                od += self.get_demo_species_od(wavelengths, elapsed)
        spectrometer.sample_optical_density = od

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
        self.lamp_min_off_seconds = float(dialog.min_off_spin.value())
        self.auto_lamp_management_enabled = dialog.auto_lamp_check.isChecked()
        self.lamp_off_between_points_enabled = dialog.lamp_off_between_check.isChecked()
        self.set_arduino_frequency_hz(dialog.frequency_spin.value())

        if self.data_collection_active and self.collection_next_due_time:
            self.schedule_collection_due_time(self.collection_next_due_time)

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
    }
