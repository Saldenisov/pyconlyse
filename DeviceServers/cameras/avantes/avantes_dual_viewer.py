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
    QCheckBox, QSplitter
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont

import pyqtgraph as pg

# Add project path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from msl.equipment import Backend, ConnectionRecord, EquipmentRecord
from DeviceServers.cameras.avantes.avantes_parallel import (
    parallel_prepare_measure,
    parallel_measure,
    parallel_poll_and_get_data
)
from DeviceServers.cameras.avantes.arduino_trigger_controller import ArduinoTriggerController


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
    
    def __init__(self, spec_id: int, parent=None):
        super().__init__(f"Spectrometer {spec_id}", parent)
        self.spec_id = spec_id
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
        self.connect_btn = QPushButton("Connect")
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
            dll_path = Path(__file__).parent / "drivers" / "avaspecx64.dll"
            
            record = EquipmentRecord(
                manufacturer="Avantes",
                model="AvaSpec-2048L",
                serial=serial,
                connection=ConnectionRecord(
                    address=f"SDK::{dll_path}"
                ),
            )
            
            self.spec = record.connect(demo=False)
            self.spec.use_high_res_adc(True)
            
            # Get wavelength calibration
            self.wavelengths = self.spec.get_lambda()
            num_pixels = self.spec.get_num_pixels()
            
            logging.info(f"Spec {self.spec_id} CONNECTED: Serial={serial}, Pixels={num_pixels}, λ={self.wavelengths[0]:.1f}-{self.wavelengths[-1]:.1f} nm")
            
            # Update UI
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
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
        self.wavelength_tracker_window = None
        
        # Arduino controller
        self.arduino = ArduinoTriggerController(ip="10.20.30.47")
        
        # Timers
        self.continuous_timer = QTimer()
        self.continuous_timer.timeout.connect(self.continuous_measurement)
        self.collection_timer = QTimer()
        self.collection_timer.timeout.connect(self.collect_data_point)
        
        # Setup logging
        self.setup_logging()
        
        self.init_ui()
        
        # Auto-connect both spectrometers after UI is ready
        QTimer.singleShot(500, self.auto_connect_spectrometers)
    
    def init_ui(self):
        """Initialize the main UI."""
        self.setWindowTitle("Avantes Dual Spectrometer Viewer")
        self.setGeometry(100, 100, 1400, 900)
        
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
        self.spec1_widget = SpectrometerWidget(1)
        controls_splitter.addWidget(self.spec1_widget)
        
        # Spectrometer 2 controls
        self.spec2_widget = SpectrometerWidget(2)
        controls_splitter.addWidget(self.spec2_widget)
        
        main_layout.addWidget(controls_splitter)
        
        # Plot layout: Left side (Ch1 + Ch2), Right side (OD)
        plot_main_splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Channel spectra (vertical split)
        left_plot_splitter = QSplitter(Qt.Vertical)
        
        # Ch1 plot (top left)
        self.plot1 = pg.PlotWidget(title="Channel 1 Spectrum")
        self.plot1.setLabel('left', 'Intensity', units='counts')
        self.plot1.setLabel('bottom', 'Wavelength', units='nm')
        self.plot1.showGrid(x=True, y=True)
        self.curve1 = self.plot1.plot(pen=pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve1 = self.plot1.plot(pen=pg.mkPen('m', width=2, style=Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve1 = self.plot1.plot(pen=pg.mkPen('b', width=2, style=Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot1)
        
        # Ch2 plot (bottom left)
        self.plot2 = pg.PlotWidget(title="Channel 2 Spectrum")
        self.plot2.setLabel('left', 'Intensity', units='counts')
        self.plot2.setLabel('bottom', 'Wavelength', units='nm')
        self.plot2.showGrid(x=True, y=True)
        self.curve2 = self.plot2.plot(pen=pg.mkPen('w', width=2), name='RT')  # White for real-time
        self.ref_curve2 = self.plot2.plot(pen=pg.mkPen('m', width=2, style=Qt.DashLine), name='REF')  # Magenta for reference
        self.bg_curve2 = self.plot2.plot(pen=pg.mkPen('b', width=2, style=Qt.DashLine), name='BG')  # Blue for background
        left_plot_splitter.addWidget(self.plot2)
        
        plot_main_splitter.addWidget(left_plot_splitter)
        
        # Right side: OD spectrum plot with controls
        od_widget = QWidget()
        od_layout = QVBoxLayout(od_widget)
        od_layout.setContentsMargins(0, 0, 0, 0)
        
        self.plot_od = pg.PlotWidget(title="Optical Density (OD) Spectrum")
        self.plot_od.setLabel('left', 'OD (Absorbance)', units='AU')
        self.plot_od.setLabel('bottom', 'Wavelength', units='nm')
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
    
    def create_control_panel(self) -> QGroupBox:
        """Create the main control panel."""
        panel = QGroupBox("Measurement Controls")
        layout = QHBoxLayout()
        
        # Arduino control section
        arduino_group = QGroupBox("Arduino Control")
        arduino_layout = QVBoxLayout()
        
        arduino_btn_layout = QHBoxLayout()
        self.lamp_avantes_btn = QPushButton("Lamp + Avantes")
        self.lamp_avantes_btn.clicked.connect(self.set_lamp_and_avantes)
        arduino_btn_layout.addWidget(self.lamp_avantes_btn)
        
        self.avantes_only_btn = QPushButton("Avantes Only")
        self.avantes_only_btn.clicked.connect(self.set_avantes_only)
        arduino_btn_layout.addWidget(self.avantes_only_btn)
        
        self.arduino_off_btn = QPushButton("Arduino OFF")
        self.arduino_off_btn.clicked.connect(self.set_arduino_off)
        arduino_btn_layout.addWidget(self.arduino_off_btn)
        
        arduino_layout.addLayout(arduino_btn_layout)
        
        self.arduino_status_label = QLabel("Status: Unknown")
        arduino_layout.addWidget(self.arduino_status_label)
        
        arduino_group.setLayout(arduino_layout)
        layout.addWidget(arduino_group)
        
        # Reference and Background measurement section
        ref_bg_group = QGroupBox("Reference & Background")
        ref_bg_layout = QVBoxLayout()
        
        # Averages control (shared by both)
        avg_layout = QHBoxLayout()
        avg_layout.addWidget(QLabel("Averages:"))
        self.ref_averages_spin = QSpinBox()
        self.ref_averages_spin.setRange(1, 100)
        self.ref_averages_spin.setValue(10)
        self.ref_averages_spin.setToolTip("Number of measurements to average")
        avg_layout.addWidget(self.ref_averages_spin)
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
        data_layout = QHBoxLayout()
        
        data_layout.addWidget(QLabel("Rate (s):"))
        self.collection_rate_spin = QDoubleSpinBox()
        self.collection_rate_spin.setRange(0.1, 10.0)
        self.collection_rate_spin.setValue(1.0)
        self.collection_rate_spin.setSingleStep(0.1)
        self.collection_rate_spin.setToolTip("Measurement interval (minimum 0.1s)")
        data_layout.addWidget(self.collection_rate_spin)
        
        self.start_collection_btn = QPushButton("Start Data Collection")
        self.start_collection_btn.clicked.connect(self.toggle_data_collection)
        self.start_collection_btn.setEnabled(False)
        data_layout.addWidget(self.start_collection_btn)
        
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
        
        # Continuous mode control
        self.continuous_btn = QPushButton("Stop Continuous")
        self.continuous_btn.clicked.connect(self.toggle_continuous_readout)
        self.continuous_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        layout.addWidget(self.continuous_btn)
        
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
    
    def single_measurement(self):
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
                self.logger.error("Spectrometer connection lost - stopping continuous mode")
                self.continuous_check.setChecked(False)
            return
        
        # Validate connections are still active
        try:
            cfg1 = self.spec1_widget.get_measurement_config()
            cfg2 = self.spec2_widget.get_measurement_config()
        except Exception as e:
            self.logger.error(f"Failed to get measurement config: {e}")
            if self.continuous_mode:
                self.logger.error("Stopping continuous mode due to connection error")
                self.continuous_check.setChecked(False)
            else:
                QMessageBox.critical(self, "Error", f"Connection error:\n{str(e)}")
            return
        
        if not cfg1 or not cfg2:
            if not self.continuous_mode:
                QMessageBox.warning(self, "Error", "Failed to create measurement configuration")
            return
        
        # Disable controls during measurement
        self.set_controls_enabled(False)
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
        """Trigger measurement for continuous mode."""
        # Skip if previous measurement still running
        if self.measurement_thread and self.measurement_thread.isRunning():
            return
            
        self.single_measurement()
    
    def set_lamp_and_avantes(self, wait_for_thermalization=False):
        """Set Arduino to trigger both lamp and Avantes.
        
        Parameters
        ----------
        wait_for_thermalization : bool
            If True, wait 1 second after enabling lamp for thermalization
        """
        # Always send command to ensure mode is set correctly
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
        # Always send command to ensure mode is set correctly
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
        """Toggle continuous readout mode on/off."""
        if self.continuous_mode:
            # Stop continuous mode
            self.continuous_timer.stop()
            self.continuous_mode = False
            self.continuous_btn.setText("Start Continuous")
            self.continuous_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            self.logger.info(f"CONTINUOUS: Stopped ({self._measurement_count} measurements completed)")
            self.statusBar().showMessage("Continuous readout stopped")
        else:
            # Start continuous mode
            self.continuous_timer.start(50)  # 50ms polling for 10Hz Arduino triggers
            self.continuous_mode = True
            self._measurement_count = 0
            self.continuous_btn.setText("Stop Continuous")
            self.continuous_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
            self.logger.info("CONTINUOUS: Started (50ms polling interval)")
            self.statusBar().showMessage("Continuous readout active")
    
    def stop_measurement(self):
        """Stop current reference or background measurement."""
        if self.measuring_reference:
            self.logger.info(f"REFERENCE: Measurement aborted by user ({len(self.reference_measurements)} of {self.ref_averages_spin.value()} collected)")
            self.measuring_reference = False
            self.reference_measurements = []
            self.statusBar().showMessage("Reference measurement aborted")
        
        if self.measuring_background:
            self.logger.info(f"BACKGROUND: Measurement aborted by user ({len(self.background_measurements)} of {self.ref_averages_spin.value()} collected)")
            self.measuring_background = False
            self.background_measurements = []
            self.statusBar().showMessage("Background measurement aborted")
        
        # Re-enable buttons
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)
    
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
        
        n_avg = self.ref_averages_spin.value()
        self.measuring_reference = True
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button
        
        self.logger.info(f"REFERENCE: Starting measurement (lamp ON, averaging {n_avg} spectra)")
        self.statusBar().showMessage(f"Measuring reference (0/{n_avg})...")
        
        # Start continuous mode to collect measurements
        if not self.continuous_mode:
            self.continuous_timer.start(50)  # 50ms polling for 10Hz Arduino triggers
            self.continuous_mode = True
        self._measurement_count = 0
    
    def measure_background(self):
        """Measure background spectra by averaging N measurements (with lamp OFF)."""
        if not self.spec1_widget.spec or not self.spec2_widget.spec:
            QMessageBox.warning(self, "Error", "Both spectrometers must be connected")
            return
        
        # Ensure lamp is OFF
        self.set_avantes_only()
        
        n_avg = self.ref_averages_spin.value()
        self.measuring_background = True
        self.background_measurements = []
        self.measure_ref_btn.setEnabled(False)
        self.measure_bg_btn.setEnabled(False)
        self.stop_measure_btn.setEnabled(True)  # Enable stop button
        
        self.logger.info(f"BACKGROUND: Starting measurement (lamp OFF, averaging {n_avg} spectra)")
        self.statusBar().showMessage(f"Measuring background (0/{n_avg})...")
        
        # Start continuous mode to collect measurements
        if not self.continuous_mode:
            self.continuous_timer.start(50)  # 50ms polling for 10Hz Arduino triggers
            self.continuous_mode = True
        self._measurement_count = 0
    
    def measure_reference_complete(self):
        """Called when reference measurement is complete."""
        n_avg = self.ref_averages_spin.value()
        
        # Average all collected measurements
        ch1_data = [m['ch1'] for m in self.reference_measurements if m['ch1'] is not None]
        ch2_data = [m['ch2'] for m in self.reference_measurements if m['ch2'] is not None]
        
        if len(ch1_data) >= n_avg and len(ch2_data) >= n_avg:
            self.reference_ch1 = np.mean(ch1_data[:n_avg], axis=0)
            self.reference_ch2 = np.mean(ch2_data[:n_avg], axis=0)
            self.reference_wavelengths = self.spec1_widget.wavelengths
            self.has_reference = True
            
            # Display reference lines on plots (magenta/purple)
            if self.reference_wavelengths is not None:
                self.ref_curve1.setData(self.reference_wavelengths, self.reference_ch1)
                self.ref_curve2.setData(self.reference_wavelengths, self.reference_ch2)
            
            self.logger.info("REFERENCE: Measurement complete (lamp ON)")
            self.statusBar().showMessage("Reference measured - continuous mode active")
            
            # Enable data collection and tracking
            self.start_collection_btn.setEnabled(True)
            self.track_wl_btn.setEnabled(True)
            
        else:
            self.logger.error(f"REFERENCE: Failed - only {len(ch1_data)}/{n_avg} measurements")
            self.statusBar().showMessage("Reference measurement failed")
        
        self.measuring_reference = False
        self.reference_measurements = []
        self.measure_ref_btn.setEnabled(True)
        self.measure_bg_btn.setEnabled(True)
        self.stop_measure_btn.setEnabled(False)  # Disable stop button
    
    def measure_background_complete(self):
        """Called when background measurement is complete."""
        n_avg = self.ref_averages_spin.value()
        
        # Average all collected measurements
        ch1_data = [m['ch1'] for m in self.background_measurements if m['ch1'] is not None]
        ch2_data = [m['ch2'] for m in self.background_measurements if m['ch2'] is not None]
        
        if len(ch1_data) >= n_avg and len(ch2_data) >= n_avg:
            self.background_ch1 = np.mean(ch1_data[:n_avg], axis=0)
            self.background_ch2 = np.mean(ch2_data[:n_avg], axis=0)
            self.has_background = True
            
            # Display background lines on plots (blue)
            # Use wavelengths from spectrometer (always available after connection)
            wavelengths = self.spec1_widget.wavelengths
            if wavelengths is not None:
                self.bg_curve1.setData(wavelengths, self.background_ch1)
                self.bg_curve2.setData(wavelengths, self.background_ch2)
                self.logger.info("BACKGROUND: Measurement complete (lamp OFF) - blue lines displayed")
            else:
                self.logger.warning("BACKGROUND: Wavelengths not available for plotting")
            
            self.statusBar().showMessage("Background measured - continuous mode active")
            
        else:
            self.logger.error(f"BACKGROUND: Failed - only {len(ch1_data)}/{n_avg} measurements")
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
            if not self.has_reference:
                QMessageBox.warning(self, "Error", "Please measure reference first")
                return
            
            interval_ms = int(self.collection_rate_spin.value() * 1000)
            if interval_ms < 100:
                QMessageBox.warning(self, "Error", "Minimum collection rate is 0.1s (100ms)")
                return
            
            self.data_collection_active = True
            self.collection_data = []
            self.collection_start_time = time.time()
            
            self.start_collection_btn.setText("Stop Data Collection")
            self.logger.info(f"DATA COLLECTION: Started (rate={self.collection_rate_spin.value()}s)")
            self.statusBar().showMessage(f"Data collection active ({self.collection_rate_spin.value()}s interval)")
        else:
            # Stop data collection
            self.data_collection_active = False
            self.start_collection_btn.setText("Start Data Collection")
            
            n_points = len(self.collection_data) if hasattr(self, 'collection_data') else 0
            self.logger.info(f"DATA COLLECTION: Stopped ({n_points} data points collected)")
            self.statusBar().showMessage(f"Data collection stopped ({n_points} points)")
    
    def collect_data_point(self):
        """Collect a data point during active data collection."""
        if not self.data_collection_active or not self.has_reference:
            return
        
        # Data point will be collected in on_measurement_complete
        # This is called by collection_timer at user-specified rate
        pass
    
    def open_wavelength_tracker(self):
        """Open wavelength tracking window."""
        if not self.has_reference:
            QMessageBox.warning(self, "Error", "Please measure reference first")
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
        
        # Handle reference measurement collection
        skip_normal_status = False
        if self.measuring_reference and data1 is not None and data2 is not None:
            self.reference_measurements.append({'ch1': data1, 'ch2': data2})
            n_avg = self.ref_averages_spin.value()
            n_collected = len(self.reference_measurements)
            
            self.statusBar().showMessage(f"Measuring reference ({n_collected}/{n_avg})...")
            skip_normal_status = True
            
            if n_collected >= n_avg:
                self.measure_reference_complete()
                skip_normal_status = False  # Will update status below
        
        # Handle background measurement collection
        # Check the flag BEFORE appending to avoid collecting after completion
        if self.measuring_background:
            if data1 is not None and data2 is not None:
                self.background_measurements.append({'ch1': data1, 'ch2': data2})
                n_avg = self.ref_averages_spin.value()
                n_collected = len(self.background_measurements)
                
                self.statusBar().showMessage(f"Measuring background ({n_collected}/{n_avg})...")
                skip_normal_status = True
                
                if n_collected >= n_avg:
                    self.logger.info(f"BACKGROUND: Completing measurement ({n_collected}/{n_avg})")
                    self.measure_background_complete()
                    # Explicitly verify flag is False
                    if not self.measuring_background:
                        skip_normal_status = False  # Will update status below
                        self.logger.info("BACKGROUND: Flag confirmed FALSE - will show normal status")
                    else:
                        self.logger.error("BACKGROUND: Flag still TRUE after completion - this is a bug!")
        
        # Calculate and plot Optical Density (only if both reference AND background exist)
        od_spectrum = None
        if data1 is not None and data2 is not None and wavelengths1 is not None:
            if self.has_reference and self.has_background:
                od_spectrum = self.calculate_optical_density(data1, data2)
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
        
        # Update wavelength tracker if active
        if self.wavelength_tracker_window and od_spectrum is not None:
            self.wavelength_tracker_window.update_od_value(od_spectrum, wavelengths1)
        
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
        
        # Check if it's a recoverable error (data timing issue)
        is_recoverable = "INVALID_MEAS_DATA" in error_msg
        
        if is_recoverable and self.continuous_mode:
            # Log but continue in continuous mode for timing issues
            self.logger.warning("Recoverable error in continuous mode - will retry next cycle")
            self.statusBar().showMessage(f"Warning: {error_msg[:50]}...")
        else:
            # Fatal error - stop continuous mode
            self.statusBar().showMessage(f"Error: {error_msg}")
            
            if self.continuous_mode:
                self.logger.error("Stopping continuous mode due to fatal error")
                self.continuous_timer.stop()
                self.continuous_mode = False
            else:
                QMessageBox.critical(self, "Measurement Error", error_msg)
    
    def on_measurement_finished(self):
        """Handle measurement thread finished."""
        # Allow slight delay before next measurement in continuous mode
        # This prevents overwhelming the USB bus
        pass
    
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
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            "",
            "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                # Remove .csv extension if present
                base_filename = filename.replace('.csv', '')
                
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
                    od = self.calculate_optical_density(data1, data2, wl1)
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
                
                QMessageBox.information(self, "Export Complete", "Data exported successfully (including OD)")
                
            except Exception as e:
                self.logger.error(f"Export failed: {str(e)}")
                QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")
    
    def calculate_optical_density(self, ch1_current: np.ndarray, ch2_current: np.ndarray) -> Optional[np.ndarray]:
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
                
                # Replace inf and nan with 0
                od[~np.isfinite(od)] = 0
                
            return od
            
        except Exception as e:
            self.logger.error(f"Failed to calculate OD: {e}")
            return None
    
    def clear_plots(self):
        """Clear all plots and reset reference and background."""
        self.curve1.setData([], [])
        self.curve2.setData([], [])
        self.curve_od.setData([], [])
        self.ref_curve1.setData([], [])
        self.ref_curve2.setData([], [])
        self.bg_curve1.setData([], [])
        self.bg_curve2.setData([], [])
        
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
        self.has_reference = False
        self.has_background = False
        
        # Disable buttons that require reference
        self.start_collection_btn.setEnabled(False)
        self.track_wl_btn.setEnabled(False)
        
        self.statusBar().showMessage("Plots cleared")
    
    def setup_logging(self):
        """Setup logging to file and console."""
        # Create logs directory if it doesn't exist
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"avantes_dual_{timestamp}.log"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()  # Also print to console
            ]
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
            
            # Auto-start continuous readout after connection
            QTimer.singleShot(500, self.auto_start_continuous)
        else:
            self.logger.error("AUTO-CONNECT: Failed to connect both spectrometers")
    
    def auto_start_continuous(self):
        """Automatically start continuous readout after connection."""
        self.logger.info("AUTO-START: Starting continuous readout")
        
        # Check Arduino status and enable Lamp + Avantes mode
        if self.arduino.is_connected():
            self.set_lamp_and_avantes()
            self.logger.info("AUTO-START: Arduino enabled (Lamp + Avantes)")
        else:
            self.logger.warning("AUTO-START: Arduino not reachable")
            self.arduino_status_label.setText("Status: Not Connected")
            self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Start continuous mode
        self.continuous_timer.start(50)  # 50ms polling for 10Hz Arduino triggers
        self.continuous_mode = True
        self._measurement_count = 0
        
        self.statusBar().showMessage("Continuous readout active (auto-started)")
        self.logger.info("AUTO-START: Continuous readout active (50ms polling interval)")
    
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
        
        # Stop measurement thread
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.measurement_thread.stop()
            self.measurement_thread.wait()
        
        # Close wavelength tracker
        if self.wavelength_tracker_window:
            self.wavelength_tracker_window.close()
        
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
