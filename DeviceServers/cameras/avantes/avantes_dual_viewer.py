"""
Avantes Dual Spectrometer Viewer - Standalone PyQt5 Application
================================================================

A standalone PyQt5 application for simultaneous/parallel readout and
visualization of two Avantes spectrometers.

Features:
- Independent connection to two Avantes spectrometers
- Real-time parallel measurement and display
- Live plotting with pyqtgraph
- Configurable integration time, averaging, and trigger modes
- Export data to CSV
- Hardware trigger support

Requirements:
- PyQt5
- pyqtgraph
- numpy
- msl-equipment
- Two Avantes AvaSpec spectrometers

Usage:
    python avantes_dual_viewer.py
"""

from sys import modules as _refactor_modules

import json
import sys
from pathlib import Path
import time
import logging
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QGroupBox, QGridLayout, QFileDialog, QMessageBox,
    QCheckBox, QSplitter, QMenu, QDialog, QDialogButtonBox, QFormLayout
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont

import pyqtgraph as pg

# Add project path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from DeviceServers.cameras.avantes.avantes_dual_viewer_methods_init_ui import _bind_avantes_dual_viewer_methods_init_ui
from DeviceServers.cameras.avantes.avantes_dual_viewer_methods_get_spectrometer_settings import _bind_avantes_dual_viewer_methods_get_spectrometer_settings
from DeviceServers.cameras.avantes.avantes_dual_viewer_methods_browse_save_folder import _bind_avantes_dual_viewer_methods_browse_save_folder

from msl.equipment import Backend, ConnectionRecord, EquipmentRecord
from DeviceServers.cameras.avantes.avantes_parallel import (
    parallel_prepare_measure,
    parallel_measure,
    parallel_poll_and_get_data
)
from DeviceServers.cameras.avantes.arduino_trigger_controller import ArduinoTriggerController
from DeviceServers.cameras.avantes.avantes_emulator import (
    ARDUINO_TRIGGER_HZ,
    EmulatedArduinoTriggerController,
    EmulatedAvantesSpectrometer,
    should_use_avantes_emulator,
)


DEFAULT_SETTINGS_JSON = Path(__file__).with_name("avantes_dual_viewer_settings.json")


