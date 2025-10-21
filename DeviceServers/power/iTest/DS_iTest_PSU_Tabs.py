#!/usr/bin/env python3
"""
Tabbed iTest PSU client widget: 2 x 4 layout, per-slot current control and on/off.

- +/- buttons adjust setpoint by step (default 0.01 A)
- Right-click on +/- opens a menu to change step to 0.001 / 0.01 / 0.1 / 1.0 A
- Uses Tango events for 'states', 'names', and 'currents_meas' to refresh UI
"""
from __future__ import annotations

from functools import partial
from typing import List

import tango
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from taurus import Device

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType

try:
    from fixes.taurus_warnings_fix import (
        check_device_connection,
        suppress_taurus_deprecation_warnings,
    )
except Exception:
    def check_device_connection(ds: Device) -> bool:
        try:
            _ = ds.state
            return True
        except Exception:
            return False

    def suppress_taurus_deprecation_warnings():
        pass


class Itest_PSU(DS_General_Widget):
    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        suppress_taurus_deprecation_warnings()
        super().__init__(device_name, parent, vis_type)

    def before_ds(self):
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")
        self.slot_count = 8
        self.names: List[str] = [f"Slot {i}" for i in range(1, self.slot_count + 1)]
        self.states: List[int] = [0] * self.slot_count
        self.currents_meas: List[float] = [0.0] * self.slot_count
        self.currents_sp: List[float] = [0.0] * self.slot_count
        self.step = 0.01
        self._slot_steps: dict[int, float] = {}
        self._controls: List[dict] = []  # per-slot widgets
        self._last_setpoint_time: dict[int, float] = {}  # Debouncing timestamps

        if check_device_connection(ds):
            try:
                self.slot_count = len(list(ds.ids))
            except Exception:
                pass
            try:
                self.names = list(ds.names)
            except Exception:
                pass
            try:
                self.states = list(ds.states)
            except Exception:
                pass
            try:
                self.currents_meas = list(ds.currents_meas)
            except Exception:
                pass
            try:
                self.currents_sp = list(ds.currents_setpoint)
            except Exception:
                pass

    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f"layout_slots_{self.dev_name}", QtWidgets.QGridLayout())

    def register_min_layouts(self):
        super().register_min_layouts()
        setattr(self, f"layout_slots_{self.dev_name}", QtWidgets.QGridLayout())

    def register_DS_full(self, group_number=1):
        super().register_DS_full()
        self._build_ui()
        self._subscribe_events()
        # Attach the device layout to the visible group layout (like other DS widgets)
        try:
            lo_group = getattr(self, f"lo_group_{group_number}")
            lo_device = getattr(self, f"layout_main_{self.dev_name}")
            lo_group.addLayout(lo_device)
        except Exception:
            pass

    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        self._build_ui()
        self._subscribe_events()
        # Attach the device layout to the visible group layout (like other DS widgets)
        try:
            lo_group = getattr(self, f"lo_group_{group_number}")
            lo_device = getattr(self, f"layout_main_{self.dev_name}")
            lo_group.addLayout(lo_device)
        except Exception:
            pass

    # ---- UI ----
    def _build_ui(self):
        dev_name = self.dev_name
        layout_main: QtWidgets.QVBoxLayout = getattr(self, f"layout_main_{dev_name}")
        layout_slots: QtWidgets.QGridLayout = getattr(self, f"layout_slots_{dev_name}")
        layout_status: QtWidgets.QHBoxLayout = getattr(self, f"layout_status_{dev_name}")

        # status line (LED + name etc.)
        self.set_state_status(False)

        # Global step selector (add to status line)
        try:
            step_label = QtWidgets.QLabel("Step:")
            step_combo = QtWidgets.QComboBox()
            for val in (0.001, 0.01, 0.1, 1.0):
                step_combo.addItem(f"{val:.3f} A", val)
            # set default selection
            def_idx = {0.001: 0, 0.01: 1, 0.1: 2, 1.0: 3}.get(self.step, 1)
            step_combo.setCurrentIndex(def_idx)
            step_combo.currentIndexChanged.connect(lambda _: self._set_global_step(float(step_combo.currentData())))
            layout_status.addWidget(step_label)
            layout_status.addWidget(step_combo)
            layout_status.addStretch(1)
            self._step_combo = step_combo
        except Exception:
            pass

        # grid: 2 columns x 4 rows
        cols, rows = 2, max(1, (self.slot_count + 1) // 2)
        font = QFont()
        font.setPointSize(10)

        self._controls.clear()
        for i in range(self.slot_count):
            r = i // cols
            c = i % cols

            box = QtWidgets.QGroupBox(self.names[i] if i < len(self.names) else f"Slot {i+1}")
            box.setFont(font)
            vbox = QtWidgets.QVBoxLayout(box)

            # measured current label
            meas = QtWidgets.QLabel("I_meas: 0.000 A")
            meas.setAlignment(Qt.AlignLeft)
            setp = QtWidgets.QLabel("I_set: 0.000 A")
            setp.setAlignment(Qt.AlignLeft)

            # setpoint controls
            h = QtWidgets.QHBoxLayout()
            btn_minus = QtWidgets.QPushButton("-")
            btn_plus = QtWidgets.QPushButton("+")
            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setRange(-50.0, 50.0)  # Allow negative values
            spin.setSingleStep(self.step)
            spin.setValue(0.0)
            chk = QtWidgets.QCheckBox("ON")

            # context menu to change step
            def make_context(btn: QtWidgets.QPushButton, slot_index: int):
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                def open_menu(pos):
                    m = QtWidgets.QMenu(btn)
                    m.addSection("Global step")
                    for val in (0.001, 0.01, 0.1, 1.0):
                        act_g = m.addAction(f"Set global step {val:.3f} A")
                        act_g.triggered.connect(partial(self._set_global_step, val))
                    m.addSeparator()
                    m.addSection("This slot step")
                    for val in (0.001, 0.01, 0.1, 1.0):
                        act_s = m.addAction(f"Set this slot step {val:.3f} A")
                        act_s.triggered.connect(partial(self._set_slot_step, slot_index, val))
                    m.exec_(btn.mapToGlobal(pos))
                btn.customContextMenuRequested.connect(open_menu)
            make_context(btn_minus, i)
            make_context(btn_plus, i)

            btn_minus.clicked.connect(partial(self._nudge, i, -1))
            btn_plus.clicked.connect(partial(self._nudge, i, +1))
            chk.toggled.connect(partial(self._toggle_slot, i))
            
            # Only user input triggers setpoint changes
            spin.editingFinished.connect(partial(self._apply_setpoint, i))

            h.addWidget(btn_minus)
            h.addWidget(spin)
            h.addWidget(btn_plus)
            h.addStretch(1)
            h.addWidget(chk)

            vbox.addWidget(meas)
            vbox.addWidget(setp)
            vbox.addLayout(h)
            layout_slots.addWidget(box, r, c)

            self._controls.append({
                "meas": meas,
                "setp": setp,
                "spin": spin,
                "chk": chk,
                "name": box,
            })

        layout_main.addLayout(layout_status)
        layout_main.addLayout(layout_slots)

        # initialize values
        self._refresh_ui_from_arrays()

    def _subscribe_events(self):
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")
        for attr in ("states", "names", "currents_meas", "currents_setpoint"):
            try:
                ds.subscribe_event(attr, tango.EventType.CHANGE_EVENT, self._event_listener)
            except Exception:
                pass

    # ---- logic ----
    def _set_global_step(self, value: float):
        self.step = float(value)
        # Update combo if present
        try:
            # Find the index with this value
            for i in range(self._step_combo.count()):
                if float(self._step_combo.itemData(i)) == self.step:
                    self._step_combo.setCurrentIndex(i)
                    break
        except Exception:
            pass
        for idx, ctrl in enumerate(self._controls):
            # do not override per-slot override
            if idx not in self._slot_steps:
                ctrl["spin"].setSingleStep(self.step)

    def _set_slot_step(self, index: int, value: float):
        self._slot_steps[int(index)] = float(value)
        self._controls[int(index)]["spin"].setSingleStep(float(value))

    def _nudge(self, index: int, direction: int):
        ctrl = self._controls[index]
        spin: QtWidgets.QDoubleSpinBox = ctrl["spin"]
        step = float(self._slot_steps.get(index, self.step))
        new_value = spin.value() + direction * step
        # Clamp to spinbox range instead of forcing >= 0
        new_value = max(spin.minimum(), min(spin.maximum(), new_value))
        spin.setValue(new_value)
        self._apply_setpoint(index)

    def _apply_setpoint(self, index: int):
        import time
        
        ctrl = self._controls[index]
        spin: QtWidgets.QDoubleSpinBox = ctrl["spin"]
        value = float(spin.value())
        
        # Debouncing: prevent rapid successive calls
        current_time = time.time()
        if index in self._last_setpoint_time:
            if current_time - self._last_setpoint_time[index] < 0.1:  # 100ms debounce
                return
        
        # Only send if the value actually differs from current setpoint to prevent loops
        if index < len(self.currents_sp):
            current_sp = float(self.currents_sp[index])
            if abs(value - current_sp) < 0.001:  # 1mA tolerance
                return
        
        self._last_setpoint_time[index] = current_time
        
        # Tango command: set_current([idx+1, value])
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.command_inout("set_current", [float(index + 1), float(value)])
        except Exception:
            pass

    def _toggle_slot(self, index: int, checked: bool):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.command_inout("set_output_state", [int(index + 1), int(1 if checked else 0)])
        except Exception:
            pass

    def _event_listener(self, ev):
        try:
            if ev.err:
                return
            name = ev.attr_name.rsplit("/", 1)[-1]
            val = ev.attr_value.value
            if name == "states":
                self.states = list(val)
            elif name == "names":
                self.names = list(val)
            elif name == "currents_meas":
                self.currents_meas = list(val)
            elif name == "currents_setpoint":
                self.currents_sp = list(val)
            self._refresh_ui_from_arrays()
        except Exception:
            pass

    def _refresh_ui_from_arrays(self):
        for i, ctrl in enumerate(self._controls):
            if i < len(self.names):
                ctrl["name"].setTitle(str(self.names[i]))
            if i < len(self.currents_meas):
                ctrl["meas"].setText(f"I_meas: {self.currents_meas[i]:.3f} A")
            if i < len(self.currents_sp):
                ctrl["setp"].setText(f"I_set: {self.currents_sp[i]:.3f} A")
                # NOTE: Spin box is NEVER updated by server - only by user input
            if i < len(self.states):
                # avoid signal feedback loop by blocking
                b = ctrl["chk"].blockSignals(True)
                ctrl["chk"].setChecked(bool(self.states[i]))
                ctrl["chk"].blockSignals(b)

    # Required abstract method (not used here)
    def set_the_control_value(self, value):
        pass
