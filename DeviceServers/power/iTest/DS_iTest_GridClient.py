# Enhanced iTest PSU Grid Client - Multi-slot control similar to OWIS multi-axis approach
import json
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDoubleSpinBox, QCheckBox, QGroupBox, QFrame,
    QMessageBox, QProgressBar, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpacerItem, QSizePolicy, QSlider, QTabWidget, QScrollArea
)
from taurus import Device


@dataclass
class SlotInfo:
    """Information about a single PSU slot"""
    slot: int
    name: str
    model: str = ""
    current_setpoint: float = 0.0
    measured_current: float = 0.0
    measured_voltage: float = 0.0
    output_enabled: bool = False
    error: str = ""


class SlotControlWidget(QFrame):
    """Individual slot control widget with comprehensive interface"""
    
    value_changed = pyqtSignal(int, str, object)  # slot, parameter, value
    
    def __init__(self, slot_info: SlotInfo, safe_min: float = -5.0, safe_max: float = 5.0, parent=None):
        super().__init__(parent)
        self.slot_info = slot_info
        self.safe_min = safe_min
        self.safe_max = safe_max
        self._setup_ui()
        self._updating = False
        
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(2)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Header with slot name and model
        header = QHBoxLayout()
        self.name_label = QLabel(f"<b>{self.slot_info.name}</b>")
        self.model_label = QLabel(f"({self.slot_info.model})" if self.slot_info.model else "")
        self.model_label.setStyleSheet("color: gray; font-size: 10px;")
        header.addWidget(self.name_label)
        header.addWidget(self.model_label)
        header.addStretch()
        layout.addLayout(header)
        
        # Output control section
        output_group = QGroupBox("Output Control")
        output_layout = QVBoxLayout(output_group)
        
        # Output enable/disable buttons
        button_layout = QHBoxLayout()
        self.btn_on = QPushButton("ON")
        self.btn_off = QPushButton("OFF")
        self.btn_on.setCheckable(True)
        self.btn_off.setCheckable(True)
        self.btn_on.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        self.btn_off.setStyleSheet("QPushButton:checked { background-color: #F44336; color: white; }")
        
        self.btn_on.clicked.connect(lambda: self._on_output_control(True))
        self.btn_off.clicked.connect(lambda: self._on_output_control(False))
        
        button_layout.addWidget(self.btn_on)
        button_layout.addWidget(self.btn_off)
        output_layout.addLayout(button_layout)
        
        # Status indicator
        self.status_label = QLabel("OFF")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("padding: 4px; border: 1px solid gray; border-radius: 3px;")
        output_layout.addWidget(self.status_label)
        
        layout.addWidget(output_group)
        
        # Current control section
        current_group = QGroupBox("Current Control [A]")
        current_layout = QVBoxLayout(current_group)
        
        # Current setpoint with quick adjustment buttons
        setpoint_layout = QHBoxLayout()
        self.btn_dec_coarse = QPushButton("-0.1")
        self.btn_dec_fine = QPushButton("-0.01")
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setDecimals(4)
        self.current_spin.setSingleStep(0.01)
        self.current_spin.setRange(self.safe_min, self.safe_max)
        self.current_spin.setValue(0.0)
        self.btn_inc_fine = QPushButton("+0.01")
        self.btn_inc_coarse = QPushButton("+0.1")
        
        for btn in [self.btn_dec_coarse, self.btn_dec_fine, self.btn_inc_fine, self.btn_inc_coarse]:
            btn.setMaximumWidth(50)
        
        self.btn_dec_coarse.clicked.connect(lambda: self._adjust_current(-0.1))
        self.btn_dec_fine.clicked.connect(lambda: self._adjust_current(-0.01))
        self.btn_inc_fine.clicked.connect(lambda: self._adjust_current(0.01))
        self.btn_inc_coarse.clicked.connect(lambda: self._adjust_current(0.1))
        
        self.current_spin.editingFinished.connect(self._on_current_changed)
        
        setpoint_layout.addWidget(self.btn_dec_coarse)
        setpoint_layout.addWidget(self.btn_dec_fine)
        setpoint_layout.addWidget(self.current_spin, 1)
        setpoint_layout.addWidget(self.btn_inc_fine)
        setpoint_layout.addWidget(self.btn_inc_coarse)
        current_layout.addLayout(setpoint_layout)
        
        # Current slider for quick adjustments
        self.current_slider = QSlider(Qt.Horizontal)
        self.current_slider.setRange(int(self.safe_min * 1000), int(self.safe_max * 1000))
        self.current_slider.setValue(0)
        self.current_slider.valueChanged.connect(self._on_slider_changed)
        current_layout.addWidget(self.current_slider)
        
        layout.addWidget(current_group)
        
        # Measurements section
        meas_group = QGroupBox("Measurements")
        meas_layout = QVBoxLayout(meas_group)
        
        self.measured_current_label = QLabel("I: -- A")
        self.measured_voltage_label = QLabel("V: -- V")
        self.measured_power_label = QLabel("P: -- W")
        
        for label in [self.measured_current_label, self.measured_voltage_label, self.measured_power_label]:
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("padding: 2px; font-family: monospace;")
            meas_layout.addWidget(label)
        
        layout.addWidget(meas_group)
        
        # Error display
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; font-size: 10px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        
        layout.addStretch()
        
    def _adjust_current(self, delta: float):
        current_val = self.current_spin.value()
        new_val = max(self.safe_min, min(self.safe_max, current_val + delta))
        self.current_spin.setValue(new_val)
        self._on_current_changed()
        
    def _on_current_changed(self):
        if not self._updating:
            value = self.current_spin.value()
            self.current_slider.setValue(int(value * 1000))
            self.value_changed.emit(self.slot_info.slot, "current", value)
            
    def _on_slider_changed(self, value):
        if not self._updating:
            current_val = value / 1000.0
            self.current_spin.setValue(current_val)
            self.value_changed.emit(self.slot_info.slot, "current", current_val)
            
    def _on_output_control(self, enable: bool):
        if not self._updating:
            self.value_changed.emit(self.slot_info.slot, "output", enable)
            
    def update_values(self, slot_info: SlotInfo):
        """Update widget with new slot information"""
        self._updating = True
        try:
            self.slot_info = slot_info
            
            # Update output status
            if slot_info.output_enabled:
                self.btn_on.setChecked(True)
                self.btn_off.setChecked(False)
                self.status_label.setText("ON")
                self.status_label.setStyleSheet("padding: 4px; border: 1px solid #4CAF50; border-radius: 3px; background-color: #E8F5E8; color: #4CAF50;")
                self.setStyleSheet("QFrame { border: 2px solid #4CAF50; }")
            else:
                self.btn_on.setChecked(False)
                self.btn_off.setChecked(True)
                self.status_label.setText("OFF")
                self.status_label.setStyleSheet("padding: 4px; border: 1px solid #F44336; border-radius: 3px; background-color: #FFEBEE; color: #F44336;")
                self.setStyleSheet("QFrame { border: 2px solid #CCCCCC; }")
            
            # Update current values if not being edited by user
            if not self.current_spin.hasFocus():
                self.current_spin.setValue(slot_info.current_setpoint)
                self.current_slider.setValue(int(slot_info.current_setpoint * 1000))
            
            # Update measurements
            self.measured_current_label.setText(f"I: {slot_info.measured_current:.4f} A")
            self.measured_voltage_label.setText(f"V: {slot_info.measured_voltage:.3f} V")
            
            # Calculate and display power
            power = slot_info.measured_current * slot_info.measured_voltage
            self.measured_power_label.setText(f"P: {power:.3f} W")
            
            # Update error display
            if slot_info.error:
                self.error_label.setText(f"Error: {slot_info.error}")
                self.error_label.show()
            else:
                self.error_label.hide()
                
        finally:
            self._updating = False


