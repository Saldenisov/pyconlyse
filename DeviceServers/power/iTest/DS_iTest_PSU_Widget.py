# iTest PSU control widget
import json
from typing import Dict, List

from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QDoubleValidator
from taurus import Device
from taurus.external.qt import Qt

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class Itest_PSU(DS_General_Widget):
    """GUI for iTest PSU rack: per-slot on/off, current set, and live readings."""

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self._rows: Dict[str, Dict] = {}
        self._timer = None
        self._safe_min = -5.0
        self._safe_max = 5.0
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

        # Timer for live updates
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

    def _update_summary(self):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            data = ds.command_inout("GetAllOutputs")
            outs = json.loads(data) if isinstance(data, str) else data
            txt = f"Outputs: {len(outs)}\n"
            on = sum(1 for o in outs if bool(o.get("output_enabled")))
            txt += f"ON: {on}, OFF: {len(outs)-on}"
            self._summary.setText(txt)
        except Exception as e:
            self._summary.setText(f"Error: {e}")

    def _refresh_table(self, build_rows: bool):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            raw = ds.command_inout("GetAllOutputs")
            outs: List[Dict] = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            if build_rows:
                err = QtWidgets.QLabel(f"Error reading outputs: {e}")
                err.setStyleSheet("color: red;")
                self._table.addWidget(err, 1, 0, 1, 5)
            return

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
            for o in outs:
                name = o.get("name") or (f"ch{int(o.get('channel'))}" if o.get("channel") else f"slot_{o.get('slot', '?')}")
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
                sp.setValue(0.0)
                self._table.addWidget(sp, row, 2)

                # Column 3,4: measured current/voltage labels
                lab_i = QtWidgets.QLabel("–")
                lab_v = QtWidgets.QLabel("–")
                self._table.addWidget(lab_i, row, 3)
                self._table.addWidget(lab_v, row, 4)

                # Wire actions
                btn_on.clicked.connect(lambda _, n=name: self._set_output_state(n, True))
                btn_off.clicked.connect(lambda _, n=name: self._set_output_state(n, False))
                sp.editingFinished.connect(lambda n=name, w=sp: self._set_current(n, w.value()))

                # Save row widgets
                self._rows[name] = {
                    "lab": lab,
                    "btn_on": btn_on,
                    "btn_off": btn_off,
                    "spin": sp,
                    "lab_i": lab_i,
                    "lab_v": lab_v,
                }
                row += 1

        # Update values
        for o in outs:
            name = o.get("name") or (f"ch{int(o.get('channel'))}" if o.get("channel") else f"slot_{o.get('slot', '?')}")
            roww = self._rows.get(name)
            if not roww:
                continue
            try:
                # ON/OFF state -> enable/disable styling
                on = bool(o.get("output_enabled")) if o.get("output_enabled") is not None else False
                roww["btn_on"].setEnabled(not on)
                roww["btn_off"].setEnabled(on)
                # Measurements
                mi = o.get("measured_current")
                mv = o.get("measured_voltage")
                roww["lab_i"].setText("{:.6f}".format(float(mi)) if mi is not None else "–")
                roww["lab_v"].setText("{:.4f}".format(float(mv)) if mv is not None else "–")
                # Update spin from current_setpoint if present (do not fight user ongoing edits)
                cs = o.get("current_setpoint")
                if cs is not None and not roww["spin"].hasFocus():
                    try:
                        roww["spin"].setValue(float(cs))
                    except Exception:
                        pass
            except Exception:
                pass

    def _set_output_state(self, name: str, on: bool):
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            if on:
                ds.command_inout("OutputOn", name)
            else:
                ds.command_inout("OutputOff", name)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "iTest", f"Failed to set output {name}: {e}")

    def _set_current(self, name: str, amps: float):
        if amps < self._safe_min or amps > self._safe_max:
            QtWidgets.QMessageBox.warning(
                self,
                "iTest",
                f"Requested current {amps:.4f} A outside safe limits [{self._safe_min}, {self._safe_max}] A",
            )
            return
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            ds.command_inout("SetOutputCurrent", (name, float(amps)))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "iTest", f"Failed to set current on {name}: {e}")
