"""Implementation for _env_bool and related operations."""


def _bind_avantes_dual_viewer_parts_env_bool(api):
    """Bind implementation to the owning module and its runtime state."""

    def _env_bool(name: str, default: bool = False) -> bool:
        value = api.os.environ.get(name)
        if value is None:
            return default
        return value.strip().lower() not in {"0", "false", "no", "off"}

    _env_bool.__module__ = api.__name__
    _env_bool.__qualname__ = "_env_bool"

    class WavelengthTrackerWindow(api.QMainWindow):
        """Window for tracking OD at a specific wavelength over time."""

        def __init__(self, parent, wavelength):
            super().__init__(parent)
            self.parent_viewer = parent
            self.target_wavelength = wavelength
            self.od_history = []
            self.time_history = []
            self.start_time = api.time.time()  # Track time from window creation

            self.init_ui()

        def init_ui(self):
            """Initialize the tracker window UI."""
            self.setWindowTitle(f"OD Tracking at {self.target_wavelength:.1f} nm")
            self.setGeometry(150, 150, 800, 400)

            central_widget = api.QWidget()
            self.setCentralWidget(central_widget)
            layout = api.QVBoxLayout(central_widget)

            # Current value display
            value_group = api.QGroupBox("Current Value")
            value_layout = api.QHBoxLayout()

            value_layout.addWidget(api.QLabel(f"Wavelength: {self.target_wavelength:.1f} nm"))
            value_layout.addStretch()

            value_layout.addWidget(api.QLabel("OD:"))
            self.od_value_label = api.QLabel("---")
            font = api.QFont()
            font.setPointSize(16)
            font.setBold(True)
            self.od_value_label.setFont(font)
            value_layout.addWidget(self.od_value_label)

            value_group.setLayout(value_layout)
            layout.addWidget(value_group)

            # Time series plot
            self.plot = api.pg.PlotWidget(title=f"OD Time Series at {self.target_wavelength:.1f} nm")
            self.plot.setLabel('left', 'OD (Absorbance)', units='AU')
            self.plot.setLabel('bottom', 'Time', units='s')
            self.plot.showGrid(x=True, y=True)
            self.curve = self.plot.plot(pen=api.pg.mkPen('g', width=2), symbol='o', symbolSize=5)
            layout.addWidget(self.plot, stretch=1)

            # Control buttons
            btn_layout = api.QHBoxLayout()

            self.clear_btn = api.QPushButton("Clear History")
            self.clear_btn.clicked.connect(self.clear_history)
            btn_layout.addWidget(self.clear_btn)

            btn_layout.addStretch()

            self.export_btn = api.QPushButton("Export Time Series")
            self.export_btn.clicked.connect(self.export_time_series)
            btn_layout.addWidget(self.export_btn)

            layout.addLayout(btn_layout)

        def set_wavelength(self, wavelength):
            """Update tracked wavelength."""
            self.target_wavelength = wavelength
            self.setWindowTitle(f"OD Tracking at {wavelength:.1f} nm")
            self.plot.setTitle(f"OD Time Series at {wavelength:.1f} nm")
            # Don't clear history when changing wavelength, just reset time
            self.start_time = api.time.time()
            self.clear_history()

        def update_od_value(self, od_spectrum, wavelengths):
            """Update OD value and time series."""
            # Find closest wavelength index
            idx = api.np.argmin(api.np.abs(wavelengths - self.target_wavelength))
            od_value = od_spectrum[idx]

            # Update current value display
            self.od_value_label.setText(f"{od_value:.4f}")

            # Calculate elapsed time from tracker window start
            elapsed_time = api.time.time() - self.start_time

            # Add to history
            self.time_history.append(elapsed_time)
            self.od_history.append(od_value)

            # Update plot
            self.curve.setData(self.time_history, self.od_history)

        def clear_history(self):
            """Clear time series history and reset start time."""
            self.od_history = []
            self.time_history = []
            self.start_time = api.time.time()  # Reset start time
            self.curve.setData([], [])
            self.od_value_label.setText("---")

        def export_time_series(self):
            """Export time series data to CSV."""
            if len(self.time_history) == 0:
                api.QMessageBox.warning(self, "No Data", "No time series data to export")
                return

            filename, _ = api.QFileDialog.getSaveFileName(
                self,
                "Export Time Series",
                f"od_timeseries_{self.target_wavelength:.0f}nm.csv",
                "CSV Files (*.csv)"
            )

            if filename:
                try:
                    data = api.np.column_stack((self.time_history, self.od_history))
                    api.np.savetxt(
                        filename,
                        data,
                        delimiter=',',
                        header=f'Time(s),OD@{self.target_wavelength:.1f}nm(AU)',
                        comments=''
                    )
                    api.QMessageBox.information(self, "Export Complete", f"Time series exported to {filename}")
                except Exception as e:
                    api.QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    WavelengthTrackerWindow.__module__ = api.__name__
    WavelengthTrackerWindow.__qualname__ = "WavelengthTrackerWindow"

    class ODHeatmapWindow(api.QMainWindow):
        """Floating OD time map window."""

        def __init__(self, parent):
            super().__init__(parent)
            self.parent_viewer = parent
            self.setWindowTitle("OD Time Map")
            self.setGeometry(220, 180, 1200, 800)

            self.wavelengths = None
            self.times = None
            self.heatmap = None
            self._regions_initialized = False
            self.detail_range = None

            central_widget = api.QWidget()
            central_layout = api.QVBoxLayout(central_widget)
            central_layout.setContentsMargins(0, 0, 0, 0)
            self.setCentralWidget(central_widget)

            controls = api.QHBoxLayout()
            self.od_source = api.QComboBox()
            for label, source in (
                ("Measured OD (Set Zero applied)", "od_delta"),
                ("OD vs initial blank", "od_vs_blank"),
                ("OD corrected for blank drift", "od_corrected"),
                ("Estimated blank drift", "blank_drift"),
                ("OD vs lamp reference", "od_raw"),
            ):
                self.od_source.addItem(label, source)
            self.od_source.currentIndexChanged.connect(parent.render_od_heatmap)
            controls.addWidget(self.od_source)
            detail = api.QPushButton("Load Zoomed Time Range")
            detail.clicked.connect(self.load_detail)
            controls.addWidget(detail)
            overview = api.QPushButton("Overview")
            overview.clicked.connect(self.show_overview)
            controls.addWidget(overview)
            central_layout.addLayout(controls)

            self.plot = api.pg.PlotWidget(title="OD Time Map")
            self.plot.setLabel('left', 'Time', units='s')
            self.plot.setLabel('bottom', 'Wavelength', units='nm')
            self.plot.getAxis('left').enableAutoSIPrefix(False)
            self.plot.getAxis('bottom').enableAutoSIPrefix(False)
            self.plot.showGrid(x=True, y=True)

            self.image_item = api.pg.ImageItem(axisOrder="row-major")
            self.image_item.setColorMap(api.pg.colormap.get("viridis"))
            self.plot.addItem(self.image_item)

            self.wavelength_region = api.pg.LinearRegionItem([350, 450], orientation='vertical')
            self.time_region = api.pg.LinearRegionItem([0, 1], orientation='horizontal')
            self.wavelength_region.setZValue(10)
            self.time_region.setZValue(11)
            self.wavelength_region.sigRegionChanged.connect(self.update_profiles)
            self.time_region.sigRegionChanged.connect(self.update_profiles)
            self.plot.addItem(self.wavelength_region)
            self.plot.addItem(self.time_region)
            self.plot.setYRange(0, 1, padding=0)
            central_layout.addWidget(self.plot, stretch=3)

            profile_splitter = api.QSplitter(api.Qt.Horizontal)
            self.kinetics_plot = api.pg.PlotWidget(title="Kinetics: mean OD over wavelength band")
            self.kinetics_plot.setLabel('left', 'OD', units='AU')
            self.kinetics_plot.setLabel('bottom', 'Time', units='s')
            self.kinetics_plot.getAxis('bottom').enableAutoSIPrefix(False)
            self.kinetics_plot.showGrid(x=True, y=True)
            self.kinetics_curve = self.kinetics_plot.plot(pen=api.pg.mkPen('y', width=2), symbol='o', symbolSize=4)
            profile_splitter.addWidget(self.kinetics_plot)

            self.spectrum_plot = api.pg.PlotWidget(title="Spectrum: mean OD over time band")
            self.spectrum_plot.setLabel('left', 'OD', units='AU')
            self.spectrum_plot.setLabel('bottom', 'Wavelength', units='nm')
            self.spectrum_plot.getAxis('bottom').enableAutoSIPrefix(False)
            self.spectrum_plot.showGrid(x=True, y=True)
            self.spectrum_curve = self.spectrum_plot.plot(pen=api.pg.mkPen('c', width=2))
            profile_splitter.addWidget(self.spectrum_plot)
            central_layout.addWidget(profile_splitter, stretch=1)

        def closeEvent(self, event):
            """Keep the parent Show/Hide button in sync."""
            self.parent_viewer.od_heatmap_window = None
            if hasattr(self.parent_viewer, "show_od_map_btn"):
                self.parent_viewer.show_od_map_btn.setText("Show DC")
            super().closeEvent(event)

        def load_detail(self):
            self.detail_range = tuple(self.plot.viewRange()[1])
            self.parent_viewer.render_od_heatmap()

        def show_overview(self):
            self.detail_range = None
            self.parent_viewer.render_od_heatmap()

        def set_heatmap(self, wavelengths, rows, times, total_points):
            """Render at most 500 measured rows and preserve exact data for cursor profiles."""
            self.wavelengths = wavelengths
            self.times = api.np.asarray(times, dtype=float)
            self.heatmap = api.np.array(rows, dtype=float) if len(rows) else None
            if self.heatmap is None:
                self.image_item.setVisible(False)
                self.kinetics_curve.setData([], [])
                self.spectrum_curve.setData([], [])
                self.plot.setTitle("OD Time Map (no points in range)")
                return

            x_edges = self._edges_from_centers(self.wavelengths)
            y_edges = self._time_edges(self.times)
            x_min, x_max = float(x_edges[0]), float(x_edges[-1])
            y_min, y_max = float(y_edges[0]), float(y_edges[-1])
            finite = api.np.isfinite(self.heatmap)
            self.image_item.setVisible(bool(finite.any()))
            if finite.any():
                # Rasterize by actual elapsed time. Empty bins show gaps such as a DC pause.
                height = min(500, len(self.times))
                width = min(1024, len(self.wavelengths))
                target_wl = x_min + (api.np.arange(width) + 0.5) * (x_max - x_min) / width
                edges = api.np.searchsorted(x_edges, target_wl, side="right") - 1
                time_bins = api.np.clip(((self.times - y_min) * height / (y_max - y_min)).astype(int),
                                    0, height - 1)
                image = api.np.full((height, width), api.np.nan, dtype=api.np.float32)
                image[time_bins] = self.heatmap[:, edges]
                levels = api.np.min(self.heatmap[finite]), api.np.max(self.heatmap[finite])
                self.image_item.setImage(image, autoLevels=False, levels=levels)
                self.image_item.setRect(api.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
            note = "" if finite.any() else " | no valid OD"
            self.plot.setTitle(f"OD Time Map ({len(rows)} shown / {total_points} recorded{note})")
            self.plot.setXRange(x_min, x_max, padding=0)
            self.plot.setYRange(y_min, y_max, padding=0)
            self._initialize_regions(x_min, x_max, y_min, y_max)
            self.update_profiles()

        def _edges_from_centers(self, centers):
            """Build cell edges from monotonically increasing center coordinates."""
            centers = api.np.asarray(centers, dtype=float)
            if len(centers) == 1:
                return api.np.array([centers[0] - 0.5, centers[0] + 0.5])
            mids = (centers[:-1] + centers[1:]) / 2.0
            first = centers[0] - (mids[0] - centers[0])
            last = centers[-1] + (centers[-1] - mids[-1])
            return api.np.concatenate(([first], mids, [last]))

        def _time_edges(self, times):
            """Build time cell edges while keeping first edge at zero when possible."""
            times = api.np.asarray(times, dtype=float)
            if len(times) == 1:
                width = max(times[0], 1.0)
                return api.np.array([max(0.0, times[0] - width / 2.0), times[0] + width / 2.0])
            edges = self._edges_from_centers(times)
            edges[0] = max(0.0, edges[0])
            if edges[-1] <= edges[0]:
                edges[-1] = edges[0] + 1.0
            return edges

        def _initialize_regions(self, x_min, x_max, y_min, y_max):
            """Set initial cursor regions once."""
            if self._regions_initialized:
                return
            x_width = x_max - x_min
            y_width = y_max - y_min
            self.wavelength_region.setRegion([x_min + 0.4 * x_width, x_min + 0.6 * x_width])
            self.time_region.setRegion([y_min, max(y_min + min(y_width, 1.0), y_min + 0.1)])
            self._regions_initialized = True

        def update_profiles(self):
            """Update kinetics and spectrum from cursor-selected regions."""
            if self.heatmap is None or self.wavelengths is None or self.times is None:
                return

            wl_min, wl_max = self.wavelength_region.getRegion()
            time_min, time_max = self.time_region.getRegion()
            wl_mask = (self.wavelengths >= min(wl_min, wl_max)) & (self.wavelengths <= max(wl_min, wl_max))
            time_mask = (self.times >= min(time_min, time_max)) & (self.times <= max(time_min, time_max))

            if api.np.any(wl_mask):
                kinetics = self.mean_profile(self.heatmap[:, wl_mask], axis=1)
                if api.np.isfinite(kinetics).any():
                    self.kinetics_curve.setData(self.times, kinetics)
                else:
                    self.kinetics_curve.setData([], [])
                self.kinetics_plot.setTitle(
                    f"Kinetics: mean OD {min(wl_min, wl_max):.1f}-{max(wl_min, wl_max):.1f} nm"
                )
            else:
                self.kinetics_curve.setData([], [])

            if api.np.any(time_mask):
                spectrum = self.mean_profile(self.heatmap[time_mask, :], axis=0)
                self.spectrum_curve.setData(self.wavelengths, spectrum)
                self.spectrum_plot.setTitle(
                    f"Spectrum: mean OD {min(time_min, time_max):.1f}-{max(time_min, time_max):.1f} s"
                )
            else:
                self.spectrum_curve.setData([], [])

        @staticmethod
        def mean_profile(values, axis):
            counts = api.np.isfinite(values).sum(axis=axis)
            totals = api.np.nansum(values, axis=axis)
            return api.np.divide(totals, counts, out=api.np.full_like(totals, api.np.nan), where=counts > 0)

    ODHeatmapWindow.__module__ = api.__name__
    ODHeatmapWindow.__qualname__ = "ODHeatmapWindow"

    class CollectionSettingsDialog(api.QDialog):
        """Dialog for Arduino frequency and lamp-management settings."""

        def __init__(self, parent):
            super().__init__(parent)
            self.parent_viewer = parent
            self.setWindowTitle("Collection Settings")

            layout = api.QVBoxLayout(self)
            form = api.QFormLayout()

            self.frequency_spin = api.QSpinBox()
            self.frequency_spin.setRange(1, 100)
            self.frequency_spin.setValue(int(round(parent.arduino_frequency_hz)))
            form.addRow("Arduino frequency (Hz):", self.frequency_spin)

            self.warmup_spin = api.QDoubleSpinBox()
            self.warmup_spin.setRange(0.0, 3600.0)
            self.warmup_spin.setDecimals(1)
            self.warmup_spin.setSingleStep(10.0)
            self.warmup_spin.setValue(parent.lamp_warmup_seconds)
            form.addRow("Lamp warmup lead (s):", self.warmup_spin)

            self.min_off_spin = api.QDoubleSpinBox()
            self.min_off_spin.setRange(0.0, 3600.0)
            self.min_off_spin.setDecimals(1)
            self.min_off_spin.setSingleStep(10.0)
            self.min_off_spin.setValue(parent.lamp_min_off_seconds)
            form.addRow("Minimum lamp-off gap (s):", self.min_off_spin)

            self.auto_lamp_check = api.QCheckBox("Auto-control lamp during data collection")
            self.auto_lamp_check.setChecked(parent.auto_lamp_management_enabled)
            form.addRow("", self.auto_lamp_check)

            self.lamp_off_between_check = api.QCheckBox("Turn lamp off between long-interval points")
            self.lamp_off_between_check.setChecked(parent.lamp_off_between_points_enabled)
            form.addRow("", self.lamp_off_between_check)

            layout.addLayout(form)

            buttons = api.QDialogButtonBox(api.QDialogButtonBox.Ok | api.QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

    CollectionSettingsDialog.__module__ = api.__name__
    CollectionSettingsDialog.__qualname__ = "CollectionSettingsDialog"

    class MeasurementThread(api.QThread):
        """Background thread for parallel spectrometer measurements."""

        measurement_complete = api.pyqtSignal(dict)  # Signal with results
        measurement_error = api.pyqtSignal(str)  # Signal with error message

        def __init__(self, spectrometers, configs, num_measurements=1):
            super().__init__()
            self.spectrometers = spectrometers
            self.configs = configs
            self.num_measurements = num_measurements
            self.running = True
            self.diagnostics = {}

        def run(self):
            """Execute parallel measurement in background thread."""
            try:
                # Prepare
                prep_results = api.parallel_prepare_measure(self.spectrometers, self.configs)
                if not all(prep_results.values()):
                    self.measurement_error.emit("Failed to prepare measurements")
                    return

                # Measure
                meas_results = api.parallel_measure(self.spectrometers, self.num_measurements)
                if not all(meas_results.values()):
                    self.measurement_error.emit("Failed to start measurements")
                    return

                # Poll and get data
                data_results = api.parallel_poll_and_get_data(
                    self.spectrometers,
                    timeout=10.0,
                    poll_interval=0.001,
                    diagnostics=self.diagnostics,
                )

                self.measurement_complete.emit(data_results)

            except Exception as e:
                self.measurement_error.emit(f"Measurement error: {str(e)}")

        def stop(self):
            """Stop the measurement thread."""
            self.running = False

    MeasurementThread.__module__ = api.__name__
    MeasurementThread.__qualname__ = "MeasurementThread"

    return {
        "_env_bool": _env_bool,
        "WavelengthTrackerWindow": WavelengthTrackerWindow,
        "ODHeatmapWindow": ODHeatmapWindow,
        "CollectionSettingsDialog": CollectionSettingsDialog,
        "MeasurementThread": MeasurementThread,
    }
