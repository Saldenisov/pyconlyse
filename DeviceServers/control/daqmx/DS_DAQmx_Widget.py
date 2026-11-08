"""Purpose-built PyQt5 operator panel for the physical TRANCON DAQ card."""

import json
import sys
from functools import partial
from pathlib import Path

app_folder = Path(__file__).resolve().parents[3]
if str(app_folder) not in sys.path:
    sys.path.append(str(app_folder))

from PyQt5 import QtCore as QtCore, QtWidgets
from PyQt5.QtCore import QTimer
from taurus.external.qt import Qt
from taurus.qt.qtgui.button import TaurusCommandButton

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class DAQmx_Widget(DS_General_Widget):
    """Standalone-capable control surface for the direct local DAQmx server."""

    refresh_interval_ms = 1000

    def __init__(self, dev_name: str, panel=None, vis_type: VisType = VisType.FULL):
        self._channel_rows = {}
        self._refresh_timer = None
        self._hardware_label = None
        super().__init__(dev_name, panel, vis_type)

    def register_DS_full(self, group_number=1):
        super().register_DS_full()
        self._build_layout(group_number, show_server_actions=True)

    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        self._build_layout(group_number, show_server_actions=False)

    def _build_layout(self, group_number=1, show_server_actions=True):
        dev_name = self.dev_name
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")

        self.setObjectName("daqmxRoot")
        self.setMinimumWidth(820 if show_server_actions else 650)
        self.setStyleSheet(self._stylesheet())
        self.set_state_status()
        lo_device.addLayout(lo_status)

        header = QtWidgets.QFrame()
        header.setObjectName("cardHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        title_box = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("TRANCON DAQ CONTROL")
        title.setObjectName("cardTitle")
        subtitle = QtWidgets.QLabel(self.dev_name)
        subtitle.setObjectName("cardSubtitle")
        self._hardware_label = QtWidgets.QLabel("NI hardware · discovering…")
        self._hardware_label.setObjectName("hardwareMeta")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_box.addWidget(self._hardware_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        if show_server_actions:
            button_on = TaurusCommandButton(command="turn_on")
            button_on.setModel(dev_name)
            button_on.setText("Enable server")
            button_on.setObjectName("primaryButton")
            button_off = TaurusCommandButton(command="turn_off")
            button_off.setModel(dev_name)
            button_off.setText("Disable server")
            button_off.setObjectName("secondaryButton")
            header_layout.addWidget(button_off)
            header_layout.addWidget(button_on)

        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.refresh_values)
        header_layout.addWidget(refresh)
        lo_device.addWidget(header)

        try:
            channels = json.loads(str(self.ds.list_channels_json()))
        except Exception as exc:
            error = QtWidgets.QLabel(f"Could not load channel list: {exc}")
            error.setObjectName("errorBanner")
            error.setWordWrap(True)
            lo_device.addWidget(error)
            channels = []

        content = QtWidgets.QGridLayout()
        content.setContentsMargins(0, 8, 0, 0)
        content.setHorizontalSpacing(10)
        content.setVerticalSpacing(10)

        outputs = [channel for channel in channels if channel.get("kind") == "DigitalOut"]
        inputs = [channel for channel in channels if channel.get("kind") == "DigitalIn"]
        analog = [channel for channel in channels if channel.get("kind") in {"AIcurrent", "AIVoltage"}]
        counters = [channel for channel in channels if channel.get("kind") == "DigitalCounter"]

        content.addWidget(self._build_outputs(outputs), 0, 0, 1, 2)
        content.addWidget(self._build_inputs(inputs), 1, 0)

        measurements = QtWidgets.QWidget()
        measurements_layout = QtWidgets.QVBoxLayout(measurements)
        measurements_layout.setContentsMargins(0, 0, 0, 0)
        measurements_layout.setSpacing(10)
        measurements_layout.addWidget(self._build_analog(analog))
        measurements_layout.addWidget(self._build_counters(counters))
        content.addWidget(measurements, 1, 1)
        content.setColumnStretch(0, 1)
        content.setColumnStretch(1, 1)
        lo_device.addLayout(content)
        lo_group.addLayout(lo_device)

        self._update_hardware_meta()
        self.refresh_values()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_values)
        self._refresh_timer.start(self.refresh_interval_ms)

    @staticmethod
    def _section(title, code):
        group = QtWidgets.QGroupBox()
        group.setObjectName("daqSection")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(12, 14, 12, 12)
        heading = QtWidgets.QHBoxLayout()
        badge = QtWidgets.QLabel(code)
        badge.setObjectName("sectionBadge")
        label = QtWidgets.QLabel(title)
        label.setObjectName("sectionTitle")
        heading.addWidget(badge)
        heading.addWidget(label)
        heading.addStretch()
        layout.addLayout(heading)
        return group, layout

    def _build_outputs(self, channels):
        group, layout = self._section("Digital outputs", "DO")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for index, channel in enumerate(channels):
            name = channel.get("name", "")
            physical = channel.get("channel", "")
            card = QtWidgets.QFrame()
            card.setObjectName("outputCard")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(10, 9, 10, 9)
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("channelName")
            physical_label = QtWidgets.QLabel(physical)
            physical_label.setObjectName("physicalChannel")
            value_label = QtWidgets.QLabel("UNKNOWN")
            value_label.setObjectName("outputUnknown")
            actions = QtWidgets.QHBoxLayout()
            off_button = QtWidgets.QPushButton("OFF")
            off_button.setObjectName("offButton")
            on_button = QtWidgets.QPushButton("ON")
            on_button.setObjectName("onButton")
            off_button.clicked.connect(partial(self._write_output, name, 0))
            on_button.clicked.connect(partial(self._write_output, name, 1))
            actions.addWidget(off_button)
            actions.addWidget(on_button)
            card_layout.addWidget(name_label)
            card_layout.addWidget(physical_label)
            card_layout.addWidget(value_label)
            card_layout.addLayout(actions)
            grid.addWidget(card, index // 3, index % 3)
            self._channel_rows[name] = {
                "kind": "DigitalOut",
                "value": value_label,
                "on": on_button,
                "off": off_button,
            }

        layout.addLayout(grid)
        return group

    def _build_inputs(self, channels):
        group, layout = self._section("Digital inputs", "DI")
        for channel in channels:
            name = channel.get("name", "")
            row = QtWidgets.QFrame()
            row.setObjectName("readoutRow")
            row_layout = QtWidgets.QHBoxLayout(row)
            lamp = QtWidgets.QLabel()
            lamp.setObjectName("inputLampOff")
            lamp.setFixedSize(14, 14)
            labels = QtWidgets.QVBoxLayout()
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("channelName")
            physical = QtWidgets.QLabel(channel.get("channel", ""))
            physical.setObjectName("physicalChannel")
            labels.addWidget(name_label)
            labels.addWidget(physical)
            value = QtWidgets.QLabel("INACTIVE")
            value.setObjectName("inputValue")
            row_layout.addWidget(lamp)
            row_layout.addLayout(labels)
            row_layout.addStretch()
            row_layout.addWidget(value)
            layout.addWidget(row)
            self._channel_rows[name] = {
                "kind": "DigitalIn",
                "value": value,
                "lamp": lamp,
            }
        layout.addStretch()
        return group

    def _build_analog(self, channels):
        group, layout = self._section("Analog inputs", "AI")
        for channel in channels:
            name = channel.get("name", "")
            unit = channel.get("unit", "")
            row = QtWidgets.QFrame()
            row.setObjectName("analogCard")
            row_layout = QtWidgets.QGridLayout(row)
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("channelName")
            physical = QtWidgets.QLabel(channel.get("channel", ""))
            physical.setObjectName("physicalChannel")
            value = QtWidgets.QLabel("—")
            value.setObjectName("analogValue")
            limits = QtWidgets.QLabel(self._limit_text(channel))
            limits.setObjectName("limitText")
            row_layout.addWidget(name_label, 0, 0)
            row_layout.addWidget(physical, 1, 0)
            row_layout.addWidget(value, 0, 1, 2, 1)
            row_layout.addWidget(limits, 2, 0, 1, 2)
            row_layout.setColumnStretch(0, 1)
            layout.addWidget(row)
            self._channel_rows[name] = {
                "kind": channel.get("kind", ""),
                "value": value,
                "unit": unit,
                "card": row,
                "limits": limits,
            }
        return group

    def _build_counters(self, channels):
        group, layout = self._section("Pulse counters", "CTR")
        for channel in channels:
            name = channel.get("name", "")
            row = QtWidgets.QFrame()
            row.setObjectName("counterCard")
            row_layout = QtWidgets.QGridLayout(row)
            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("channelName")
            physical = QtWidgets.QLabel(
                f"{channel.get('counter', '')} ← {channel.get('channel', '')}"
            )
            physical.setObjectName("physicalChannel")
            value = QtWidgets.QLabel("—")
            value.setObjectName("counterValue")
            reset = QtWidgets.QPushButton("Reset counter")
            reset.setObjectName("secondaryButton")
            reset.clicked.connect(partial(self._reset_counter, name))
            row_layout.addWidget(name_label, 0, 0)
            row_layout.addWidget(physical, 1, 0)
            row_layout.addWidget(value, 0, 1, 2, 1)
            row_layout.addWidget(reset, 2, 0, 1, 2)
            row_layout.setColumnStretch(0, 1)
            layout.addWidget(row)
            self._channel_rows[name] = {
                "kind": "DigitalCounter",
                "value": value,
            }
        return group

    @staticmethod
    def _limit_text(channel):
        low = channel.get("limit_alarm_min")
        high = channel.get("limit_alarm_max")
        if low is None and high is None:
            return channel.get("kind", "")
        unit = channel.get("unit", "")
        return f"Alarm limits: {low if low is not None else '—'} – {high if high is not None else '—'} {unit}".strip()

    def _update_hardware_meta(self):
        if self._hardware_label is None:
            return
        try:
            info = json.loads(str(self.ds.device_info_json))
            if info.get("error"):
                self._hardware_label.setText(info["error"])
                return
            self._hardware_label.setText(
                f"{info.get('product_type', 'NI DAQmx')} · serial {info.get('serial_num', '—')} · {info.get('name', '')}"
            )
        except Exception as exc:
            self._hardware_label.setText(f"Hardware metadata unavailable: {exc}")

    def refresh_values(self):
        if not self._device_available:
            return
        for name, row in self._channel_rows.items():
            try:
                payload = json.loads(str(self.ds.read_channel(name)))
                value = payload.get("value")
                kind = row.get("kind")
                if kind == "DigitalOut":
                    known = bool(payload.get("value_known", True)) and int(value) >= 0
                    if not known:
                        row["value"].setText("UNKNOWN")
                        row["value"].setObjectName("outputUnknown")
                    elif int(value):
                        row["value"].setText("ON")
                        row["value"].setObjectName("outputOn")
                    else:
                        row["value"].setText("OFF")
                        row["value"].setObjectName("outputOff")
                    self._repolish(row["value"])
                elif kind == "DigitalIn":
                    active = bool(int(value))
                    row["value"].setText("ACTIVE" if active else "INACTIVE")
                    row["lamp"].setObjectName("inputLampOn" if active else "inputLampOff")
                    self._repolish(row["lamp"])
                elif kind in {"AIcurrent", "AIVoltage"}:
                    text = self._format_number(value)
                    if row.get("unit"):
                        text = f"{text} {row['unit']}"
                    row["value"].setText(text)
                    row["card"].setProperty("alarm", bool(payload.get("alarm")))
                    row["limits"].setText(
                        "ALARM · outside configured limits"
                        if payload.get("alarm")
                        else self._limit_text(payload)
                    )
                    self._repolish(row["card"])
                else:
                    text = self._format_number(value)
                    unit = payload.get("unit", "")
                    row["value"].setText(f"{text} {unit}".strip())
            except Exception as exc:
                row["value"].setText(f"ERR · {exc}")
                row["value"].setToolTip(str(exc))

    @staticmethod
    def _format_number(value):
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    @staticmethod
    def _repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _write_output(self, name: str, value: int):
        try:
            self.ds.write_digital_output([name, str(int(value))])
            self.refresh_values()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "DAQmx output", f"Write failed:\n{exc}")
            self.refresh_values()

    def _reset_counter(self, name: str):
        try:
            self.ds.reset_counter(name)
            self.refresh_values()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "DAQmx counter", f"Reset failed:\n{exc}")

    def on_device_lost(self, error_text: str):
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

    def on_device_reconnected(self):
        if self._refresh_timer is not None:
            self._refresh_timer.start(self.refresh_interval_ms)
        self._update_hardware_meta()
        self.refresh_values()

    def set_the_control_value(self, value):
        pass

    @staticmethod
    def _stylesheet():
        return """
        QWidget#daqmxRoot { background: #eef3f6; color: #152633; }
        QFrame#cardHeader {
            background: #123f56; border: 1px solid #0e3346; border-radius: 10px;
        }
        QLabel#cardTitle { color: white; font-size: 20px; font-weight: 800; letter-spacing: 1px; }
        QLabel#cardSubtitle { color: #b9e2e6; font-size: 12px; }
        QLabel#hardwareMeta { color: #d5e8ed; font-size: 11px; }
        QGroupBox#daqSection {
            background: white; border: 1px solid #d4dde3; border-radius: 9px;
        }
        QLabel#sectionBadge {
            background: #dceef3; color: #0c6172; border-radius: 4px;
            padding: 3px 7px; font-family: Consolas; font-size: 10px; font-weight: bold;
        }
        QLabel#sectionTitle { font-size: 14px; font-weight: 800; }
        QFrame#outputCard, QFrame#readoutRow, QFrame#analogCard, QFrame#counterCard {
            background: #f9fbfc; border: 1px solid #dbe3e8; border-radius: 7px;
        }
        QFrame#analogCard[alarm="true"] { background: #fff3f3; border: 1px solid #dd727c; }
        QLabel#channelName { font-size: 12px; font-weight: 700; }
        QLabel#physicalChannel { color: #687b88; font-family: Consolas; font-size: 9px; }
        QLabel#outputUnknown { color: #8a6200; background: #fff0c2; padding: 3px; font-weight: bold; }
        QLabel#outputOn { color: #08734b; background: #dff5e9; padding: 3px; font-weight: bold; }
        QLabel#outputOff { color: #536572; background: #e9eef1; padding: 3px; font-weight: bold; }
        QLabel#inputLampOff { background: #aeb9c0; border: 3px solid #dce3e7; border-radius: 7px; }
        QLabel#inputLampOn { background: #23b878; border: 3px solid #c9f1df; border-radius: 7px; }
        QLabel#inputValue { color: #52636f; font-size: 10px; font-weight: bold; }
        QLabel#analogValue, QLabel#counterValue { font-family: Consolas; font-size: 22px; font-weight: 800; }
        QLabel#limitText { color: #687b88; font-size: 9px; }
        QLabel#errorBanner { background: #fff1f1; color: #9a2631; padding: 8px; border-radius: 5px; }
        QPushButton, TaurusCommandButton {
            min-height: 28px; padding: 2px 10px; border: 1px solid #0b668d;
            border-radius: 5px; background: #0b668d; color: white; font-weight: bold;
        }
        QPushButton#secondaryButton, TaurusCommandButton#secondaryButton {
            background: white; color: #304b5b; border-color: #9eafb9;
        }
        QPushButton#offButton { background: #e9edef; color: #344a57; border-color: #aebac1; }
        QPushButton#onButton { background: #087b60; color: white; border-color: #087b60; }
        QPushButton:disabled { background: #d7dde1; color: #8b979e; border-color: #c2cbd0; }
        """
