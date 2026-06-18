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

import json
import os
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
    QCheckBox, QSplitter, QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont

import pyqtgraph as pg

try:
    from msl.equipment import Connection
except ImportError:
    from msl.equipment import ConnectionRecord, EquipmentRecord
    msl_avantes = None
    MSL_EQUIPMENT_API = "legacy"
else:
    try:
        from msl.equipment.resources import avantes as msl_avantes
    except ImportError as exc:
        raise ImportError(
            "Modern msl-equipment requires msl-equipment-resources for Avantes support"
        ) from exc

    MSL_EQUIPMENT_API = "modern"
from avantes_parallel import (
    parallel_prepare_measure,
    parallel_measure,
    parallel_poll_and_get_data
)
from arduino_trigger_controller import ArduinoTriggerController
from avantes_emulator import (
    ARDUINO_TRIGGER_HZ,
    EmulatedArduinoTriggerController,
    EmulatedAvantesSpectrometer,
    should_use_avantes_emulator,
)


DEFAULT_SETTINGS_JSON = Path(__file__).with_name("avantes_dual_viewer_settings.json")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


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

    def closeEvent(self, event):
        """Keep the parent Show/Hide button in sync."""
        self.parent_viewer.od_heatmap_window = None
        if hasattr(self.parent_viewer, "show_od_map_btn"):
            self.parent_viewer.show_od_map_btn.setText("Show")
        super().closeEvent(event)

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

        self.min_off_spin = QDoubleSpinBox()
        self.min_off_spin.setRange(0.0, 3600.0)
        self.min_off_spin.setDecimals(1)
        self.min_off_spin.setSingleStep(10.0)
        self.min_off_spin.setValue(parent.lamp_min_off_seconds)
        form.addRow("Minimum lamp-off gap (s):", self.min_off_spin)

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
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

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

                if MSL_EQUIPMENT_API == "modern":
                    connection = Connection(
                        f"SDK::{dll_path}",
                        manufacturer="Avantes",
                        model="AvaSpec-2048L",
                        serial=serial,
                    )
                    self.spec = self._connect_with_discovery_retry(connection, serial)
                else:
                    record = EquipmentRecord(
                        manufacturer="Avantes",
                        model="AvaSpec-2048L",
                        serial=serial,
                        connection=ConnectionRecord(
                            address=f"SDK::{dll_path}"
                        ),
                    )
                    self.spec = self._connect_with_discovery_retry(record, serial)

            self.enable_high_res_adc_if_supported()

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

    def _connect_with_discovery_retry(self, connector, serial, attempts=6, delay_s=2.0):
        """Connect to an Ethernet AvaSpec, retrying transient discovery misses.

        ``AVS_Init`` runs a fresh Ethernet discovery scan on every call. The first
        scan after process start (or right after the network interface comes up)
        often returns zero devices, which msl-equipment raises as "No Avantes
        devices were found". Because each spectrometer is connected with its own
        ``record.connect()`` call, whichever unit is connected first loses this
        race. Retrying a few times lets a cold scan settle so both units connect
        regardless of order.
        """
        transient_errors = (
            "Cannot activate. No devices found",
            "No Avantes devices were found",
            "Did not find the Avantes serial",
        )
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return connector.connect()
            except Exception as exc:
                if not any(token in str(exc) for token in transient_errors):
                    raise
                last_error = exc
                logging.warning(
                    f"Spec {self.spec_id}: '{serial}' not discovered yet "
                    f"(attempt {attempt}/{attempts}); waiting {delay_s:.0f}s for "
                    f"Ethernet discovery to populate..."
                )
                if attempt < attempts:
                    time.sleep(delay_s)
        raise last_error

    def enable_high_res_adc_if_supported(self):
        """Enable high-resolution ADC only when this SDK exposes it."""
        method = getattr(self.spec, "use_high_res_adc", None)
        if not callable(method):
            logging.warning(f"Spec {self.spec_id}: High-resolution ADC method not available; continuing")
            return

        try:
            method(True)
        except AttributeError as exc:
            logging.warning(f"Spec {self.spec_id}: High-resolution ADC not supported by this SDK: {exc}")
        except Exception as exc:
            logging.warning(f"Spec {self.spec_id}: Could not enable high-resolution ADC: {exc}")

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
            cfg = self.create_meas_config()
            cfg.m_StopPixel = self.spec.get_num_pixels() - 1
            cfg.m_IntegrationTime = float(self.integration_spin.value())
            cfg.m_NrAverages = self.averages_spin.value()

            trigger = self.create_trigger_config()
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

    def create_meas_config(self):
        if msl_avantes is not None and not self.emulate_hardware:
            return msl_avantes.MeasConfigType()
        return self.spec.MeasConfigType()

    def create_trigger_config(self):
        if msl_avantes is not None and not self.emulate_hardware:
            return msl_avantes.TriggerType()
        return self.spec.TriggerType()

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
        self.reference_target_blocks = 1
        self.background_target_blocks = 1
        self.pending_ref_bg_role = None
        self.collection_data = []
        self.collection_point_index = 0
        self.collection_start_time = None
        self.collection_point_start_time = None
        self.collection_file_path = None
        self.collection_next_due_time = None
        self.lamp_warmup_seconds = 120.0
        self.lamp_min_off_seconds = 60.0
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
        self.demo_kinetics_enabled = self.emulate_hardware and _env_bool("AVANTES_DEMO_KINETICS", False)
        self.demo_kinetics_duration_s = float(os.environ.get("AVANTES_DEMO_DURATION_S", "40"))
        self.demo_kinetics_max_od = float(os.environ.get("AVANTES_DEMO_MAX_OD", "0.95"))

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

    def init_ui(self):
        """Initialize the main UI."""
        title = "Avantes Dual Spectrometer Viewer"
        if self.emulate_hardware:
            title += " [EMULATOR]"
        if self.demo_kinetics_enabled:
            title += " [DEMO KINETICS]"
        self.setWindowTitle(title)
        self.setGeometry(80, 80, 1180, 820)
        self.create_menu_bar()

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # Splitter for spectrometer controls
        controls_splitter = QSplitter(Qt.Horizontal)

        # Spectrometer 1 controls
        self.spec1_widget = SpectrometerWidget(1, emulate_hardware=self.emulate_hardware)
        controls_splitter.addWidget(self.spec1_widget)

        # Spectrometer 2 controls
        self.spec2_widget = SpectrometerWidget(2, emulate_hardware=self.emulate_hardware)
        controls_splitter.addWidget(self.spec2_widget)
        controls_splitter.setSizes([590, 590])
        self.link_detector_averages()

        main_layout.addWidget(controls_splitter)

        # Plot layout: Left side (Ch1 + Ch2), Right side (OD)
        plot_main_splitter = QSplitter(Qt.Horizontal)

        # Left side: Channel spectra (vertical split)
        left_plot_splitter = QSplitter(Qt.Vertical)
        left_plot_splitter.setMinimumWidth(260)

        # Ch1 plot (top left)
        self.plot1 = pg.PlotWidget(title="Channel 1 Spectrum")
        self.plot1.setLabel('left', 'Intensity', units='counts')
        self.plot1.setLabel('bottom', 'Wavelength', units='nm')
        self.plot1.showGrid(x=True, y=True)
        self.plot1.setMinimumWidth(260)
        self.curve1 = self.plot1.plot(pen=pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve1 = self.plot1.plot(pen=pg.mkPen('m', width=2, style=Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve1 = self.plot1.plot(pen=pg.mkPen('b', width=2, style=Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot1)

        # Ch2 plot (bottom left)
        self.plot2 = pg.PlotWidget(title="Channel 2 Spectrum")
        self.plot2.setLabel('left', 'Intensity', units='counts')
        self.plot2.setLabel('bottom', 'Wavelength', units='nm')
        self.plot2.showGrid(x=True, y=True)
        self.plot2.setMinimumWidth(260)
        self.curve2 = self.plot2.plot(pen=pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve2 = self.plot2.plot(pen=pg.mkPen('m', width=2, style=Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve2 = self.plot2.plot(pen=pg.mkPen('b', width=2, style=Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot2)

        plot_main_splitter.addWidget(left_plot_splitter)

        # Right side: OD spectrum plot with controls
        od_widget = QWidget()
        od_widget.setMinimumWidth(520)
        od_layout = QVBoxLayout(od_widget)
        od_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_od = pg.PlotWidget(title="Optical Density (OD) Spectrum")
        self.plot_od.setLabel('left', 'OD (Absorbance)', units='AU')
        self.plot_od.setLabel('bottom', 'Wavelength', units='nm')
        self.plot_od.getAxis('bottom').enableAutoSIPrefix(False)
        self.plot_od.showGrid(x=True, y=True)
        self.curve_od = self.plot_od.plot(pen=pg.mkPen('w', width=2))  # White for OD
        od_layout.addWidget(self.plot_od)

        # OD plot axis controls
        od_controls = QGroupBox("OD Plot Limits")
        od_controls_layout = QHBoxLayout()

        # X-axis (Wavelength) controls
        x_group = QGroupBox("Wavelength (nm)")
        x_layout = QHBoxLayout()

        self.od_x_auto_check = QCheckBox("Auto")
        self.od_x_auto_check.setChecked(True)
        self.od_x_auto_check.stateChanged.connect(self.update_od_axis_limits)
        x_layout.addWidget(self.od_x_auto_check)

        x_layout.addWidget(QLabel("Min:"))
        self.od_x_min_spin = QDoubleSpinBox()
        self.od_x_min_spin.setRange(0, 2000)
        self.od_x_min_spin.setValue(200)
        self.od_x_min_spin.setSingleStep(10)
        self.od_x_min_spin.setEnabled(False)
        self.od_x_min_spin.valueChanged.connect(self.update_od_axis_limits)
        x_layout.addWidget(self.od_x_min_spin)

        x_layout.addWidget(QLabel("Max:"))
        self.od_x_max_spin = QDoubleSpinBox()
        self.od_x_max_spin.setRange(0, 2000)
        self.od_x_max_spin.setValue(1100)
        self.od_x_max_spin.setSingleStep(10)
        self.od_x_max_spin.setEnabled(False)
        self.od_x_max_spin.valueChanged.connect(self.update_od_axis_limits)
        x_layout.addWidget(self.od_x_max_spin)

        x_group.setLayout(x_layout)
        od_controls_layout.addWidget(x_group)

        # Y-axis (OD) controls
        y_group = QGroupBox("OD (AU)")
        y_layout = QHBoxLayout()

        self.od_y_auto_check = QCheckBox("Auto")
        self.od_y_auto_check.setChecked(True)
        self.od_y_auto_check.stateChanged.connect(self.update_od_axis_limits)
        y_layout.addWidget(self.od_y_auto_check)

        y_layout.addWidget(QLabel("Min:"))
        self.od_y_min_spin = QDoubleSpinBox()
        self.od_y_min_spin.setRange(-5.0, 5.0)
        self.od_y_min_spin.setValue(-0.5)
        self.od_y_min_spin.setSingleStep(0.1)
        self.od_y_min_spin.setDecimals(2)
        self.od_y_min_spin.setEnabled(False)
        self.od_y_min_spin.valueChanged.connect(self.update_od_axis_limits)
        y_layout.addWidget(self.od_y_min_spin)

        y_layout.addWidget(QLabel("Max:"))
        self.od_y_max_spin = QDoubleSpinBox()
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

        plot_main_splitter.setStretchFactor(0, 1)
        plot_main_splitter.setStretchFactor(1, 2)
        plot_main_splitter.setSizes([390, 760])

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

    def create_control_panel(self) -> QGroupBox:
        """Create the main control panel."""
        panel = QGroupBox("Measurement Controls")
        layout = QHBoxLayout()

        # Arduino control section
        arduino_group = QGroupBox("Arduino Control")
        arduino_layout = QVBoxLayout()

        arduino_btn_layout = QHBoxLayout()
        self.lamp_on_btn = QPushButton("Lamp ON")
        self.lamp_on_btn.clicked.connect(lambda: self.set_lamp_on())
        arduino_btn_layout.addWidget(self.lamp_on_btn)

        self.lamp_off_btn = QPushButton("Lamp OFF")
        self.lamp_off_btn.clicked.connect(lambda: self.set_lamp_off())
        arduino_btn_layout.addWidget(self.lamp_off_btn)

        self.arduino_advanced_btn = QPushButton("Advanced")
        advanced_menu = QMenu(self)
        advanced_menu.addAction("Collection Settings...", self.open_collection_settings)
        advanced_menu.addSeparator()
        advanced_menu.addAction("Lamp + Avantes", self.set_lamp_and_avantes)
        advanced_menu.addAction("Avantes Only", self.set_avantes_only)
        advanced_menu.addAction("Arduino OFF", self.set_arduino_off)
        self.arduino_advanced_btn.setMenu(advanced_menu)
        arduino_btn_layout.addWidget(self.arduino_advanced_btn)

        arduino_layout.addLayout(arduino_btn_layout)

        self.arduino_status_label = QLabel("Status: Unknown")
        arduino_layout.addWidget(self.arduino_status_label)

        if self.emulate_hardware:
            emulator_label = QLabel("Mode: Emulator")
            emulator_label.setStyleSheet("color: purple; font-weight: bold;")
            arduino_layout.addWidget(emulator_label)

        arduino_group.setLayout(arduino_layout)
        layout.addWidget(arduino_group)

        # Reference and Background measurement section
        ref_bg_group = QGroupBox("Reference & Background")
        ref_bg_layout = QVBoxLayout()

        # Block averaging for reference/background. Avantes hardware averages
        # are controlled in the spectrometer panels.
        avg_layout = QHBoxLayout()
        avg_layout.addWidget(QLabel("Blocks:"))
        self.ref_blocks_spin = QSpinBox()
        self.ref_blocks_spin.setRange(1, 100)
        self.ref_blocks_spin.setValue(3)
        self.ref_blocks_spin.setToolTip("Number of spectra, already averaged by Avantes, to average in Python")
        avg_layout.addWidget(self.ref_blocks_spin)
        ref_bg_layout.addLayout(avg_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.measure_ref_btn = QPushButton("Measure Reference")
        self.measure_ref_btn.clicked.connect(self.measure_reference)
        self.measure_ref_btn.setToolTip("Measure reference with lamp ON")
        btn_layout.addWidget(self.measure_ref_btn)

        self.measure_bg_btn = QPushButton("Measure Background")
        self.measure_bg_btn.clicked.connect(self.measure_background)
        self.measure_bg_btn.setToolTip("Measure background with lamp OFF")
        btn_layout.addWidget(self.measure_bg_btn)

        self.zero_reference_btn = QPushButton("Set Zero")
        self.zero_reference_btn.clicked.connect(self.set_zero_baseline_from_current)
        self.zero_reference_btn.setEnabled(False)
        self.zero_reference_btn.setToolTip("Store current no-sample OD as a zero baseline spectrum")
        btn_layout.addWidget(self.zero_reference_btn)

        self.stop_measure_btn = QPushButton("Stop Measurement")
        self.stop_measure_btn.clicked.connect(self.stop_measurement)
        self.stop_measure_btn.setEnabled(False)
        self.stop_measure_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_measure_btn.setToolTip("Abort current reference/background measurement")
        btn_layout.addWidget(self.stop_measure_btn)

        ref_bg_layout.addLayout(btn_layout)
        ref_bg_group.setLayout(ref_bg_layout)
        layout.addWidget(ref_bg_group)

        # Data collection section
        data_group = QGroupBox("Data Collection")
        data_layout = QGridLayout()

        data_layout.addWidget(QLabel("Rate (s):"), 0, 0)
        self.collection_rate_spin = QDoubleSpinBox()
        self.collection_rate_spin.setRange(0.1, 86400.0)
        self.collection_rate_spin.setValue(1.0)
        self.collection_rate_spin.setSingleStep(1.0)
        self.collection_rate_spin.setToolTip("Time between saved data points")
        self.collection_rate_spin.valueChanged.connect(self.on_collection_rate_changed)
        data_layout.addWidget(self.collection_rate_spin, 0, 1)

        self.start_collection_btn = QPushButton("Start DC")
        self.start_collection_btn.clicked.connect(self.toggle_data_collection)
        self.start_collection_btn.setEnabled(False)
        data_layout.addWidget(self.start_collection_btn, 0, 2)

        self.show_od_map_btn = QPushButton("Show")
        self.show_od_map_btn.clicked.connect(self.toggle_od_heatmap_window)
        self.show_od_map_btn.setToolTip("Show OD time map")
        data_layout.addWidget(self.show_od_map_btn, 0, 3)

        self.collection_countdown_label = QLabel("Next: -- | Points: 0")
        self.collection_countdown_label.setToolTip("Next data-collection point countdown and saved point count")
        data_layout.addWidget(self.collection_countdown_label, 0, 4)

        data_layout.addWidget(QLabel("Folder:"), 1, 0)
        self.save_folder_input = QLineEdit(str(Path.home() / "AvantesData"))
        data_layout.addWidget(self.save_folder_input, 1, 1, 1, 3)

        self.browse_save_btn = QPushButton("Browse")
        self.browse_save_btn.clicked.connect(self.browse_save_folder)
        data_layout.addWidget(self.browse_save_btn, 1, 4)

        data_layout.addWidget(QLabel("Name:"), 2, 0)
        self.save_name_input = QLineEdit("avantes_measurement")
        self.save_name_input.setToolTip("Base file name without extension")
        data_layout.addWidget(self.save_name_input, 2, 1, 1, 4)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # Wavelength tracking
        wl_group = QGroupBox("Wavelength Tracking")
        wl_layout = QHBoxLayout()

        wl_layout.addWidget(QLabel("Wavelength (nm):"))
        self.track_wavelength_spin = QDoubleSpinBox()
        self.track_wavelength_spin.setRange(200, 1100)
        self.track_wavelength_spin.setValue(550)
        self.track_wavelength_spin.setSingleStep(1.0)
        wl_layout.addWidget(self.track_wavelength_spin)

        self.track_wl_btn = QPushButton("Track Wavelength")
        self.track_wl_btn.clicked.connect(self.open_wavelength_tracker)
        self.track_wl_btn.setEnabled(False)
        wl_layout.addWidget(self.track_wl_btn)

        wl_group.setLayout(wl_layout)
        layout.addWidget(wl_group)

        layout.addStretch()

        # Live preview control
        self.continuous_btn = QPushButton("Start Live Preview")
        self.continuous_btn.clicked.connect(self.toggle_continuous_readout)
        self.continuous_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        layout.addWidget(self.continuous_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMenu(self.create_settings_menu(self.settings_btn))
        layout.addWidget(self.settings_btn)

        # Export button
        self.export_btn = QPushButton("Export Data")
        self.export_btn.clicked.connect(self.export_data)
        layout.addWidget(self.export_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear Plots")
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
        menu = QMenu(parent or self)
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
            QMessageBox.warning(self, "Rate Too Short", message)
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
                QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
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
                QMessageBox.critical(self, "Error", f"Connection error:\n{str(e)}")
            return

        if not cfg1 or not cfg2:
            if not self.continuous_mode:
                QMessageBox.warning(self, "Error", "Failed to create measurement configuration")
            return

        # Disable controls during measurement
        self.set_controls_enabled(False)
        if measurement_role:
            self.current_measurement_role = measurement_role
        else:
            self.current_measurement_role = "preview" if self.continuous_mode else "manual"
        if self.current_measurement_role in {"reference", "background", "collection"}:
            self.logger.info(
                f"MEASUREMENT: role={self.current_measurement_role}, "
                f"Avantes averages ch1={int(cfg1.m_NrAverages)}, ch2={int(cfg2.m_NrAverages)}"
            )
        self.statusBar().showMessage("Measuring...")

        # Start measurement thread
        self.measurement_thread = MeasurementThread(
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
        dialog = CollectionSettingsDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        self.lamp_warmup_seconds = float(dialog.warmup_spin.value())
        self.lamp_min_off_seconds = float(dialog.min_off_spin.value())
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
                "lamp_min_off_seconds": float(self.lamp_min_off_seconds),
                "auto_lamp_management_enabled": bool(self.auto_lamp_management_enabled),
                "lamp_off_between_points_enabled": bool(self.lamp_off_between_points_enabled),
            },
            "spectrometers": {
                "1": self.get_spectrometer_settings(self.spec1_widget),
                "2": self.get_spectrometer_settings(self.spec2_widget),
            },
            "reference_background": {
                "blocks": int(self.ref_blocks_spin.value()),
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

    def get_spectrometer_settings(self, widget) -> dict:
        """Return settings for one spectrometer panel."""
        return {
            "serial": widget.serial_input.text().strip(),
            "integration_ms": float(widget.integration_spin.value()),
            "averages": int(widget.averages_spin.value()),
            "trigger_mode": int(widget.trigger_combo.currentIndex()),
        }

    def apply_settings_dict(self, settings: dict):
        """Apply settings loaded from JSON."""
        arduino = settings.get("arduino", {})
        if "lamp_warmup_seconds" in arduino:
            self.lamp_warmup_seconds = float(arduino["lamp_warmup_seconds"])
        if "lamp_min_off_seconds" in arduino:
            self.lamp_min_off_seconds = float(arduino["lamp_min_off_seconds"])
        if "auto_lamp_management_enabled" in arduino:
            self.auto_lamp_management_enabled = bool(arduino["auto_lamp_management_enabled"])
        if "lamp_off_between_points_enabled" in arduino:
            self.lamp_off_between_points_enabled = bool(arduino["lamp_off_between_points_enabled"])
        if "frequency_hz" in arduino:
            frequency = min(max(float(arduino["frequency_hz"]), 1.0), 100.0)
            if not self.set_arduino_frequency_hz(frequency):
                self.arduino_frequency_hz = frequency

        spectrometers = settings.get("spectrometers", {})
        self.apply_spectrometer_settings(self.spec1_widget, spectrometers.get("1", {}))
        self.apply_spectrometer_settings(self.spec2_widget, spectrometers.get("2", {}))

        ref_bg = settings.get("reference_background", {})
        if "blocks" in ref_bg:
            self.ref_blocks_spin.setValue(int(ref_bg["blocks"]))
        elif "averages" in ref_bg:
            legacy_averages = int(ref_bg["averages"])
            self.spec1_widget.averages_spin.setValue(legacy_averages)
            self.spec2_widget.averages_spin.setValue(legacy_averages)

        data_collection = settings.get("data_collection", {})
        if "rate_s" in data_collection:
            self.collection_rate_spin.setValue(float(data_collection["rate_s"]))
        if "save_folder" in data_collection:
            self.save_folder_input.setText(str(data_collection["save_folder"]))
        if "save_name" in data_collection:
            self.save_name_input.setText(str(data_collection["save_name"]))

        od_limits = settings.get("od_plot_limits", {})
        if "x_auto" in od_limits:
            self.od_x_auto_check.setChecked(bool(od_limits["x_auto"]))
        if "x_min_nm" in od_limits:
            self.od_x_min_spin.setValue(float(od_limits["x_min_nm"]))
        if "x_max_nm" in od_limits:
            self.od_x_max_spin.setValue(float(od_limits["x_max_nm"]))
        if "y_auto" in od_limits:
            self.od_y_auto_check.setChecked(bool(od_limits["y_auto"]))
        if "y_min" in od_limits:
            self.od_y_min_spin.setValue(float(od_limits["y_min"]))
        if "y_max" in od_limits:
            self.od_y_max_spin.setValue(float(od_limits["y_max"]))
        self.update_od_axis_limits()

        tracking = settings.get("wavelength_tracking", {})
        if "wavelength_nm" in tracking:
            self.track_wavelength_spin.setValue(float(tracking["wavelength_nm"]))

        self.validate_collection_rate(show_warning=False)
        self.update_live_preview_interval()

    def apply_spectrometer_settings(self, widget, settings: dict):
        """Apply settings to one spectrometer panel."""
        if "serial" in settings:
            widget.serial_input.setText(str(settings["serial"]))
        if "integration_ms" in settings:
            widget.integration_spin.setValue(float(settings["integration_ms"]))
        if "averages" in settings:
            widget.averages_spin.setValue(int(settings["averages"]))
        if "trigger_mode" in settings:
            widget.trigger_combo.setCurrentIndex(int(settings["trigger_mode"]))

    def load_settings_json(self):
        """Choose and load JSON settings."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Settings JSON",
            str(self.settings_json_path),
            "JSON Files (*.json)"
        )
        if filename:
            self.load_settings_from_file(Path(filename), show_message=True)

    def load_settings_from_file(self, path: Path, show_message: bool = False):
        """Load JSON settings from path."""
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
            self.apply_settings_dict(settings)
            self.settings_json_path = path
            self.statusBar().showMessage(f"Loaded settings: {path}")
            self.logger.info(f"SETTINGS: Loaded {path}")
            if show_message:
                QMessageBox.information(self, "Settings Loaded", f"Loaded:\n{path}")
        except Exception as e:
            self.logger.error(f"SETTINGS: Failed to load {path} - {e}")
            QMessageBox.critical(self, "Settings Error", f"Failed to load settings:\n{e}")

    def save_settings_json_as(self):
        """Choose JSON path and save settings."""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Settings JSON",
            str(self.settings_json_path),
            "JSON Files (*.json)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        self.settings_json_path = path
        self.write_settings_json(path, show_message=True)

    def update_settings_json(self):
        """Write current settings to current JSON path."""
        self.write_settings_json(self.settings_json_path, show_message=True)

    def write_settings_json(self, path: Path, show_message: bool = False):
        """Write current settings to JSON."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self.get_settings_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            self.statusBar().showMessage(f"Updated settings JSON: {path}")
            self.logger.info(f"SETTINGS: Updated {path}")
            if show_message:
                QMessageBox.information(self, "Settings Saved", f"Saved:\n{path}")
        except Exception as e:
            self.logger.error(f"SETTINGS: Failed to save {path} - {e}")
            QMessageBox.critical(self, "Settings Error", f"Failed to save settings:\n{e}")

    def is_lamp_enabled(self, poll: bool = False) -> bool:
        """Check whether lamp TTL is enabled."""
        if poll:
            lamp_enabled, _ = self.get_arduino_state()
            return bool(lamp_enabled)
        return bool(getattr(self.arduino, "lamp_enabled", False))

    def is_avantes_enabled(self, poll: bool = False) -> bool:
        """Check whether Avantes TTL is enabled."""
        if poll:
            _, avantes_enabled = self.get_arduino_state()
            return bool(avantes_enabled)
        return bool(getattr(self.arduino, "avantes_enabled", False))

    def set_lamp_on(self):
        """Enable lamp and Avantes TTL pulses."""
        return self.set_lamp_and_avantes()

    def set_lamp_off(self, reschedule=True):
        """Disable lamp while keeping Avantes TTL available."""
        result = self.set_avantes_only()
        if result and reschedule and self.data_collection_active and self.collection_next_due_time:
            self.schedule_collection_due_time(self.collection_next_due_time)
        return result

    def set_lamp_and_avantes(self, wait_for_thermalization=False):
        """Set Arduino to trigger both lamp and Avantes.

        Parameters
        ----------
        wait_for_thermalization : bool
            If True, wait 1 second after enabling lamp for thermalization
        """
        if self.is_lamp_enabled() and self.is_avantes_enabled():
            self.arduino_status_label.setText("Status: Lamp + Avantes")
            self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            return True

        if self.arduino.set_mode("LAMP AND AVANTES"):
            self.arduino_status_label.setText("Status: Lamp + Avantes")
            self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.logger.info("ARDUINO: Lamp + Avantes mode activated")

            # Wait for lamp thermalization if requested
            if wait_for_thermalization:
                self.logger.info("ARDUINO: Waiting 1s for lamp thermalization...")
                QTimer.singleShot(1000, lambda: self.logger.info("ARDUINO: Thermalization complete"))
                # Process events to keep UI responsive during wait
                from PyQt5.QtCore import QEventLoop
                loop = QEventLoop()
                QTimer.singleShot(1000, loop.quit)
                loop.exec_()

            return True
        else:
            self.arduino_status_label.setText("Status: Error")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.error("ARDUINO: Failed to set Lamp + Avantes mode")
            return False

    def set_avantes_only(self):
        """Set Arduino to trigger only Avantes (no lamp)."""
        if not self.is_lamp_enabled() and self.is_avantes_enabled():
            self.arduino_status_label.setText("Status: Avantes Only")
            self.arduino_status_label.setStyleSheet("color: orange; font-weight: bold;")
            return True

        if self.arduino.set_mode("ONLY AVANTES"):
            self.arduino_status_label.setText("Status: Avantes Only")
            self.arduino_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.logger.info("ARDUINO: Avantes Only mode activated (lamp OFF)")
            return True
        else:
            self.arduino_status_label.setText("Status: Error")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.error("ARDUINO: Failed to set Avantes Only mode")
            return False

    def set_arduino_off(self):
        """Turn off Arduino triggers."""
        if self.arduino.set_mode("OFF"):
            self.arduino_status_label.setText("Status: OFF")
            self.arduino_status_label.setStyleSheet("color: gray; font-weight: bold;")
            self.logger.info("ARDUINO: Triggers disabled")
        else:
            self.arduino_status_label.setText("Status: Error")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.error("ARDUINO: Failed to turn off")

    def toggle_continuous_readout(self):
        """Toggle manual live preview on/off."""
        if self.continuous_mode:
            self.stop_live_preview()
        else:
            # Start live preview at a modest rate; experiment collection has its own timer.
            interval_ms = self.get_live_preview_interval_ms()
            self.continuous_timer.start(interval_ms)
            self.continuous_mode = True
            self.continuous_btn.setText("Stop Live Preview")
            self.continuous_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
            self.logger.info(f"LIVE PREVIEW: Started ({interval_ms}ms interval)")
            self.statusBar().showMessage("Live preview active")

    def stop_live_preview(self):
        """Stop manual live preview if it is active."""
        if self.continuous_timer.isActive():
            self.continuous_timer.stop()
        self.continuous_mode = False
        self.continuous_btn.setText("Start Live Preview")
        self.continuous_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.logger.info(f"LIVE PREVIEW: Stopped ({self._measurement_count} measurements completed)")
        self.statusBar().showMessage("Live preview stopped")

    def stop_measurement(self):
        """Stop current reference or background measurement."""
        if self.measuring_reference:
            self.logger.info(
                f"REFERENCE: Measurement aborted by user "
                f"({len(self.reference_measurements)} of {self.reference_target_blocks} blocks collected)"
            )
            self.measuring_reference = False
            self.reference_measurements = []
            self.statusBar().showMessage("Reference measurement aborted")

        if self.measuring_background:
            self.logger.info(
                f"BACKGROUND: Measurement aborted by user "
                f"({len(self.background_measurements)} of {self.background_target_blocks} blocks collected)"
            )
            self.measuring_background = False
            self.background_measurements = []
            self.statusBar().showMessage("Background measurement aborted")

        # Re-enable buttons
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)
        self.pending_ref_bg_role = None

    def measure_reference(self):
        """Measure reference spectra by averaging N measurements (with lamp ON)."""
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            return

        # Ensure lamp is ON and wait for thermalization
        self.statusBar().showMessage("Preparing lamp...")
        if not self.set_lamp_and_avantes(wait_for_thermalization=True):
            QMessageBox.warning(self, "Error", "Failed to enable lamp")
            return

        n_avg = self.get_detector_average_count()
        n_blocks = self.ref_blocks_spin.value()
        self.reference_target_blocks = n_blocks
        self.pending_ref_bg_role = None
        self.measuring_reference = True
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button

        self.logger.info(
            f"REFERENCE: Starting measurement (lamp ON, hardware avg={n_avg} pulses, "
            f"blocks={n_blocks}, total pulses={n_avg * n_blocks})"
        )
        self.statusBar().showMessage(f"Measuring reference block 1/{n_blocks} (Avantes avg={n_avg})...")

        self.single_measurement(measurement_role="reference")

    def measure_background(self):
        """Measure background spectra by averaging N measurements (with lamp OFF)."""
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            return

        # Ensure lamp is OFF
        self.set_avantes_only()

        n_avg = self.get_detector_average_count()
        n_blocks = self.ref_blocks_spin.value()
        self.background_target_blocks = n_blocks
        self.pending_ref_bg_role = None
        self.measuring_background = True
        self.background_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button

        self.logger.info(
            f"BACKGROUND: Starting measurement (lamp OFF, hardware avg={n_avg} pulses, "
            f"blocks={n_blocks}, total pulses={n_avg * n_blocks})"
        )
        self.statusBar().showMessage(f"Measuring background block 1/{n_blocks} (Avantes avg={n_avg})...")

        self.single_measurement(measurement_role="background")

    def measure_reference_complete(self):
        """Called when reference measurement is complete."""
        if self.reference_measurements:
            self.reference_ch1 = np.mean([m['ch1'] for m in self.reference_measurements], axis=0)
            self.reference_ch2 = np.mean([m['ch2'] for m in self.reference_measurements], axis=0)
            self.reference_wavelengths = self.spec1_widget.wavelengths
            self.clear_zero_baseline()
            self.has_reference = True

            # Display reference lines on plots (magenta/purple)
            if self.reference_wavelengths is not None:
                self.ref_curve1.setData(self.reference_wavelengths, self.reference_ch1)
                self.ref_curve2.setData(self.reference_wavelengths, self.reference_ch2)

            n_blocks = len(self.reference_measurements)
            n_avg = self.get_detector_average_count()
            self.logger.info(
                f"REFERENCE: Measurement complete (lamp ON, blocks={n_blocks}, "
                f"hardware avg={n_avg}, total pulses={n_blocks * n_avg})"
            )
            self.statusBar().showMessage(f"Reference measured ({n_blocks} blocks x {n_avg} pulses)")

            # Enable data collection and tracking after reference and background exist.
            self.update_analysis_buttons()

        else:
            self.logger.error("REFERENCE: Failed - no measurement")
            self.statusBar().showMessage("Reference measurement failed")

        self.measuring_reference = False
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)  # Disable stop button
        self.update_analysis_buttons()

    def set_zero_baseline_from_current(self):
        """Store current no-sample OD as a baseline to subtract from future OD."""
        data1 = self.spec1_widget.last_data
        data2 = self.spec2_widget.last_data
        wavelengths = self.spec1_widget.wavelengths

        if data1 is None or data2 is None or wavelengths is None:
            QMessageBox.warning(self, "Set Zero", "No current spectra available")
            return

        if not self.has_reference or not self.has_background:
            QMessageBox.warning(self, "Set Zero", "Measure background and reference first")
            return

        od_spectrum = self.calculate_optical_density(data1, data2, apply_zero_baseline=False)
        if od_spectrum is not None:
            self.zero_baseline_wavelengths = np.array(wavelengths, dtype=float, copy=True)
            self.zero_baseline_od = np.array(od_spectrum, dtype=float, copy=True)
            corrected_od = od_spectrum - self.zero_baseline_od
            self.curve_od.setData(self.zero_baseline_wavelengths, corrected_od)

        self.update_analysis_buttons()
        self.logger.info("ZERO: Baseline OD set from current spectra")
        self.statusBar().showMessage("Zero baseline set from current spectra")

    def measure_background_complete(self):
        """Called when background measurement is complete."""
        if self.background_measurements:
            self.background_ch1 = np.mean([m['ch1'] for m in self.background_measurements], axis=0)
            self.background_ch2 = np.mean([m['ch2'] for m in self.background_measurements], axis=0)
            self.clear_zero_baseline()
            self.has_background = True

            # Display background lines on plots (blue)
            # Use wavelengths from spectrometer (always available after connection)
            wavelengths = self.spec1_widget.wavelengths
            if wavelengths is not None:
                self.bg_curve1.setData(wavelengths, self.background_ch1)
                self.bg_curve2.setData(wavelengths, self.background_ch2)
                n_blocks = len(self.background_measurements)
                n_avg = self.get_detector_average_count()
                self.logger.info(
                    f"BACKGROUND: Measurement complete (lamp OFF, blocks={n_blocks}, "
                    f"hardware avg={n_avg}, total pulses={n_blocks * n_avg})"
                )
            else:
                self.logger.warning("BACKGROUND: Wavelengths not available for plotting")

            self.statusBar().showMessage(f"Background measured ({len(self.background_measurements)} blocks)")
            self.update_analysis_buttons()

        else:
            self.logger.error("BACKGROUND: Failed - no measurement")
            self.statusBar().showMessage("Background measurement failed")

        # Reset measuring flag FIRST before any other updates
        self.measuring_background = False
        self.background_measurements = []
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)  # Disable stop button

        # Log the state explicitly
        self.logger.info(f"BACKGROUND: Flags reset - measuring_background={self.measuring_background}, has_background={self.has_background}")

    def toggle_data_collection(self):
        """Toggle data collection mode."""
        if not self.data_collection_active:
            # Start data collection
            if not self.has_reference or not self.has_background:
                QMessageBox.warning(self, "Error", "Please measure reference and background first")
                return

            if not self.validate_collection_rate(show_warning=True):
                return

            interval_ms = int(self.collection_rate_spin.value() * 1000)
            if interval_ms < 100:
                QMessageBox.warning(self, "Error", "Minimum collection rate is 0.1s (100ms)")
                return

            try:
                save_dir = Path(self.save_folder_input.text()).expanduser()
                save_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Save Folder Error", f"Cannot use save folder:\n{str(e)}")
                return

            base_name = self.save_name_input.text().strip() or "avantes_measurement"
            self.collection_file_path = save_dir / f"{base_name}.dat"

            self.data_collection_active = True
            self.collection_data = []
            self.collection_point_index = 0
            self.collection_start_time = time.time()
            self.collection_point_start_time = None
            self.collection_next_due_time = None
            self.reset_od_heatmap()
            if self.collection_file_path.exists():
                self.collection_file_path.unlink()

            self.start_collection_btn.setText("Stop DC")
            self.collection_countdown_timer.start()
            self.update_collection_countdown_label()
            self.logger.info(
                f"DATA COLLECTION: Started (rate={self.collection_rate_spin.value()}s, "
                f"detector_avg={self.get_detector_average_count()}, file={self.collection_file_path})"
            )
            self.statusBar().showMessage(f"Data collection active ({self.collection_rate_spin.value()}s interval)")
            self.collect_data_point()
        else:
            # Stop data collection
            self.data_collection_active = False
            self.collection_timer.stop()
            self.lamp_warmup_timer.stop()
            self.collection_countdown_timer.stop()
            self.start_collection_btn.setText("Start DC")

            n_points = len(self.collection_data) if hasattr(self, 'collection_data') else 0
            self.update_collection_countdown_label()
            self.logger.info(f"DATA COLLECTION: Stopped ({n_points} data points collected, file={self.collection_file_path})")
            self.statusBar().showMessage(f"Data collection stopped ({n_points} points)")

    def collect_data_point(self):
        """Collect a data point during active data collection."""
        if not self.data_collection_active or not self.has_reference or not self.has_background:
            return
        if self.measurement_thread and self.measurement_thread.isRunning():
            return

        n_avg = self.get_detector_average_count()
        self.collection_timer.stop()
        self.lamp_warmup_timer.stop()
        if not self.is_lamp_enabled():
            self.logger.info("DATA COLLECTION: Lamp was off at measurement time; enabling now")
            if not self.set_lamp_and_avantes():
                self.statusBar().showMessage("Data collection paused: failed to enable lamp")
                self.schedule_next_collection_point()
                return
        self.collection_point_start_time = time.time()
        self.statusBar().showMessage(f"Collecting point {self.collection_point_index + 1} (avg={n_avg})...")
        self.update_collection_countdown_label()
        self.single_measurement(averages_override=n_avg, measurement_role="collection")

    def schedule_next_collection_point(self):
        """Schedule next collection point without overlapping hardware averaging."""
        if not self.data_collection_active:
            return

        self.validate_collection_rate(show_warning=False)
        interval_s = float(self.collection_rate_spin.value())
        base_time = self.collection_point_start_time or time.time()
        self.schedule_collection_due_time(base_time + interval_s)
        self.update_collection_countdown_label()

    def on_collection_rate_changed(self):
        """Reschedule active data collection when rate changes."""
        if not self.data_collection_active:
            return
        if self.measurement_thread and self.measurement_thread.isRunning():
            return

        self.validate_collection_rate(show_warning=False)
        interval_s = float(self.collection_rate_spin.value())
        base_time = self.collection_point_start_time or self.collection_start_time or time.time()
        self.schedule_collection_due_time(base_time + interval_s)
        self.update_collection_countdown_label()

    def schedule_collection_due_time(self, due_time: float):
        """Schedule warmup and measurement for the next collection point."""
        if not self.data_collection_active:
            return

        self.collection_next_due_time = due_time
        self.collection_timer.stop()
        self.lamp_warmup_timer.stop()

        now = time.time()
        seconds_until_due = max(0.0, due_time - now)
        warmup_s = max(0.0, float(self.lamp_warmup_seconds))
        lamp_off_gap_s = seconds_until_due - warmup_s
        min_off_s = max(0.0, float(self.lamp_min_off_seconds))
        can_save_lamp = (
            self.auto_lamp_management_enabled
            and self.lamp_off_between_points_enabled
            and lamp_off_gap_s >= min_off_s
        )

        if not self.auto_lamp_management_enabled:
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(f"Next point in {seconds_until_due:.0f}s")
        elif can_save_lamp:
            if self.is_lamp_enabled():
                self.set_lamp_off(reschedule=False)
            warmup_delay_ms = int(lamp_off_gap_s * 1000)
            self.lamp_warmup_timer.start(warmup_delay_ms)
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(
                f"Next point in {seconds_until_due:.0f}s; lamp warmup starts in {lamp_off_gap_s:.0f}s"
            )
        else:
            if not self.is_lamp_enabled():
                self.prepare_lamp_for_collection()
            self.collection_timer.start(int(seconds_until_due * 1000))
            self.statusBar().showMessage(f"Next point in {seconds_until_due:.0f}s; lamp stays on")
            if (
                self.auto_lamp_management_enabled
                and self.lamp_off_between_points_enabled
                and lamp_off_gap_s > 0
            ):
                self.logger.info(
                    f"DATA COLLECTION: Lamp stays on; off gap {lamp_off_gap_s:.1f}s "
                    f"is shorter than minimum {min_off_s:.1f}s"
                )
        self.update_collection_countdown_label()

    def prepare_lamp_for_collection(self):
        """Enable lamp before a scheduled collection point."""
        if not self.data_collection_active:
            return
        if self.is_lamp_enabled():
            return
        if self.set_lamp_and_avantes():
            due = self.collection_next_due_time or time.time()
            self.statusBar().showMessage(f"Lamp warming; next point in {max(0.0, due - time.time()):.0f}s")
            self.logger.info("DATA COLLECTION: Lamp enabled for scheduled measurement")
            self.update_collection_countdown_label()

    def format_seconds_for_countdown(self, seconds: float) -> str:
        """Format countdown seconds as compact time text."""
        seconds = max(0, int(round(seconds)))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:d}:{secs:02d}"

    def update_collection_countdown_label(self):
        """Update data-collection countdown and point counter."""
        points = self.collection_point_index if hasattr(self, "collection_point_index") else 0
        if not hasattr(self, "collection_countdown_label"):
            return
        if not self.data_collection_active:
            self.collection_countdown_label.setText(f"Next: -- | Points: {points}")
            return
        if getattr(self, "current_measurement_role", None) == "collection":
            self.collection_countdown_label.setText(f"Collecting... | Points: {points}")
            return
        if self.collection_next_due_time is None:
            self.collection_countdown_label.setText(f"Next: now | Points: {points}")
            return

        remaining = max(0.0, self.collection_next_due_time - time.time())
        text = f"Next: {self.format_seconds_for_countdown(remaining)} | Points: {points}"

        if self.auto_lamp_management_enabled and self.lamp_off_between_points_enabled:
            warmup_start_in = remaining - max(0.0, float(self.lamp_warmup_seconds))
            if warmup_start_in >= max(0.0, float(self.lamp_min_off_seconds)):
                text += f" | Lamp in {self.format_seconds_for_countdown(warmup_start_in)}"
            else:
                text += " | Lamp on"

        self.collection_countdown_label.setText(text)

    def browse_save_folder(self):
        """Choose folder for exported and collected files."""
        folder = QFileDialog.getExistingDirectory(self, "Choose Save Folder", self.save_folder_input.text())
        if folder:
            self.save_folder_input.setText(folder)

    def update_analysis_buttons(self):
        """Enable controls that require complete OD prerequisites."""
        enabled = self.has_reference and self.has_background
        self.start_collection_btn.setEnabled(enabled)
        self.track_wl_btn.setEnabled(enabled)
        has_current = self.spec1_widget.last_data is not None and self.spec2_widget.last_data is not None
        self.zero_reference_btn.setEnabled(enabled and has_current)

    def clear_zero_baseline(self):
        """Clear the stored OD zero baseline."""
        self.zero_baseline_wavelengths = None
        self.zero_baseline_od = None

    def reset_od_heatmap(self):
        """Clear OD time map for a new data collection run."""
        self.od_heatmap_rows = []
        self.od_heatmap_times = []
        self.od_heatmap_wavelengths = None
        self.render_od_heatmap()

    def update_od_heatmap(
        self,
        wavelengths: np.ndarray,
        od_spectrum: Optional[np.ndarray],
        elapsed_time: Optional[float] = None,
    ):
        """Append one OD spectrum to the time map."""
        if wavelengths is None or od_spectrum is None:
            return

        self.od_heatmap_wavelengths = wavelengths
        self.od_heatmap_rows.append(np.array(od_spectrum, dtype=float))
        if elapsed_time is None:
            elapsed_time = float(len(self.od_heatmap_rows))
        self.od_heatmap_times.append(float(elapsed_time))
        self.render_od_heatmap()

    def render_od_heatmap(self):
        """Render heatmap data if floating window exists."""
        if self.od_heatmap_window is not None:
            self.od_heatmap_window.set_heatmap(
                self.od_heatmap_wavelengths,
                self.od_heatmap_rows,
                self.od_heatmap_times,
            )

    def toggle_od_heatmap_window(self):
        """Open the floating OD time map, or close it if already visible."""
        if self.od_heatmap_window is not None:
            window = self.od_heatmap_window
            self.od_heatmap_window = None
            self.show_od_map_btn.setText("Show")
            window.close()
            return

        self.show_od_heatmap_window()

    def show_od_heatmap_window(self):
        """Open or raise the floating OD time map window."""
        if self.od_heatmap_window is None:
            self.od_heatmap_window = ODHeatmapWindow(self)
        self.render_od_heatmap()
        self.od_heatmap_window.show()
        self.od_heatmap_window.raise_()
        self.od_heatmap_window.activateWindow()
        self.show_od_map_btn.setText("Hide")

    def get_export_base_path(self) -> Path:
        """Return base path for manual export files."""
        save_dir = Path(self.save_folder_input.text()).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)
        base_name = self.save_name_input.text().strip() or "avantes_measurement"
        return save_dir / base_name

    def open_wavelength_tracker(self):
        """Open wavelength tracking window."""
        if not self.has_reference or not self.has_background:
            QMessageBox.warning(self, "Error", "Please measure reference and background first")
            return

        wavelength = self.track_wavelength_spin.value()

        if self.wavelength_tracker_window is None:
            self.wavelength_tracker_window = WavelengthTrackerWindow(self, wavelength)
            self.wavelength_tracker_window.show()
        else:
            self.wavelength_tracker_window.set_wavelength(wavelength)
            self.wavelength_tracker_window.show()
            self.wavelength_tracker_window.raise_()
            self.wavelength_tracker_window.activateWindow()

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
            if self.collection_point_index == 0:
                collection_elapsed = 0.0
            else:
                collection_elapsed = time.time() - self.collection_start_time
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
                QMessageBox.critical(self, "Measurement Error", error_msg)

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
        wavelengths: np.ndarray,
        od_spectrum: Optional[np.ndarray],
    ):
        """Append one OD spectrum row to tab-delimited DAT file."""
        if self.collection_file_path is None or wavelengths is None:
            return

        if od_spectrum is None:
            od_spectrum = np.full_like(wavelengths, np.nan, dtype=float)

        write_header = not self.collection_file_path.exists()
        row = np.concatenate(([elapsed_time], np.asarray(od_spectrum, dtype=float)))
        with open(self.collection_file_path, "a", encoding="utf-8") as f:
            if write_header:
                wavelength_header = "\t".join(f"{wl:.3f}" for wl in wavelengths)
                f.write(f"time_s\t{wavelength_header}\n")
            np.savetxt(f, row.reshape(1, -1), delimiter="\t", fmt="%.8g")
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
            QMessageBox.warning(self, "No Data", "No measurement data to export")
            return

        try:
            base_filename = str(self.get_export_base_path())

            # Export spec 1
            if data1 is not None and wl1 is not None:
                filename1 = f"{base_filename}_spec1.csv"
                np.savetxt(
                    filename1,
                    np.column_stack((wl1, data1)),
                    delimiter=',',
                    header='Wavelength(nm),Intensity(counts)',
                    comments=''
                )

            # Export spec 2
            if data2 is not None and wl2 is not None:
                filename2 = f"{base_filename}_spec2.csv"
                np.savetxt(
                    filename2,
                    np.column_stack((wl2, data2)),
                    delimiter=',',
                    header='Wavelength(nm),Intensity(counts)',
                    comments=''
                )

            # Calculate and export OD if both datasets available
            if data1 is not None and data2 is not None and wl1 is not None:
                od = self.calculate_optical_density(data1, data2)
                if od is not None:
                    filename_od = f"{base_filename}_OD.csv"
                    np.savetxt(
                        filename_od,
                        np.column_stack((wl1, od)),
                        delimiter=',',
                        header='Wavelength(nm),OpticalDensity(AU)',
                        comments=''
                    )

            self.logger.info(f"EXPORT: Data saved to {base_filename}_*.csv (spec1, spec2, OD)")

            QMessageBox.information(self, "Export Complete", f"Data exported to {base_filename}_*.csv")

        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")

    def calculate_optical_density(
        self,
        ch1_current: np.ndarray,
        ch2_current: np.ndarray,
        elapsed_time: Optional[float] = None,
        apply_zero_baseline: bool = True,
    ) -> Optional[np.ndarray]:
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
            with np.errstate(divide='ignore', invalid='ignore'):
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
                od = np.log10(ref_ratio / curr_ratio)

                if elapsed_time is not None and self.demo_kinetics_enabled:
                    od += self.get_demo_species_od(np.asarray(self.spec1_widget.wavelengths), elapsed_time)

                if (
                    apply_zero_baseline
                    and self.zero_baseline_od is not None
                    and len(self.zero_baseline_od) == len(od)
                ):
                    od = od - self.zero_baseline_od

                # Replace inf and nan with 0
                od[~np.isfinite(od)] = 0

            return od

        except Exception as e:
            self.logger.error(f"Failed to calculate OD: {e}")
            return None

    def get_demo_species_od(self, wavelengths: np.ndarray, elapsed_time: float) -> np.ndarray:
        """Return a synthetic growing UV-visible species OD spectrum."""
        if wavelengths is None:
            return 0.0

        duration_s = max(1.0, self.demo_kinetics_duration_s)
        progress = np.clip(float(elapsed_time) / duration_s, 0.0, 1.0)
        growth = 1.0 - np.exp(-4.2 * progress)
        slow_growth = progress * progress * (3.0 - 2.0 * progress)
        wl = np.asarray(wavelengths, dtype=float)

        # Broad product bands spanning UV to visible, with a later visible shoulder.
        species_shape = (
            0.32 * np.exp(-0.5 * ((wl - 285.0) / 34.0) ** 2)
            + 0.46 * np.exp(-0.5 * ((wl - 365.0) / 58.0) ** 2)
            + 0.58 * np.exp(-0.5 * ((wl - 525.0) / 120.0) ** 2)
            + 0.25 * np.exp(-0.5 * ((wl - 705.0) / 170.0) ** 2)
        )
        late_visible = 0.24 * slow_growth * np.exp(-0.5 * ((wl - 610.0) / 95.0) ** 2)
        baseline = 0.025 * growth * np.exp(-0.5 * ((wl - 480.0) / 360.0) ** 2)
        species_shape = species_shape / max(float(np.max(species_shape)), 1e-12)
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
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"avantes_dual_{timestamp}.log"

        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler(log_file, encoding="utf-8")

        # Stream handler: try to reconfigure stdout to UTF-8 (Python 3.7+);
        # fall back to replacing un-encodable characters so logging never crashes.
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            stream_handler = logging.StreamHandler(sys.stdout)
        except Exception:
            import io
            utf8_stream = io.TextIOWrapper(
                sys.stdout.buffer if hasattr(sys.stdout, "buffer") else sys.stdout,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
            )
            stream_handler = logging.StreamHandler(utf8_stream)

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        # Configure root logger (force=True clears any pre-existing handlers
        # so we don't end up with duplicate non-UTF-8 handlers).
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler, stream_handler],
            force=True,
        )

        self.logger = logging.getLogger(__name__)
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
        QTimer.singleShot(1000, self.auto_connect_spec2)

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
