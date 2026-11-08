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


if __package__:
    from .avantes_dual_viewer_parts_env_bool import _bind_avantes_dual_viewer_parts_env_bool
else:
    from avantes_dual_viewer_parts_env_bool import _bind_avantes_dual_viewer_parts_env_bool

from sys import modules as _refactor_modules

if __package__:
    from .avantes_dual_viewer_methods_init_ui import _bind_avantes_dual_viewer_methods_init_ui
else:
    from avantes_dual_viewer_methods_init_ui import _bind_avantes_dual_viewer_methods_init_ui

if __package__:
    from .avantes_dual_viewer_methods_get_settings_dict import _bind_avantes_dual_viewer_methods_get_settings_dict
else:
    from avantes_dual_viewer_methods_get_settings_dict import _bind_avantes_dual_viewer_methods_get_settings_dict

if __package__:
    from .avantes_dual_viewer_methods_toggle_data_collection import _bind_avantes_dual_viewer_methods_toggle_data_collection
else:
    from avantes_dual_viewer_methods_toggle_data_collection import _bind_avantes_dual_viewer_methods_toggle_data_collection

if __package__:
    from .avantes_dual_viewer_methods_on_measurement_complete import _bind_avantes_dual_viewer_methods_on_measurement_complete
else:
    from avantes_dual_viewer_methods_on_measurement_complete import _bind_avantes_dual_viewer_methods_on_measurement_complete

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


_avantes_dual_viewer_parts_env_bool = _bind_avantes_dual_viewer_parts_env_bool(_refactor_modules[__name__])
_env_bool = _avantes_dual_viewer_parts_env_bool["_env_bool"]


WavelengthTrackerWindow = _avantes_dual_viewer_parts_env_bool["WavelengthTrackerWindow"]


ODHeatmapWindow = _avantes_dual_viewer_parts_env_bool["ODHeatmapWindow"]


CollectionSettingsDialog = _avantes_dual_viewer_parts_env_bool["CollectionSettingsDialog"]