class ITestGridClient(QMainWindow):
    """
    Enhanced Grid Client for iTest PSU - Multi-slot control similar to OWIS approach.
    
    Features:
    - Grid layout for multiple slots (flexible: 1-4 slots per row based on total count)
    - One Device Server controls multiple slots (like OWIS DS controls 4+ cards)
    - Comprehensive per-slot controls
    - Live monitoring and updates
    - Batch operations across slots
    - Scalable for any number of slots (8, 16, 32, etc.)
    """
    
    def __init__(self, device_name: str, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.slot_widgets: Dict[int, SlotControlWidget] = {}
        self.device: Optional[Device] = None
        self.safe_min = -5.0
        self.safe_max = 5.0
        
        self.setWindowTitle(f"iTest PSU Grid Client - {device_name}")
        self.setMinimumSize(1200, 800)
        
        self._setup_ui()
        self._connect_device()
        self._setup_timer()
        
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Title and connection status
        header_layout = QHBoxLayout()
        title_label = QLabel(f"<h2>iTest PSU: {self.device_name}</h2>")
        self.connection_label = QLabel("Connecting...")
        self.connection_label.setAlignment(Qt.AlignRight)
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.connection_label)
        main_layout.addLayout(header_layout)
        
        # Control toolbar
        toolbar_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_data)
        
        self.all_on_btn = QPushButton("All ON")
        self.all_on_btn.clicked.connect(lambda: self._batch_operation("output", True))
        
        self.all_off_btn = QPushButton("All OFF")
        self.all_off_btn.clicked.connect(lambda: self._batch_operation("output", False))
        
        self.zero_all_btn = QPushButton("Zero All")
        self.zero_all_btn.clicked.connect(lambda: self._batch_operation("current", 0.0))
        
        toolbar_layout.addWidget(self.refresh_btn)
        
        # Add separator (vertical line)
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        toolbar_layout.addWidget(separator)
        
        toolbar_layout.addWidget(self.all_on_btn)
        toolbar_layout.addWidget(self.all_off_btn)
        toolbar_layout.addWidget(self.zero_all_btn)
        toolbar_layout.addStretch()
        
        # Status summary
        self.status_summary = QLabel("Ready")
        toolbar_layout.addWidget(self.status_summary)
        
        main_layout.addLayout(toolbar_layout)
        
        # Tabbed area: one slot per tab (NETIO-like robustness with better per-slot focus)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, 1)  # Take most space
        
    def _connect_device(self):
        """Connect to the Tango device"""
        try:
            self.device = Device(self.device_name)
            # Set longer timeout for slow devices
            self.device.set_timeout_millis(10000)  # 10 seconds instead of 3
            
            # Read safety limits
            try:
                props = self.device.get_property(["SafeCurrentMin", "SafeCurrentMax"])
                if "SafeCurrentMin" in props and props["SafeCurrentMin"]:
                    self.safe_min = float(props["SafeCurrentMin"][0])
                if "SafeCurrentMax" in props and props["SafeCurrentMax"]:
                    self.safe_max = float(props["SafeCurrentMax"][0])
            except Exception as e:
                print(f"Warning: Could not read safety limits: {e}")
            
            self.connection_label.setText("✓ Connected")
            self.connection_label.setStyleSheet("color: green;")
            
            # Initial data refresh
            self._refresh_data()
            
        except Exception as e:
            self.connection_label.setText("✗ Connection Failed")
            self.connection_label.setStyleSheet("color: red;")
            error_msg = str(e)
            if "Timeout" in error_msg or "TimedOut" in error_msg:
                QMessageBox.critical(self, "Device Timeout Error", 
                    f"Device {self.device_name} is not responding.\n\n"
                    f"This usually means:\n"
                    f"• The device server is hung/stuck\n"
                    f"• The hardware is not responding\n"
                    f"• Network connectivity issues\n\n"
                    f"Try restarting the device server:\n"
                    f"DS_itest_psu/1_iTest")
            else:
                QMessageBox.critical(self, "Connection Error", f"Failed to connect to {self.device_name}:\n{e}")
            
    def _setup_timer(self):
        """Setup periodic updates"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh_data)
        self.update_timer.start(1000)  # Update every second
        
    def _refresh_data(self):
        """Refresh data from device and update UI"""
        if not self.device:
            return

        def _build_placeholder_slot_infos() -> List[SlotInfo]:
            # Try to determine slot count from attributes/properties
            count = 0
            try:
                try:
                    ids_attr = self.device.read_attribute("ids")
                    ids_val = list(getattr(ids_attr, "value", []) or [])
                    count = len(ids_val)
                except Exception:
                    pass
                if not count:
                    try:
                        ch_attr = self.device.read_attribute("Channels")
                        count = int(getattr(ch_attr, "value", 0) or 0)
                    except Exception:
                        pass
                if not count:
                    try:
                        props = self.device.get_property(["ChannelsPerRack"]) or {}
                        arr = props.get("ChannelsPerRack") or []
                        count = int(arr[0]) if arr else 0
                    except Exception:
                        pass
                if not count:
                    count = 8
            except Exception:
                count = 8
            infos: List[SlotInfo] = []
            for i in range(1, count + 1):
                infos.append(
                    SlotInfo(
                        slot=i,
                        name=f"slot_{i}",
                        model="",
                        current_setpoint=0.0,
                        measured_current=0.0,
                        measured_voltage=0.0,
                        output_enabled=False,
                        error="(no live data)"
                    )
                )
            return infos

        try:
            # Get all outputs status from DS (best-effort)
            raw_data = self.device.command_inout("GetAllOutputs")
            outputs_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            # If DS returns empty or invalid data, create placeholders
            if not outputs_data or not isinstance(outputs_data, (list, tuple)):
                slot_infos = _build_placeholder_slot_infos()
            else:
                # Convert to SlotInfo objects
                slot_infos = []
                for data in outputs_data:
                    slot_infos.append(
                        SlotInfo(
                            slot=data.get("slot", data.get("channel", 1)),
                            name=data.get("name", f"Slot {data.get('slot', data.get('channel', 1))}"),
                            model=data.get("model", ""),
                            current_setpoint=data.get("current_setpoint", 0.0) or 0.0,
                            measured_current=data.get("measured_current", 0.0) or 0.0,
                            measured_voltage=data.get("measured_voltage", 0.0) or 0.0,
                            output_enabled=bool(data.get("output_enabled", False)),
                            error=data.get("error", "")
                        )
                    )

            # Update or create slot tabs
            self._update_slot_tabs(slot_infos)

            # Update status summary
            total_slots = len(slot_infos)
            active_slots = sum(1 for s in slot_infos if s.output_enabled)
            total_current = sum(s.measured_current for s in slot_infos)
            self.status_summary.setText(
                f"Slots: {total_slots} | Active: {active_slots} | Total Current: {total_current:.3f} A"
            )

        except Exception as e:
            # Build placeholders so UI still shows fully
            slot_infos = _build_placeholder_slot_infos()
            self._update_slot_tabs(slot_infos)
            self.status_summary.setText(f"Slots: {len(slot_infos)} | Note: {e}")
            
    def _update_slot_tabs(self, slot_infos: List[SlotInfo]):
        """Update or create one tab per slot with a SlotControlWidget inside."""
        # Build a mapping from slot->index for existing tabs
        existing_tabs = {}
        for idx in range(self.tab_widget.count()):
            w = self.tab_widget.widget(idx)
            if hasattr(w, "slot_info"):
                existing_tabs[getattr(w, "slot_info").slot] = idx

        desired_slots = [s.slot for s in slot_infos]

        # Remove tabs for slots that no longer exist
        for slot in list(existing_tabs.keys()):
            if slot not in desired_slots:
                idx = existing_tabs[slot]
                self.tab_widget.removeTab(idx)
                existing_tabs.pop(slot, None)
                if slot in self.slot_widgets:
                    try:
                        self.slot_widgets[slot].setParent(None)
                    except Exception:
                        pass
                    self.slot_widgets.pop(slot, None)
                # Rebuild mapping after removal
                existing_tabs = {}
                for j in range(self.tab_widget.count()):
                    w = self.tab_widget.widget(j)
                    if hasattr(w, "slot_info"):
                        existing_tabs[getattr(w, "slot_info").slot] = j

        # Add/update tabs for desired slots
        for slot_info in slot_infos:
            if slot_info.slot not in self.slot_widgets:
                widget = SlotControlWidget(slot_info, self.safe_min, self.safe_max)
                widget.value_changed.connect(self._on_slot_value_changed)
                self.slot_widgets[slot_info.slot] = widget
                tab_label = slot_info.name or f"slot_{slot_info.slot}"
                self.tab_widget.addTab(widget, tab_label)
            else:
                self.slot_widgets[slot_info.slot].update_values(slot_info)
                # Update tab label if name changed
                try:
                    idx = existing_tabs.get(slot_info.slot)
                    if idx is not None:
                        tab_label = slot_info.name or f"slot_{slot_info.slot}"
                        self.tab_widget.setTabText(idx, tab_label)
                except Exception:
                    pass
                
    def _on_slot_value_changed(self, slot: int, parameter: str, value):
        """Handle value change from slot widget"""
        if not self.device:
            return
            
        slot_info = None
        for widget in self.slot_widgets.values():
            if widget.slot_info.slot == slot:
                slot_info = widget.slot_info
                break
                
        if not slot_info:
            return
            
        try:
            if parameter == "current":
                self.device.command_inout("SetOutputCurrent", (slot_info.name, float(value)))
            elif parameter == "output":
                if bool(value):
                    self.device.command_inout("OutputOn", slot_info.name)
                else:
                    self.device.command_inout("OutputOff", slot_info.name)
        except Exception as e:
            QMessageBox.warning(self, "Control Error", f"Failed to set {parameter} on {slot_info.name}:\n{e}")
            
    def _batch_operation(self, operation: str, value):
        """Perform operation on all slots"""
        if not self.device:
            return
            
        reply = QMessageBox.question(
            self, 
            "Batch Operation", 
            f"Apply {operation}={value} to all slots?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        errors = []
        if operation == "output":
            # Prefer DS batch command to reduce per-slot traffic
            try:
                try:
                    ids_attr = self.device.read_attribute("ids")
                    ids = list(ids_attr.value) if hasattr(ids_attr, "value") else list(ids_attr)
                except Exception:
                    # Fallback: infer length from current widgets
                    ids = sorted([w.slot_info.slot for w in self.slot_widgets.values()])
                outputs = [1 if bool(value) else 0] * len(ids)
                self.device.command_inout("set_channels_states", outputs)
                # Quick refresh after batch
                self._refresh_data()
                return
            except Exception as e:
                errors.append(f"Batch set failed: {e}")
                # Fallback to per-slot loop below
        
        # Fallback: per-slot loop
        for widget in self.slot_widgets.values():
            try:
                slot_info = widget.slot_info
                if operation == "current":
                    self.device.command_inout("SetOutputCurrent", (slot_info.name, float(value)))
                elif operation == "output":
                    if bool(value):
                        self.device.command_inout("OutputOn", slot_info.name)
                    else:
                        self.device.command_inout("OutputOff", slot_info.name)
            except Exception as e:
                errors.append(f"{slot_info.name}: {e}")
                
        if errors:
            QMessageBox.warning(self, "Batch Operation Errors", "\n".join(errors[:5]) + ("..." if len(errors) > 5 else ""))


def main():
    """Main entry point for standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="iTest PSU Grid Client")
    parser.add_argument("device_name", help="Tango device name (e.g., domain/family/member)")
    parser.add_argument("--standalone", action="store_true", help="Run as standalone application")
    
    args = parser.parse_args()
    
    if args.standalone:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Modern look
        
        # Apply dark theme
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))
        app.setPalette(palette)
        
        window = ITestGridClient(args.device_name)
        window.show()
        
        sys.exit(app.exec_())
    else:
        # For integration with existing frameworks
        return ITestGridClient


if __name__ == "__main__":
    main()