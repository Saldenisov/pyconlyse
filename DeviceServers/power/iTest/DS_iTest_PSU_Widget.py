# iTest PSU control widget
import sys
import json
from pathlib import Path
from typing import Dict, List

import tango
from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QDoubleValidator
from taurus import Device
from taurus.external.qt import Qt

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType

# Reuse helper utilities like NETIO widget
fixes_path = Path(__file__).parents[3] / "fixes"
if str(fixes_path) not in sys.path:
    sys.path.append(str(fixes_path))
from taurus_warnings_fix import (
    suppress_taurus_deprecation_warnings,
    check_device_connection,
)


class Itest_PSU(DS_General_Widget):
    """GUI for iTest PSU rack: per-slot on/off, current set, and live readings.

    Updated to follow NETIO client pattern: use Tango attributes (names/ids/states,
    CurrentSetpoints/MeasuredCurrents/MeasuredVoltages) and subscribe to state changes.
    """

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        suppress_taurus_deprecation_warnings()
        self._rows: Dict[str, Dict] = {}
        self._timer = None
        self._safe_min = -5.0
        self._safe_max = 5.0
        # Cached arrays
        self._ids: List[int] = []
        self._names: List[str] = []
        self._states: List[int] = []
        self._csps: List[float] = []
        self._meas_i: List[float] = []
        self._meas_v: List[float] = []
        self._controls_ready = False
        super().__init__(device_name, parent, vis_type)

    def before_ds(self):
        # Read safe limits from device properties if available
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            props = ds.get_property("SafeCurrentMin")
            if props and props.get("SafeCurrentMin"):
                self._safe_min = float(props["SafeCurrentMin"][0])
        except Exception:
            pass
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            props = ds.get_property("SafeCurrentMax")
            if props and props.get("SafeCurrentMax"):
                self._safe_max = float(props["SafeCurrentMax"][0])
        except Exception:
            pass

        # Initialize arrays from Tango attributes if device is connected
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            if check_device_connection(ds):
                self._read_arrays()
            else:
                self._ids, self._names, self._states = [], [], []
                self._csps, self._meas_i, self._meas_v = [], [], []
        except Exception:
            self._ids, self._names, self._states = [], [], []
            self._csps, self._meas_i, self._meas_v = [], [], []

    def register_full_layouts(self):
        super().register_full_layouts()
        # Container layout
        dev_name = self.dev_name
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{1}")
        lo_device: Qt.QVBoxLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QHBoxLayout = getattr(self, f"layout_status_{dev_name}")

        # Status strip
        self.set_state_status(short=True)

        # Table for outputs
        self._table = QtWidgets.QGridLayout()
        self._table.setHorizontalSpacing(12)
        self._table.setVerticalSpacing(6)

        header = ["Slot/Name", "Output", "Set Current [A]", "Measured I [A]", "Measured V [V]"]
        for col, text in enumerate(header):
            lab = QtWidgets.QLabel(f"<b>{text}</b>")
            self._table.addWidget(lab, 0, col)

        # First refresh builds rows
        self._refresh_table(build_rows=True)

        # Subscribe to states change events like NETIO client
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.subscribe_event("states", tango.EventType.CHANGE_EVENT, self._states_event_listener)
        except Exception:
            pass

        # Timer for live updates of measurements/values
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(lambda: self._refresh_table(build_rows=False))
        self._timer.start()

        lo_device.addLayout(lo_status)
        lo_device.addLayout(self._table)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        # Minimal: just status and live summary
        super().register_min_layouts()
        dev_name = self.dev_name
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{1}")
        lo_device: Qt.QVBoxLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QHBoxLayout = getattr(self, f"layout_status_{dev_name}")
        self.set_state_status(short=True)
        # Simple label area
        self._summary = QtWidgets.QLabel("Loading...")
        lo_device.addLayout(lo_status)
        lo_device.addWidget(self._summary)
        lo_group.addLayout(lo_device)
        # Timer to refresh summary
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_summary)
        self._timer.start()
        self._update_summary()

    # Unused abstract method from base
    def set_the_control_value(self, value):
        pass

    # --- Helpers ---
    def _read_arrays(self):
        ds: Device = getattr(self, f"ds_{self.dev_name}")
        # Use attribute access; if fails, fallback to read_attribute
        try:
            ids = list(getattr(ds, "ids", []) or [])
        except Exception:
            ids = list(ds.read_attribute("ids").value)
        try:
            names = list(getattr(ds, "names", []) or [])
        except Exception:
            names = list(ds.read_attribute("names").value)
        try:
            states = list(getattr(ds, "states", []) or [])
        except Exception:
            states = list(ds.read_attribute("states").value)
        try:
            csps = list(getattr(ds, "CurrentSetpoints", []) or [])
        except Exception:
            try:
                csps = list(ds.read_attribute("CurrentSetpoints").value)
            except Exception:
                csps = []
        try:
            mi = list(getattr(ds, "MeasuredCurrents", []) or [])
        except Exception:
            try:
                mi = list(ds.read_attribute("MeasuredCurrents").value)
            except Exception:
                mi = []
        try:
            mv = list(getattr(ds, "MeasuredVoltages", []) or [])
        except Exception:
            try:
                mv = list(ds.read_attribute("MeasuredVoltages").value)
            except Exception:
                mv = []
        self._ids, self._names, self._states = ids, names, states
        self._csps, self._meas_i, self._meas_v = csps, mi, mv

    def _states_event_listener(self, event):
        # Update state buttons quickly on event
        try:
            if not self._controls_ready:
                return
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            new_states = []
            try:
                new_states = list(getattr(ds, "states", []) or [])
            except Exception:
                try:
                    new_states = list(ds.read_attribute("states").value)
                except Exception:
                    return
            # Preserve ids/names mapping
            ids = list(self._ids) if self._ids else []
            names = list(self._names) if self._names else [f"slot_{i}" for i in ids]
            for idx, sid in enumerate(ids):
                name = names[idx] if idx < len(names) else f"slot_{sid}"
                roww = self._rows.get(name)
                if not roww:
                    continue
                try:
                    on = int(new_states[idx]) == 1 if idx < len(new_states) else None
                    if on is None:
                        continue
                    roww["btn_on"].setEnabled(not on)
                    roww["btn_off"].setEnabled(on)
                except Exception:
                    continue
            # cache
            self._states = list(new_states)
        except Exception:
            pass

    def _update_summary(self):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            # Read attribute arrays
            ids = list(getattr(ds, "ids", []) or [])
            states = list(getattr(ds, "states", []) or [])
            txt = f"Outputs: {len(ids)}\n"
            on = sum(1 for s in states if int(s) == 1)
            txt += f"ON: {on}, OFF: {max(0, len(ids)-on)}"
            self._summary.setText(txt)
        except Exception as e:
            self._summary.setText(f"Error: {e}")

    def _refresh_table(self, build_rows: bool):
        # Read arrays from Tango attributes
        fallback = False
        try:
            self._read_arrays()
        except Exception as e:
            fallback = True
            # Show warning banner but still build full UI
            if build_rows:
                err = QtWidgets.QLabel(f"Warning: {e}")
                err.setStyleSheet("color: orange;")
                self._table.addWidget(err, 1, 0, 1, 5)
            # Prepare placeholder arrays using configured channel count
            try:
                ds: Device = getattr(self, f"ds_{self.dev_name}")
                # Prefer ids length
                try:
                    ids_attr = getattr(ds, "ids", None)
                    count = len(list(ids_attr)) if ids_attr is not None else 0
                except Exception:
                    count = 0
                if not count:
                    try:
                        count = int(getattr(ds, "Channels", 0) or 0)
                    except Exception:
                        count = 0
                if not count:
                    try:
                        props = ds.get_property("ChannelsPerRack")
                        count = int(props.get("ChannelsPerRack", [8])[0])
                    except Exception:
                        count = 8
            except Exception:
                count = 8
            self._ids = list(range(1, count + 1))
            self._names = [f"slot_{i}" for i in self._ids]
            self._states = [0] * count
            self._csps = [0.0] * count
            self._meas_i = [None] * count
            self._meas_v = [None] * count

        ids = list(self._ids)
        names = list(self._names) if self._names else [f"slot_{i}" for i in ids]
        states = list(self._states)
        csps = list(self._csps)
        meas_i = list(self._meas_i)
        meas_v = list(self._meas_v)

        # Build rows once
        if build_rows:
            # Clear prior rows (except header)
            for i in reversed(range(1, self._table.rowCount())):
                for j in range(self._table.columnCount()):
                    item = self._table.itemAtPosition(i, j)
                    if item:
                        w = item.widget()
                        if w:
                            w.setParent(None)
            self._rows.clear()

            row = 1
            for idx, sid in enumerate(ids):
                name = names[idx] if idx < len(names) else f"slot_{sid}"
                # Column 0: label
                lab = QtWidgets.QLabel(name)
                self._table.addWidget(lab, row, 0)

                # Column 1: ON/OFF buttons
                box = QtWidgets.QWidget()
                hb = QtWidgets.QHBoxLayout(box)
                hb.setContentsMargins(0, 0, 0, 0)
                btn_on = QtWidgets.QPushButton("On")
                btn_off = QtWidgets.QPushButton("Off")
                hb.addWidget(btn_on)
                hb.addWidget(btn_off)
                self._table.addWidget(box, row, 1)

                # Column 2: set current spinbox
                sp = QtWidgets.QDoubleSpinBox()
                sp.setDecimals(4)
                sp.setSingleStep(0.01)
                sp.setRange(self._safe_min, self._safe_max)
                sp.setValue(float(csps[idx]) if idx < len(csps) and csps[idx] is not None else 0.0)
                self._table.addWidget(sp, row, 2)

                # Column 3,4: measured current/voltage labels
                lab_i = QtWidgets.QLabel("–")
                lab_v = QtWidgets.QLabel("–")
                self._table.addWidget(lab_i, row, 3)
                self._table.addWidget(lab_v, row, 4)

                # Wire actions
                btn_on.clicked.connect(lambda _, s=sid: self._set_output_state_slot(s, True))
                btn_off.clicked.connect(lambda _, s=sid: self._set_output_state_slot(s, False))
                sp.editingFinished.connect(lambda s=sid, w=sp: self._set_current_slot(s, w.value()))

                # Save row widgets
                self._rows[name] = {
                    "id": sid,
                    "lab": lab,
                    "btn_on": btn_on,
                    "btn_off": btn_off,
                    "spin": sp,
                    "lab_i": lab_i,
                    "lab_v": lab_v,
                }
                row += 1

            self._controls_ready = True

        # Update values
        for idx, sid in enumerate(ids):
            name = names[idx] if idx < len(names) else f"slot_{sid}"
            roww = self._rows.get(name)
            if not roww:
                continue
            try:
                # ON/OFF state -> enable/disable styling
                on = int(states[idx]) == 1 if idx < len(states) else False
                roww["btn_on"].setEnabled(not on)
                roww["btn_off"].setEnabled(on)
                # Measurements
                mi = meas_i[idx] if idx < len(meas_i) else None
                mv = meas_v[idx] if idx < len(meas_v) else None
                roww["lab_i"].setText("{:.6f}".format(float(mi)) if mi is not None else "–")
                roww["lab_v"].setText("{:.4f}".format(float(mv)) if mv is not None else "–")
                # Update spin from current_setpoint if present (do not fight user ongoing edits)
                cs = csps[idx] if idx < len(csps) else None
                if cs is not None and not roww["spin"].hasFocus():
                    try:
                        roww["spin"].setValue(float(cs))
                    except Exception:
                        pass
            except Exception:
                pass

    def _set_output_state_slot(self, slot: int, on: bool):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            # Prefer slot-indexed convenience commands
            cmd = "OutputOnSlot" if on else "OutputOffSlot"
            ds.command_inout(cmd, int(slot))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "iTest", f"Failed to set output for slot {slot}: {e}")

    def _set_current_slot(self, slot: int, amps: float):
        if amps < self._safe_min or amps > self._safe_max:
            QtWidgets.QMessageBox.warning(
                self,
                "iTest",
                f"Requested current {amps:.4f} A outside safe limits [{self._safe_min}, {self._safe_max}] A",
            )
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.command_inout("SetSlotCurrent", (int(slot), float(amps)))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "iTest", f"Failed to set current on slot {slot}: {e}")