MeasurementThread = _avantes_dual_viewer_parts_env_bool["MeasurementThread"]
del _avantes_dual_viewer_parts_env_bool


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
        self.loaded_collection_file_path = None
        self.collection_next_due_time = None
        self.collection_time_offset_s = 0.0
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
    del _avantes_dual_viewer_methods_init_ui

    _avantes_dual_viewer_methods_get_settings_dict = _bind_avantes_dual_viewer_methods_get_settings_dict(_refactor_modules[__name__])
    get_settings_dict = _avantes_dual_viewer_methods_get_settings_dict["get_settings_dict"]

    get_spectrometer_settings = _avantes_dual_viewer_methods_get_settings_dict["get_spectrometer_settings"]

    apply_settings_dict = _avantes_dual_viewer_methods_get_settings_dict["apply_settings_dict"]

    apply_spectrometer_settings = _avantes_dual_viewer_methods_get_settings_dict["apply_spectrometer_settings"]

    load_settings_json = _avantes_dual_viewer_methods_get_settings_dict["load_settings_json"]

    load_settings_from_file = _avantes_dual_viewer_methods_get_settings_dict["load_settings_from_file"]

    save_settings_json_as = _avantes_dual_viewer_methods_get_settings_dict["save_settings_json_as"]

    update_settings_json = _avantes_dual_viewer_methods_get_settings_dict["update_settings_json"]

    write_settings_json = _avantes_dual_viewer_methods_get_settings_dict["write_settings_json"]

    is_lamp_enabled = _avantes_dual_viewer_methods_get_settings_dict["is_lamp_enabled"]

    is_avantes_enabled = _avantes_dual_viewer_methods_get_settings_dict["is_avantes_enabled"]

    set_lamp_on = _avantes_dual_viewer_methods_get_settings_dict["set_lamp_on"]

    set_lamp_off = _avantes_dual_viewer_methods_get_settings_dict["set_lamp_off"]

    set_lamp_and_avantes = _avantes_dual_viewer_methods_get_settings_dict["set_lamp_and_avantes"]

    set_avantes_only = _avantes_dual_viewer_methods_get_settings_dict["set_avantes_only"]

    set_arduino_off = _avantes_dual_viewer_methods_get_settings_dict["set_arduino_off"]

    toggle_continuous_readout = _avantes_dual_viewer_methods_get_settings_dict["toggle_continuous_readout"]

    stop_live_preview = _avantes_dual_viewer_methods_get_settings_dict["stop_live_preview"]

    stop_measurement = _avantes_dual_viewer_methods_get_settings_dict["stop_measurement"]

    measure_reference = _avantes_dual_viewer_methods_get_settings_dict["measure_reference"]

    measure_background = _avantes_dual_viewer_methods_get_settings_dict["measure_background"]

    measure_reference_complete = _avantes_dual_viewer_methods_get_settings_dict["measure_reference_complete"]

    set_zero_baseline_from_current = _avantes_dual_viewer_methods_get_settings_dict["set_zero_baseline_from_current"]

    measure_background_complete = _avantes_dual_viewer_methods_get_settings_dict["measure_background_complete"]
    del _avantes_dual_viewer_methods_get_settings_dict

    _avantes_dual_viewer_methods_toggle_data_collection = _bind_avantes_dual_viewer_methods_toggle_data_collection(_refactor_modules[__name__])
    toggle_data_collection = _avantes_dual_viewer_methods_toggle_data_collection["toggle_data_collection"]

    collect_data_point = _avantes_dual_viewer_methods_toggle_data_collection["collect_data_point"]

    schedule_next_collection_point = _avantes_dual_viewer_methods_toggle_data_collection["schedule_next_collection_point"]

    on_collection_rate_changed = _avantes_dual_viewer_methods_toggle_data_collection["on_collection_rate_changed"]

    schedule_collection_due_time = _avantes_dual_viewer_methods_toggle_data_collection["schedule_collection_due_time"]

    prepare_lamp_for_collection = _avantes_dual_viewer_methods_toggle_data_collection["prepare_lamp_for_collection"]

    format_seconds_for_countdown = _avantes_dual_viewer_methods_toggle_data_collection["format_seconds_for_countdown"]

    update_collection_countdown_label = _avantes_dual_viewer_methods_toggle_data_collection["update_collection_countdown_label"]

    browse_save_folder = _avantes_dual_viewer_methods_toggle_data_collection["browse_save_folder"]

    update_loaded_collection_label = _avantes_dual_viewer_methods_toggle_data_collection["update_loaded_collection_label"]

    ask_collection_start_mode = _avantes_dual_viewer_methods_toggle_data_collection["ask_collection_start_mode"]

    suggest_new_collection_file_path = _avantes_dual_viewer_methods_toggle_data_collection["suggest_new_collection_file_path"]

    choose_new_collection_file_path = _avantes_dual_viewer_methods_toggle_data_collection["choose_new_collection_file_path"]

    can_resume_collection_wavelengths = _avantes_dual_viewer_methods_toggle_data_collection["can_resume_collection_wavelengths"]

    get_resume_collection_time_offset = _avantes_dual_viewer_methods_toggle_data_collection["get_resume_collection_time_offset"]

    load_collection_dat = _avantes_dual_viewer_methods_toggle_data_collection["load_collection_dat"]

    load_collection_dat_file = _avantes_dual_viewer_methods_toggle_data_collection["load_collection_dat_file"]

    update_analysis_buttons = _avantes_dual_viewer_methods_toggle_data_collection["update_analysis_buttons"]

    clear_zero_baseline = _avantes_dual_viewer_methods_toggle_data_collection["clear_zero_baseline"]

    reset_od_heatmap = _avantes_dual_viewer_methods_toggle_data_collection["reset_od_heatmap"]

    update_od_heatmap = _avantes_dual_viewer_methods_toggle_data_collection["update_od_heatmap"]

    render_od_heatmap = _avantes_dual_viewer_methods_toggle_data_collection["render_od_heatmap"]

    toggle_od_heatmap_window = _avantes_dual_viewer_methods_toggle_data_collection["toggle_od_heatmap_window"]

    show_od_heatmap_window = _avantes_dual_viewer_methods_toggle_data_collection["show_od_heatmap_window"]

    get_export_base_path = _avantes_dual_viewer_methods_toggle_data_collection["get_export_base_path"]

    open_wavelength_tracker = _avantes_dual_viewer_methods_toggle_data_collection["open_wavelength_tracker"]
    del _avantes_dual_viewer_methods_toggle_data_collection

    _avantes_dual_viewer_methods_on_measurement_complete = _bind_avantes_dual_viewer_methods_on_measurement_complete(_refactor_modules[__name__])
    on_measurement_complete = _avantes_dual_viewer_methods_on_measurement_complete["on_measurement_complete"]

    on_measurement_error = _avantes_dual_viewer_methods_on_measurement_complete["on_measurement_error"]

    on_measurement_finished = _avantes_dual_viewer_methods_on_measurement_complete["on_measurement_finished"]

    save_collection_point = _avantes_dual_viewer_methods_on_measurement_complete["save_collection_point"]

    set_controls_enabled = _avantes_dual_viewer_methods_on_measurement_complete["set_controls_enabled"]

    export_data = _avantes_dual_viewer_methods_on_measurement_complete["export_data"]

    calculate_optical_density = _avantes_dual_viewer_methods_on_measurement_complete["calculate_optical_density"]

    get_demo_species_od = _avantes_dual_viewer_methods_on_measurement_complete["get_demo_species_od"]

    clear_plots = _avantes_dual_viewer_methods_on_measurement_complete["clear_plots"]

    setup_logging = _avantes_dual_viewer_methods_on_measurement_complete["setup_logging"]


    auto_connect_spectrometers = _avantes_dual_viewer_methods_on_measurement_complete["auto_connect_spectrometers"]

    auto_connect_spec2 = _avantes_dual_viewer_methods_on_measurement_complete["auto_connect_spec2"]

    auto_start_continuous = _avantes_dual_viewer_methods_on_measurement_complete["auto_start_continuous"]

    closeEvent = _avantes_dual_viewer_methods_on_measurement_complete["closeEvent"]
    del _avantes_dual_viewer_methods_on_measurement_complete


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
