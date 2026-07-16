import json
import sys
from functools import partial
from pathlib import Path

app_folder = Path(__file__).resolve().parents[3]
if str(app_folder) not in sys.path:
    sys.path.append(str(app_folder))

from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
from taurus.external.qt import Qt
from taurus.qt.qtgui.button import TaurusCommandButton

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class DAQmx_Widget(DS_General_Widget):
    """Operator widget for the direct local DAQmx Tango server."""

    refresh_interval_ms = 1000

    def __init__(self, dev_name: str, panel=None, vis_type: VisType = VisType.FULL):
        self._channel_rows = {}
        self._refresh_timer = None
        super().__init__(dev_name, panel, vis_type)

    def register_DS_full(self, group_number=1):
        super().register_DS_full()
        self._build_layout(group_number)

    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        self._build_layout(group_number)

    def _build_layout(self, group_number=1):
        dev_name = self.dev_name
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")

        self.set_state_status()
        lo_device.addLayout(lo_status)

        if self.vis_type == VisType.FULL:
            buttons = QtWidgets.QHBoxLayout()
            button_on = TaurusCommandButton(command="turn_on")
            button_on.setModel(dev_name)
            button_on.setText("ON")
            button_off = TaurusCommandButton(command="turn_off")
            button_off.setModel(dev_name)
            button_off.setText("OFF")
            refresh = QtWidgets.QPushButton("Refresh")
            refresh.clicked.connect(self.refresh_values)
            buttons.addWidget(button_on)
            buttons.addWidget(button_off)
            buttons.addWidget(refresh)
            buttons.addStretch()
            lo_device.addLayout(buttons)

        group = QtWidgets.QGroupBox("DAQmx Controls")
        grid = QtWidgets.QGridLayout(group)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)

        headers = ("Name", "Type", "Value", "Action")
        for col, title in enumerate(headers):
            label = QtWidgets.QLabel(title)
            font = QFont()
            font.setBold(True)
            label.setFont(font)
            grid.addWidget(label, 0, col)

        self._build_channel_rows(grid)
        lo_device.addWidget(group)
        lo_group.addLayout(lo_device)

        self.refresh_values()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_values)
        self._refresh_timer.start(self.refresh_interval_ms)

    def _build_channel_rows(self, grid):
        try:
            channels = json.loads(str(self.ds.list_channels_json()))
        except Exception as exc:
            error = QtWidgets.QLabel(f"Could not load channel list: {exc}")
            error.setStyleSheet("color: red;")
            grid.addWidget(error, 1, 0, 1, 4)
            return

        for row, channel in enumerate(channels, start=1):
            name = channel.get("name", "")
            kind = channel.get("kind", "")
            physical = channel.get("channel", "")

            name_label = QtWidgets.QLabel(name)
            name_label.setToolTip(physical)
            type_label = QtWidgets.QLabel(kind)
            value_label = QtWidgets.QLabel("...")
            value_label.setMinimumWidth(90)
            value_label.setToolTip(physical)

            action_widget = QtWidgets.QWidget()
            action_layout = QtWidgets.QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)

            if kind == "DigitalOut":
                toggle = QtWidgets.QCheckBox()
                toggle.setToolTip(f"Write {name}")
                toggle.clicked.connect(partial(self._write_output, name, toggle))
                action_layout.addWidget(toggle)
                self._channel_rows[name] = {
                    "type": kind,
                    "value": value_label,
                    "toggle": toggle,
                }
            elif kind == "DigitalCounter":
                reset = QtWidgets.QPushButton("Reset")
                reset.clicked.connect(partial(self._reset_counter, name))
                action_layout.addWidget(reset)
                self._channel_rows[name] = {"type": kind, "value": value_label}
            else:
                action_layout.addStretch()
                self._channel_rows[name] = {"type": kind, "value": value_label}

            grid.addWidget(name_label, row, 0)
            grid.addWidget(type_label, row, 1)
            grid.addWidget(value_label, row, 2)
            grid.addWidget(action_widget, row, 3)

    def refresh_values(self):
        if not self._device_available:
            return
        for name, row in self._channel_rows.items():
            try:
                payload = json.loads(str(self.ds.read_channel(name)))
                value = payload.get("value")
                kind = row.get("type")
                if isinstance(value, float):
                    text = f"{value:.6g}"
                else:
                    text = str(value)
                if payload.get("alarm"):
                    text = f"{text} ALARM"
                    row["value"].setStyleSheet("color: red; font-weight: bold;")
                else:
                    row["value"].setStyleSheet("")
                row["value"].setText(text)
                if kind == "DigitalOut" and "toggle" in row:
                    toggle = row["toggle"]
                    toggle.blockSignals(True)
                    toggle.setChecked(bool(int(value)))
                    toggle.blockSignals(False)
            except Exception as exc:
                row["value"].setText(f"ERR: {exc}")
                row["value"].setStyleSheet("color: red;")

    def _write_output(self, name: str, toggle: QtWidgets.QCheckBox):
        try:
            self.ds.write_digital_output([name, str(int(toggle.isChecked()))])
            self.refresh_values()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "DAQmx", f"Write failed: {exc}")
            self.refresh_values()

    def _reset_counter(self, name: str):
        try:
            self.ds.reset_counter(name)
            self.refresh_values()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "DAQmx", f"Reset failed: {exc}")

    def on_device_lost(self, error_text: str):
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

    def on_device_reconnected(self):
        if self._refresh_timer is not None:
            self._refresh_timer.start(self.refresh_interval_ms)
        self.refresh_values()

    def set_the_control_value(self, value):
        pass