class WavelengthTrackerWindow(QMainWindow):
    """Window for tracking OD at a specific wavelength over time."""

    def __init__(self, parent, wavelength):
        super().__init__(parent)
        self.parent_viewer = parent
        self.target_wavelength = wavelength
        self.od_history = []
        self.time_history = []
        self.start_time = time.time()  # Track time from window creation

        self.init_ui()

    def init_ui(self):
        """Initialize the tracker window UI."""
        self.setWindowTitle(f"OD Tracking at {self.target_wavelength:.1f} nm")
        self.setGeometry(150, 150, 800, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Current value display
        value_group = QGroupBox("Current Value")
        value_layout = QHBoxLayout()

        value_layout.addWidget(QLabel(f"Wavelength: {self.target_wavelength:.1f} nm"))
        value_layout.addStretch()

        value_layout.addWidget(QLabel("OD:"))
        self.od_value_label = QLabel("---")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.od_value_label.setFont(font)
        value_layout.addWidget(self.od_value_label)

        value_group.setLayout(value_layout)
        layout.addWidget(value_group)

        # Time series plot
        self.plot = pg.PlotWidget(title=f"OD Time Series at {self.target_wavelength:.1f} nm")
        self.plot.setLabel('left', 'OD (Absorbance)', units='AU')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(x=True, y=True)
        self.curve = self.plot.plot(pen=pg.mkPen('g', width=2), symbol='o', symbolSize=5)
        layout.addWidget(self.plot, stretch=1)

        # Control buttons
        btn_layout = QHBoxLayout()

        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.clicked.connect(self.clear_history)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()

        self.export_btn = QPushButton("Export Time Series")
        self.export_btn.clicked.connect(self.export_time_series)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

    def set_wavelength(self, wavelength):
        """Update tracked wavelength."""
        self.target_wavelength = wavelength
        self.setWindowTitle(f"OD Tracking at {wavelength:.1f} nm")
        self.plot.setTitle(f"OD Time Series at {wavelength:.1f} nm")
        # Don't clear history when changing wavelength, just reset time
        self.start_time = time.time()
        self.clear_history()

    def update_od_value(self, od_spectrum, wavelengths):
        """Update OD value and time series."""
        # Find closest wavelength index
        idx = np.argmin(np.abs(wavelengths - self.target_wavelength))
        od_value = od_spectrum[idx]

        # Update current value display
        self.od_value_label.setText(f"{od_value:.4f}")

        # Calculate elapsed time from tracker window start
        elapsed_time = time.time() - self.start_time

        # Add to history
        self.time_history.append(elapsed_time)
        self.od_history.append(od_value)

        # Update plot
        self.curve.setData(self.time_history, self.od_history)

    def clear_history(self):
        """Clear time series history and reset start time."""
        self.od_history = []
        self.time_history = []
        self.start_time = time.time()  # Reset start time
        self.curve.setData([], [])
        self.od_value_label.setText("---")

    def export_time_series(self):
        """Export time series data to CSV."""
        if len(self.time_history) == 0:
            QMessageBox.warning(self, "No Data", "No time series data to export")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Time Series",
            f"od_timeseries_{self.target_wavelength:.0f}nm.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            try:
                data = np.column_stack((self.time_history, self.od_history))
                np.savetxt(
                    filename,
                    data,
                    delimiter=',',
                    header=f'Time(s),OD@{self.target_wavelength:.1f}nm(AU)',
                    comments=''
                )
                QMessageBox.information(self, "Export Complete", f"Time series exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")


class ODHeatmapWindow(QMainWindow):
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

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

        self.plot = pg.PlotWidget(title="OD Time Map")
        self.plot.setLabel('left', 'Time', units='s')
        self.plot.setLabel('bottom', 'Wavelength', units='nm')
        self.plot.getAxis('left').enableAutoSIPrefix(False)
        self.plot.getAxis('bottom').enableAutoSIPrefix(False)
        self.plot.showGrid(x=True, y=True)

        self.mesh_item = pg.PColorMeshItem(colorMap=pg.colormap.get("viridis"))
        self.plot.addItem(self.mesh_item)

        self.wavelength_region = pg.LinearRegionItem([350, 450], orientation='vertical')
        self.time_region = pg.LinearRegionItem([0, 1], orientation='horizontal')
        self.wavelength_region.setZValue(10)
        self.time_region.setZValue(11)
        self.wavelength_region.sigRegionChanged.connect(self.update_profiles)
        self.time_region.sigRegionChanged.connect(self.update_profiles)
        self.plot.addItem(self.wavelength_region)
        self.plot.addItem(self.time_region)
        self.plot.setYRange(0, 1, padding=0)
        central_layout.addWidget(self.plot, stretch=3)

        profile_splitter = QSplitter(Qt.Horizontal)
        self.kinetics_plot = pg.PlotWidget(title="Kinetics: mean OD over wavelength band")
        self.kinetics_plot.setLabel('left', 'OD', units='AU')
        self.kinetics_plot.setLabel('bottom', 'Time', units='s')
        self.kinetics_plot.getAxis('bottom').enableAutoSIPrefix(False)
        self.kinetics_plot.showGrid(x=True, y=True)
        self.kinetics_curve = self.kinetics_plot.plot(pen=pg.mkPen('y', width=2), symbol='o', symbolSize=4)
        profile_splitter.addWidget(self.kinetics_plot)

        self.spectrum_plot = pg.PlotWidget(title="Spectrum: mean OD over time band")
        self.spectrum_plot.setLabel('left', 'OD', units='AU')
        self.spectrum_plot.setLabel('bottom', 'Wavelength', units='nm')
        self.spectrum_plot.getAxis('bottom').enableAutoSIPrefix(False)
        self.spectrum_plot.showGrid(x=True, y=True)
        self.spectrum_curve = self.spectrum_plot.plot(pen=pg.mkPen('c', width=2))
        profile_splitter.addWidget(self.spectrum_plot)
        central_layout.addWidget(profile_splitter, stretch=1)

    def set_heatmap(self, wavelengths, rows, times):
        """Render OD rows as wavelength x elapsed-time image."""
        if wavelengths is None or not rows:
            self.wavelengths = None
            self.times = None
            self.heatmap = None
            self.mesh_item.setVisible(False)
            self.kinetics_curve.setData([], [])
            self.spectrum_curve.setData([], [])
            self.plot.setYRange(0, 1, padding=0)
            self.plot.enableAutoRange(axis='x')
            return

        self.wavelengths = np.asarray(wavelengths, dtype=float)
        self.times = np.asarray(times, dtype=float)
        self.heatmap = np.nan_to_num(np.vstack(rows), nan=0.0, posinf=0.0, neginf=0.0)

        x_edges = self._edges_from_centers(self.wavelengths)
        y_edges = self._time_edges(self.times)
        x_grid, y_grid = np.meshgrid(x_edges, y_edges)

        self.mesh_item.setVisible(True)
        self.mesh_item.setData(x_grid, y_grid, self.heatmap)
        self.plot.setTitle(f"OD Time Map ({len(rows)} points)")
        x_min = float(x_edges[0])
        x_max = float(x_edges[-1])
        y_min = float(y_edges[0])
        y_max = max(float(y_edges[-1]), 1.0)
        self.plot.setXRange(x_min, x_max, padding=0)
        self.plot.setYRange(y_min, y_max, padding=0)

        self._initialize_regions(x_min, x_max, y_min, y_max)
        self.update_profiles()

    def _edges_from_centers(self, centers):
        """Build cell edges from monotonically increasing center coordinates."""
        centers = np.asarray(centers, dtype=float)
        if len(centers) == 1:
            return np.array([centers[0] - 0.5, centers[0] + 0.5])
        mids = (centers[:-1] + centers[1:]) / 2.0
        first = centers[0] - (mids[0] - centers[0])
        last = centers[-1] + (centers[-1] - mids[-1])
        return np.concatenate(([first], mids, [last]))

    def _time_edges(self, times):
        """Build time cell edges while keeping first edge at zero when possible."""
        times = np.asarray(times, dtype=float)
        if len(times) == 1:
            width = max(times[0], 1.0)
            return np.array([max(0.0, times[0] - width / 2.0), times[0] + width / 2.0])
        edges = self._edges_from_centers(times)
        edges[0] = max(0.0, edges[0])
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

        if np.any(wl_mask):
            kinetics = np.nanmean(self.heatmap[:, wl_mask], axis=1)
            self.kinetics_curve.setData(self.times, kinetics)
            self.kinetics_plot.setTitle(
                f"Kinetics: mean OD {min(wl_min, wl_max):.1f}-{max(wl_min, wl_max):.1f} nm"
            )
        else:
            self.kinetics_curve.setData([], [])

        if np.any(time_mask):
            spectrum = np.nanmean(self.heatmap[time_mask, :], axis=0)
            self.spectrum_curve.setData(self.wavelengths, spectrum)
            self.spectrum_plot.setTitle(
                f"Spectrum: mean OD {min(time_min, time_max):.1f}-{max(time_min, time_max):.1f} s"
            )
        else:
            self.spectrum_curve.setData([], [])

    def closeEvent(self, event):
        """Allow Show button to recreate window after user closes it."""
        self.parent_viewer.od_heatmap_window = None
        event.accept()


class CollectionSettingsDialog(QDialog):
    """Dialog for Arduino frequency and lamp-management settings."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_viewer = parent
        self.setWindowTitle("Collection Settings")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.frequency_spin = QSpinBox()
        self.frequency_spin.setRange(1, 100)
        self.frequency_spin.setValue(int(round(parent.arduino_frequency_hz)))
        form.addRow("Arduino frequency (Hz):", self.frequency_spin)

        self.warmup_spin = QDoubleSpinBox()
        self.warmup_spin.setRange(0.0, 3600.0)
        self.warmup_spin.setDecimals(1)
        self.warmup_spin.setSingleStep(10.0)
        self.warmup_spin.setValue(parent.lamp_warmup_seconds)
        form.addRow("Lamp warmup lead (s):", self.warmup_spin)

        self.auto_lamp_check = QCheckBox("Auto-control lamp during data collection")
        self.auto_lamp_check.setChecked(parent.auto_lamp_management_enabled)
        form.addRow("", self.auto_lamp_check)

        self.lamp_off_between_check = QCheckBox("Turn lamp off between long-interval points")
        self.lamp_off_between_check.setChecked(parent.lamp_off_between_points_enabled)
        form.addRow("", self.lamp_off_between_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MeasurementThread(QThread):
    """Background thread for parallel spectrometer measurements."""

    measurement_complete = pyqtSignal(dict)  # Signal with results
    measurement_error = pyqtSignal(str)  # Signal with error message

    def __init__(self, spectrometers, configs, num_measurements=1):
        super().__init__()
        self.spectrometers = spectrometers
        self.configs = configs
        self.num_measurements = num_measurements
        self.running = True

    def run(self):
        """Execute parallel measurement in background thread."""
        try:
            # Prepare
            prep_results = parallel_prepare_measure(self.spectrometers, self.configs)
            if not all(prep_results.values()):
                self.measurement_error.emit("Failed to prepare measurements")
                return

            # Measure
            meas_results = parallel_measure(self.spectrometers, self.num_measurements)
            if not all(meas_results.values()):
                self.measurement_error.emit("Failed to start measurements")
                return

            # Poll and get data
            data_results = parallel_poll_and_get_data(
                self.spectrometers,
                timeout=10.0,
                poll_interval=0.001
            )

            self.measurement_complete.emit(data_results)

        except Exception as e:
            self.measurement_error.emit(f"Measurement error: {str(e)}")

    def stop(self):
        """Stop the measurement thread."""
        self.running = False


class SpectrometerWidget(QGroupBox):
    """Widget for controlling a single spectrometer."""

    def __init__(self, spec_id: int, parent=None, emulate_hardware: bool = False):
        super().__init__(f"Spectrometer {spec_id}", parent)
        self.spec_id = spec_id
        self.emulate_hardware = emulate_hardware
        self.spec = None
        self.wavelengths = None
        self.last_data = None

        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        layout = QGridLayout()

        # Serial number
        layout.addWidget(QLabel("Serial Number:"), 0, 0)
        self.serial_input = QLineEdit()
        # Set default serial numbers based on spec_id
        default_serials = {1: "1810225U1", 2: "1810226U1"}
        self.serial_input.setText(default_serials.get(self.spec_id, ""))
        self.serial_input.setPlaceholderText("e.g., 1810225U1")
        layout.addWidget(self.serial_input, 0, 1)

        # Connect button
        self.connect_btn = QPushButton("Connect Emulator" if self.emulate_hardware else "Connect")
        self.connect_btn.clicked.connect(self.connect_spectrometer)
        layout.addWidget(self.connect_btn, 0, 2)

        # Status
        layout.addWidget(QLabel("Status:"), 1, 0)
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.status_label, 1, 1, 1, 2)

        # Integration time
        layout.addWidget(QLabel("Integration (ms):"), 2, 0)
        self.integration_spin = QDoubleSpinBox()
        self.integration_spin.setRange(0.1, 10000)
        self.integration_spin.setValue(1.0)  # Default 1ms
        self.integration_spin.setSingleStep(1.0)
        self.integration_spin.setDecimals(1)
        self.integration_spin.valueChanged.connect(self.on_settings_changed)
        layout.addWidget(self.integration_spin, 2, 1)

        # Number of averages
        layout.addWidget(QLabel("Averages:"), 3, 0)
        self.averages_spin = QSpinBox()
        self.averages_spin.setRange(1, 100)
        self.averages_spin.setValue(1)
        self.averages_spin.valueChanged.connect(self.on_settings_changed)
        layout.addWidget(self.averages_spin, 3, 1)

        # Trigger mode
        layout.addWidget(QLabel("Trigger Mode:"), 4, 0)
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["Software", "Hardware", "Synchronous"])
        self.trigger_combo.setCurrentIndex(1)  # Default to Hardware for Arduino sync
        self.trigger_combo.currentIndexChanged.connect(self.on_settings_changed)
        layout.addWidget(self.trigger_combo, 4, 1)

        # Info labels
        layout.addWidget(QLabel("Pixels:"), 5, 0)
        self.pixels_label = QLabel("---")
        layout.addWidget(self.pixels_label, 5, 1)

        layout.addWidget(QLabel("λ range (nm):"), 6, 0)
        self.wavelength_label = QLabel("---")
        layout.addWidget(self.wavelength_label, 6, 1)

        # Statistics
        layout.addWidget(QLabel("Mean:"), 7, 0)
        self.mean_label = QLabel("---")
        layout.addWidget(self.mean_label, 7, 1)

        layout.addWidget(QLabel("Max:"), 8, 0)
        self.max_label = QLabel("---")
        layout.addWidget(self.max_label, 8, 1)

        self.setLayout(layout)

    def connect_spectrometer(self):
        """Connect to the Avantes spectrometer."""
        serial = self.serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "Error", "Please enter serial number")
            return

        try:
            if self.emulate_hardware:
                self.spec = EmulatedAvantesSpectrometer(serial=serial, channel_index=self.spec_id - 1)
            else:
                dll_path = Path(__file__).parent / "drivers" / "avaspecx64.dll"

                record = EquipmentRecord(
                    manufacturer="Avantes",
                    model="AvaSpec-2048L",
                    serial=serial,
                    connection=ConnectionRecord(
                        address=f"SDK::{dll_path}"
                    ),
                )

                self.spec = record.connect()
            self.spec.use_high_res_adc(True)

            # Get wavelength calibration
            self.wavelengths = self.spec.get_lambda()
            num_pixels = self.spec.get_num_pixels()

            mode = "EMULATED" if self.emulate_hardware else "CONNECTED"
            logging.info(f"Spec {self.spec_id} {mode}: Serial={serial}, Pixels={num_pixels}, λ={self.wavelengths[0]:.1f}-{self.wavelengths[-1]:.1f} nm")

            # Update UI
            self.status_label.setText("Emulated" if self.emulate_hardware else "Connected")
            self.status_label.setStyleSheet("color: purple; font-weight: bold;" if self.emulate_hardware else "color: green; font-weight: bold;")
            self.pixels_label.setText(str(num_pixels))
            self.wavelength_label.setText(f"{self.wavelengths[0]:.1f} - {self.wavelengths[-1]:.1f}")

            self.connect_btn.setText("Disconnect")
            self.connect_btn.clicked.disconnect()
            self.connect_btn.clicked.connect(self.disconnect_spectrometer)
            self.serial_input.setEnabled(False)

        except Exception as e:
            logging.error(f"Spec {self.spec_id}: Connection failed - {str(e)}")
            QMessageBox.critical(self, "Connection Error", f"Failed to connect:\n{str(e)}")

    def disconnect_spectrometer(self):
        """Disconnect from the spectrometer."""
        if self.spec:
            try:
                self.spec.disconnect()
            except:
                pass
            self.spec = None
            self.wavelengths = None

            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.pixels_label.setText("---")
            self.wavelength_label.setText("---")
            self.mean_label.setText("---")
            self.max_label.setText("---")

            self.connect_btn.setText("Connect")
            if self.emulate_hardware:
                self.connect_btn.setText("Connect Emulator")
            self.connect_btn.clicked.disconnect()
            self.connect_btn.clicked.connect(self.connect_spectrometer)
            self.serial_input.setEnabled(True)

    def get_measurement_config(self):
        """Create measurement configuration from current settings."""
        if not self.spec:
            return None

        try:
            cfg = self.spec.MeasConfigType()
            cfg.m_StopPixel = self.spec.get_num_pixels() - 1
            cfg.m_IntegrationTime = float(self.integration_spin.value())
            cfg.m_NrAverages = self.averages_spin.value()

            trigger = self.spec.TriggerType()
            trigger_mode = self.trigger_combo.currentIndex()
            trigger.m_Mode = trigger_mode
            trigger.m_Source = 0
            trigger.m_SourceType = 0
            cfg.m_Trigger = trigger

            return cfg
        except Exception as e:
            logging.error(f"Spec {self.spec_id}: Failed to create config - {str(e)}")
            # Mark as disconnected
            self.spec = None
            self.status_label.setText("Connection Lost")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            raise

    def on_settings_changed(self):
        """Called when integration time, averages, or trigger mode changes."""
        # Settings will be applied on next measurement
        # No need to stop/restart - new config used automatically
        parent = self.parent()
        if parent and hasattr(parent, "update_live_preview_interval"):
            parent.update_live_preview_interval()
        pass

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

    def update_statistics(self, data: np.ndarray):
        """Update statistics display."""
        if data is not None and len(data) > 0:
            self.last_data = data
            self.mean_label.setText(f"{np.mean(data):.1f}")
            self.max_label.setText(f"{np.max(data):.1f}")


class AvantesDualViewer(QMainWindow):
    """Main application window for dual spectrometer viewing."""

    def __init__(self):
        super().__init__()
        self.spec1_widget = None
        self.spec2_widget = None
        self.measurement_thread = None
        self.continuous_mode = False
        self.data_collection_active = False
        self.measuring_reference = False
        self.measuring_background = False
        self.reference_measurements = []
        self.background_measurements = []
        self.collection_data = []
        self.collection_point_index = 0
        self.collection_start_time = None
        self.collection_point_start_time = None
        self.collection_file_path = None
        self.collection_next_due_time = None
        self.lamp_warmup_seconds = 120.0
        self.arduino_frequency_hz = ARDUINO_TRIGGER_HZ
        self.auto_lamp_management_enabled = True
        self.lamp_off_between_points_enabled = True
        self.od_heatmap_rows = []
        self.od_heatmap_times = []
        self.od_heatmap_wavelengths = None
        self.od_heatmap_window = None
        self.current_measurement_role = None
        self.settings_json_path = DEFAULT_SETTINGS_JSON
        self._measurement_count = 0
        self.wavelength_tracker_window = None
        self.emulate_hardware = should_use_avantes_emulator()

        # Arduino controller
        if self.emulate_hardware:
            self.arduino = EmulatedArduinoTriggerController()
        else:
            self.arduino = ArduinoTriggerController(ip="10.20.30.47")

        # Timers
        self.continuous_timer = QTimer()
        self.continuous_timer.timeout.connect(self.continuous_measurement)
        self.collection_timer = QTimer()
        self.collection_timer.setSingleShot(True)
        self.collection_timer.timeout.connect(self.collect_data_point)
        self.lamp_warmup_timer = QTimer()
        self.lamp_warmup_timer.setSingleShot(True)
        self.lamp_warmup_timer.timeout.connect(self.prepare_lamp_for_collection)
        self.collection_countdown_timer = QTimer()
        self.collection_countdown_timer.setInterval(1000)
        self.collection_countdown_timer.timeout.connect(self.update_collection_countdown_label)

        # Setup logging
        self.setup_logging()

        self.init_ui()

        # Auto-connect both spectrometers after UI is ready
        QTimer.singleShot(500, self.auto_connect_spectrometers)

    _avantes_dual_viewer_methods_init_ui = _bind_avantes_dual_viewer_methods_init_ui(_refactor_modules[__name__])
    init_ui = _avantes_dual_viewer_methods_init_ui["init_ui"]

    create_control_panel = _avantes_dual_viewer_methods_init_ui["create_control_panel"]

    create_menu_bar = _avantes_dual_viewer_methods_init_ui["create_menu_bar"]

    create_settings_menu = _avantes_dual_viewer_methods_init_ui["create_settings_menu"]

    populate_settings_menu = _avantes_dual_viewer_methods_init_ui["populate_settings_menu"]

    update_od_axis_limits = _avantes_dual_viewer_methods_init_ui["update_od_axis_limits"]

    link_detector_averages = _avantes_dual_viewer_methods_init_ui["link_detector_averages"]

    get_live_preview_interval_ms = _avantes_dual_viewer_methods_init_ui["get_live_preview_interval_ms"]

    update_live_preview_interval = _avantes_dual_viewer_methods_init_ui["update_live_preview_interval"]

    get_collection_min_rate_s = _avantes_dual_viewer_methods_init_ui["get_collection_min_rate_s"]

    get_detector_average_count = _avantes_dual_viewer_methods_init_ui["get_detector_average_count"]

    validate_collection_rate = _avantes_dual_viewer_methods_init_ui["validate_collection_rate"]

    single_measurement = _avantes_dual_viewer_methods_init_ui["single_measurement"]

    continuous_measurement = _avantes_dual_viewer_methods_init_ui["continuous_measurement"]

    get_arduino_state = _avantes_dual_viewer_methods_init_ui["get_arduino_state"]

    set_arduino_frequency_hz = _avantes_dual_viewer_methods_init_ui["set_arduino_frequency_hz"]

    sync_arduino_frequency_from_controller = _avantes_dual_viewer_methods_init_ui["sync_arduino_frequency_from_controller"]

    open_collection_settings = _avantes_dual_viewer_methods_init_ui["open_collection_settings"]

    get_settings_dict = _avantes_dual_viewer_methods_init_ui["get_settings_dict"]
    del _avantes_dual_viewer_methods_init_ui

    _avantes_dual_viewer_methods_get_spectrometer_settings = _bind_avantes_dual_viewer_methods_get_spectrometer_settings(_refactor_modules[__name__])
    get_spectrometer_settings = _avantes_dual_viewer_methods_get_spectrometer_settings["get_spectrometer_settings"]

    apply_settings_dict = _avantes_dual_viewer_methods_get_spectrometer_settings["apply_settings_dict"]

    apply_spectrometer_settings = _avantes_dual_viewer_methods_get_spectrometer_settings["apply_spectrometer_settings"]

    load_settings_json = _avantes_dual_viewer_methods_get_spectrometer_settings["load_settings_json"]

    load_settings_from_file = _avantes_dual_viewer_methods_get_spectrometer_settings["load_settings_from_file"]

    save_settings_json_as = _avantes_dual_viewer_methods_get_spectrometer_settings["save_settings_json_as"]

    update_settings_json = _avantes_dual_viewer_methods_get_spectrometer_settings["update_settings_json"]

    write_settings_json = _avantes_dual_viewer_methods_get_spectrometer_settings["write_settings_json"]

    is_lamp_enabled = _avantes_dual_viewer_methods_get_spectrometer_settings["is_lamp_enabled"]

    set_lamp_on = _avantes_dual_viewer_methods_get_spectrometer_settings["set_lamp_on"]

    set_lamp_off = _avantes_dual_viewer_methods_get_spectrometer_settings["set_lamp_off"]

    set_lamp_and_avantes = _avantes_dual_viewer_methods_get_spectrometer_settings["set_lamp_and_avantes"]

    set_avantes_only = _avantes_dual_viewer_methods_get_spectrometer_settings["set_avantes_only"]

    set_arduino_off = _avantes_dual_viewer_methods_get_spectrometer_settings["set_arduino_off"]

    toggle_continuous_readout = _avantes_dual_viewer_methods_get_spectrometer_settings["toggle_continuous_readout"]

    stop_live_preview = _avantes_dual_viewer_methods_get_spectrometer_settings["stop_live_preview"]

    stop_measurement = _avantes_dual_viewer_methods_get_spectrometer_settings["stop_measurement"]

    measure_reference = _avantes_dual_viewer_methods_get_spectrometer_settings["measure_reference"]

    measure_background = _avantes_dual_viewer_methods_get_spectrometer_settings["measure_background"]

    measure_reference_complete = _avantes_dual_viewer_methods_get_spectrometer_settings["measure_reference_complete"]

    measure_background_complete = _avantes_dual_viewer_methods_get_spectrometer_settings["measure_background_complete"]

    toggle_data_collection = _avantes_dual_viewer_methods_get_spectrometer_settings["toggle_data_collection"]

    collect_data_point = _avantes_dual_viewer_methods_get_spectrometer_settings["collect_data_point"]

    schedule_next_collection_point = _avantes_dual_viewer_methods_get_spectrometer_settings["schedule_next_collection_point"]

    on_collection_rate_changed = _avantes_dual_viewer_methods_get_spectrometer_settings["on_collection_rate_changed"]

    schedule_collection_due_time = _avantes_dual_viewer_methods_get_spectrometer_settings["schedule_collection_due_time"]

    prepare_lamp_for_collection = _avantes_dual_viewer_methods_get_spectrometer_settings["prepare_lamp_for_collection"]

    format_seconds_for_countdown = _avantes_dual_viewer_methods_get_spectrometer_settings["format_seconds_for_countdown"]

    update_collection_countdown_label = _avantes_dual_viewer_methods_get_spectrometer_settings["update_collection_countdown_label"]
    del _avantes_dual_viewer_methods_get_spectrometer_settings

    _avantes_dual_viewer_methods_browse_save_folder = _bind_avantes_dual_viewer_methods_browse_save_folder(_refactor_modules[__name__])
    browse_save_folder = _avantes_dual_viewer_methods_browse_save_folder["browse_save_folder"]

    update_analysis_buttons = _avantes_dual_viewer_methods_browse_save_folder["update_analysis_buttons"]

    reset_od_heatmap = _avantes_dual_viewer_methods_browse_save_folder["reset_od_heatmap"]

    update_od_heatmap = _avantes_dual_viewer_methods_browse_save_folder["update_od_heatmap"]

    render_od_heatmap = _avantes_dual_viewer_methods_browse_save_folder["render_od_heatmap"]

    show_od_heatmap_window = _avantes_dual_viewer_methods_browse_save_folder["show_od_heatmap_window"]

    get_export_base_path = _avantes_dual_viewer_methods_browse_save_folder["get_export_base_path"]

    open_wavelength_tracker = _avantes_dual_viewer_methods_browse_save_folder["open_wavelength_tracker"]

    on_measurement_complete = _avantes_dual_viewer_methods_browse_save_folder["on_measurement_complete"]

    on_measurement_error = _avantes_dual_viewer_methods_browse_save_folder["on_measurement_error"]

    on_measurement_finished = _avantes_dual_viewer_methods_browse_save_folder["on_measurement_finished"]

    save_collection_point = _avantes_dual_viewer_methods_browse_save_folder["save_collection_point"]

    set_controls_enabled = _avantes_dual_viewer_methods_browse_save_folder["set_controls_enabled"]

    export_data = _avantes_dual_viewer_methods_browse_save_folder["export_data"]

    calculate_optical_density = _avantes_dual_viewer_methods_browse_save_folder["calculate_optical_density"]

    clear_plots = _avantes_dual_viewer_methods_browse_save_folder["clear_plots"]

    setup_logging = _avantes_dual_viewer_methods_browse_save_folder["setup_logging"]


    auto_connect_spectrometers = _avantes_dual_viewer_methods_browse_save_folder["auto_connect_spectrometers"]

    auto_connect_spec2 = _avantes_dual_viewer_methods_browse_save_folder["auto_connect_spec2"]

    auto_start_continuous = _avantes_dual_viewer_methods_browse_save_folder["auto_start_continuous"]

    closeEvent = _avantes_dual_viewer_methods_browse_save_folder["closeEvent"]
    del _avantes_dual_viewer_methods_browse_save_folder


def main():
    """Main entry point."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    # Create and show main window
    window = AvantesDualViewer()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
