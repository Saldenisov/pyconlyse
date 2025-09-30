# Keysight 33509B Client Widget
# Mirrors core controls of the web UI: Output, Waveform, Frequency, Amplitude (Vpp), DC Offset

import sys
from pathlib import Path

import tango
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
from taurus import Device
from taurus.external.qt import Qt as TQt

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType

# Optional: warn/connection helpers (same pattern as other widgets)
fixes_path = Path(__file__).resolve().parents[3] / "fixes"
if str(fixes_path) not in sys.path:
    sys.path.append(str(fixes_path))
try:
    from taurus_warnings_fix import (
        check_device_connection,
        suppress_taurus_deprecation_warnings,
    )
except Exception:  # fallback if fixes missing
    def check_device_connection(_):
        return True

    def suppress_taurus_deprecation_warnings():
        pass


class Keysight_33509B(DS_General_Widget):
    """UI widget for Keysight 33509B DeviceServer.

    Attributes expected on the DS:
    - idn (str, RO)
    - output_enabled (int, RW)
    - waveform (str, RW)
    - frequency_hz (float, RW)
    - amplitude_vpp (float, RW)
    - offset_v (float, RW)
    """

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        suppress_taurus_deprecation_warnings()
        self._updating_from_device = False
        super().__init__(device_name, parent, vis_type)

    # Layout registrations
    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f"layout_controls_{self.dev_name}", TQt.QGridLayout())

    def register_min_layouts(self):
        super().register_min_layouts()
        setattr(self, f"layout_controls_{self.dev_name}", TQt.QGridLayout())

    def before_ds(self):
        # Pre-create values
        self._cached = {
            "idn": "",
            "output_enabled": 0,
            "burst_enabled": 0,
            "waveform": "SIN",
            "frequency_hz": 1000.0,
            "amplitude_vpp": 1.0,
            "offset_v": 0.0,
        }

    def register_DS_full(self, group_number=1):
        super().register_DS_full(group_number)
        self._build_common_ui(group_number, minimal=False)

    def register_DS_min(self, group_number=1):
        super().register_DS_min(group_number)
        self._build_common_ui(group_number, minimal=True)

    def _build_common_ui(self, group_number: int, minimal: bool):
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")

        lo_group: TQt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: TQt.QVBoxLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: TQt.QHBoxLayout = getattr(self, f"layout_status_{dev_name}")
        lo_controls: TQt.QGridLayout = getattr(self, f"layout_controls_{dev_name}")

        # Status line with LED + name + Always on + Update button
        self.set_state_status(short=True)

        # Controls group
        group_box = QtWidgets.QGroupBox("Channel Controls")
        group_box.setLayout(lo_controls)

        # Row 0: IDN display
        label_idn = QtWidgets.QLabel("Instrument:")
        self.txt_idn = QtWidgets.QLabel("…")
        self.txt_idn.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lo_controls.addWidget(label_idn, 0, 0)
        lo_controls.addWidget(self.txt_idn, 0, 1, 1, 3)

        # Row 1: Output toggle
        self.chk_output = QtWidgets.QCheckBox("Output ON")
        self.chk_output.toggled.connect(self._on_output_toggled)
        lo_controls.addWidget(QtWidgets.QLabel("Output:"), 1, 0)
        lo_controls.addWidget(self.chk_output, 1, 1)

        # Row 1b: Burst toggle
        self.chk_burst = QtWidgets.QCheckBox("Burst ON")
        self.chk_burst.toggled.connect(self._on_burst_toggled)
        lo_controls.addWidget(QtWidgets.QLabel("Burst:"), 1, 2)
        lo_controls.addWidget(self.chk_burst, 1, 3)

        # Row 2: Waveform selector
        self.cmb_waveform = QtWidgets.QComboBox()
        self.cmb_waveform.addItems(["SIN", "SQU", "RAMP", "NOIS", "DC", "USER"])  # common set
        self.cmb_waveform.currentTextChanged.connect(self._on_waveform_changed)
        lo_controls.addWidget(QtWidgets.QLabel("Waveform:"), 2, 0)
        lo_controls.addWidget(self.cmb_waveform, 2, 1)

        # Row 3: Frequency
        self.ed_freq = QtWidgets.QLineEdit()
        self.ed_freq.setPlaceholderText("Hz")
        self.ed_freq.setValidator(QDoubleValidator(0.000001, 2.0e7, 6))  # up to ~20 MHz
        self.ed_freq.editingFinished.connect(self._on_freq_changed)
        lo_controls.addWidget(QtWidgets.QLabel("Frequency (Hz):"), 3, 0)
        lo_controls.addWidget(self.ed_freq, 3, 1)

        # Row 4: Amplitude Vpp
        self.ed_amp = QtWidgets.QLineEdit()
        self.ed_amp.setPlaceholderText("Vpp")
        self.ed_amp.setValidator(QDoubleValidator(0.001, 20.0, 4))  # up to 20 Vpp
        self.ed_amp.editingFinished.connect(self._on_amp_changed)
        lo_controls.addWidget(QtWidgets.QLabel("Amplitude (Vpp):"), 4, 0)
        lo_controls.addWidget(self.ed_amp, 4, 1)

        # Row 5: DC Offset
        self.ed_off = QtWidgets.QLineEdit()
        self.ed_off.setPlaceholderText("V")
        self.ed_off.setValidator(QDoubleValidator(-10.0, 10.0, 4))
        self.ed_off.editingFinished.connect(self._on_off_changed)
        lo_controls.addWidget(QtWidgets.QLabel("Offset (V):"), 5, 0)
        lo_controls.addWidget(self.ed_off, 5, 1)

        # Buttons
        btn_refresh = QtWidgets.QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_from_device)
        btn_apply = QtWidgets.QPushButton("Apply All")
        btn_apply.clicked.connect(self._apply_all)
        lo_controls.addWidget(btn_refresh, 6, 0)
        lo_controls.addWidget(btn_apply, 6, 1)

        if minimal:
            # In minimal mode, show only output and a condensed row
            self.cmb_waveform.setVisible(False)
            self.ed_freq.setVisible(False)
            self.ed_amp.setVisible(False)
            self.ed_off.setVisible(False)

        # Add layouts
        lo_device.addLayout(lo_status)
        lo_device.addWidget(group_box)
        lo_group.addLayout(lo_device)

        # Subscribe to attribute changes when possible
        try:
            ds.subscribe_event("output_enabled", tango.EventType.CHANGE_EVENT, self._attr_listener)
            ds.subscribe_event("burst_enabled", tango.EventType.CHANGE_EVENT, self._attr_listener)
            ds.subscribe_event("waveform", tango.EventType.CHANGE_EVENT, self._attr_listener)
            ds.subscribe_event("frequency_hz", tango.EventType.CHANGE_EVENT, self._attr_listener)
            ds.subscribe_event("amplitude_vpp", tango.EventType.CHANGE_EVENT, self._attr_listener)
            ds.subscribe_event("offset_v", tango.EventType.CHANGE_EVENT, self._attr_listener)
            ds.subscribe_event("idn", tango.EventType.CHANGE_EVENT, self._attr_listener)
        except Exception:
            pass

        # Initial refresh
        self._refresh_from_device()

    # Event listeners and UI sync
    def _attr_listener(self, ev):
        try:
            if ev.err:
                return
            name = ev.attr_name.split("/")[-1]
            val = ev.attr_value.value
            self._cached[name] = val
            self._update_ui_from_cache()
        except Exception:
            pass

    def _update_ui_from_cache(self):
        self._updating_from_device = True
        try:
            self.txt_idn.setText(str(self._cached.get("idn", "")))
            self.chk_output.setChecked(bool(int(self._cached.get("output_enabled", 0))))
            self.chk_burst.setChecked(bool(int(self._cached.get("burst_enabled", 0))))
            wf = str(self._cached.get("waveform", "SIN")).upper()
            idx = self.cmb_waveform.findText(wf)
            if idx >= 0:
                self.cmb_waveform.setCurrentIndex(idx)
            self.ed_freq.setText(str(self._cached.get("frequency_hz", 0.0)))
            self.ed_amp.setText(str(self._cached.get("amplitude_vpp", 0.0)))
            self.ed_off.setText(str(self._cached.get("offset_v", 0.0)))
        finally:
            self._updating_from_device = False

    def _refresh_from_device(self):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            # Attempt reads; tolerate failures when device offline
            for attr in ("idn", "output_enabled", "burst_enabled", "waveform", "frequency_hz", "amplitude_vpp", "offset_v"):
                try:
                    self._cached[attr] = ds.read_attribute(attr).value
                except Exception:
                    pass
            self._update_ui_from_cache()
        except Exception:
            pass

    # Apply handlers
    def _on_output_toggled(self, checked: bool):
        if self._updating_from_device:
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.write_attribute("output_enabled", 1 if checked else 0)
        except Exception:
            pass

    def _on_waveform_changed(self, text: str):
        if self._updating_from_device:
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.write_attribute("waveform", str(text).upper())
        except Exception:
            pass

    def _on_burst_toggled(self, checked: bool):
        if self._updating_from_device:
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.write_attribute("burst_enabled", 1 if checked else 0)
        except Exception:
            pass

    def _on_freq_changed(self):
        if self._updating_from_device:
            return
        try:
            val = float(self.ed_freq.text())
        except Exception:
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.write_attribute("frequency_hz", float(val))
        except Exception:
            pass

    def _on_amp_changed(self):
        if self._updating_from_device:
            return
        try:
            val = float(self.ed_amp.text())
        except Exception:
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.write_attribute("amplitude_vpp", float(val))
        except Exception:
            pass

    def _on_off_changed(self):
        if self._updating_from_device:
            return
        try:
            val = float(self.ed_off.text())
        except Exception:
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.write_attribute("offset_v", float(val))
        except Exception:
            pass

    def _apply_all(self):
        # Push all UI values to the device in a safe order
        self._on_waveform_changed(self.cmb_waveform.currentText())
        self._on_freq_changed()
        self._on_amp_changed()
        self._on_off_changed()

    # Unused abstract requirement
    def set_the_control_value(self, value):
        pass
