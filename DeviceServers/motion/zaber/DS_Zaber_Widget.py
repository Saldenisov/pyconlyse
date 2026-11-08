"""PyQt control for the VD2 Zaber mirror stage, with millimetre inputs only."""

from __future__ import annotations

import math

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from tango import DeviceProxy


class ZaberStageWidget(QWidget):
    """Operator-driven motion; construction and polling never move or home."""

    def __init__(self, device_name="manip/VD2/Zaber", parent=None, vis_type=None):
        super().__init__(parent)
        self.device_name = str(device_name)
        self._proxy = None
        self._state = "UNKNOWN"
        self.setWindowTitle("Zaber mirror stage — {}".format(self.device_name))

        layout = QVBoxLayout(self)
        self.state_label = QLabel("State: UNKNOWN")
        self.position_label = QLabel("Position: unavailable")
        self.status_label = QLabel("Waiting for Zaber Tango server")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        layout.addWidget(self.position_label)
        layout.addWidget(self.status_label)

        form = QFormLayout()
        self.target = QDoubleSpinBox()
        self.target.setDecimals(6)
        self.target.setSingleStep(0.1)
        self.target.setSuffix(" mm")
        self.target.setRange(0.0, 50.8)
        form.addRow("Absolute target:", self.target)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.move_button = QPushButton("Move")
        self.stop_button = QPushButton("Stop")
        self.home_button = QPushButton("Home")
        self.reconnect_button = QPushButton("Reconnect")
        for button in (self.move_button, self.stop_button, self.home_button, self.reconnect_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.move_button.clicked.connect(self._move)
        self.stop_button.clicked.connect(lambda: self._command("Stop"))
        self.home_button.clicked.connect(self._home)
        self.reconnect_button.clicked.connect(lambda: self._command("Reconnect"))
        layout.addWidget(QLabel("After power cycling, Home before relying on absolute positions."))

        self._set_controls()
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _device(self):
        if self._proxy is None:
            self._proxy = DeviceProxy(self.device_name)
            self._proxy.set_timeout_millis(2000)
        return self._proxy

    def _set_controls(self):
        self.move_button.setEnabled(self._state == "ON")
        self.home_button.setEnabled(self._state == "ON")
        self.stop_button.setEnabled(self._state == "MOVING")
        self.reconnect_button.setEnabled(self._state != "MOVING")

    def refresh(self):
        try:
            device = self._device()
            self._state = str(device.state()).rsplit(".", 1)[-1]
            self.state_label.setText("State: {}".format(self._state))
            self.status_label.setText(str(device.status()))
            if self._state == "ON":
                minimum = float(device.read_attribute("minimum_mm").value)
                maximum = float(device.read_attribute("maximum_mm").value)
                position = float(device.read_attribute("position_mm").value)
                if not all(math.isfinite(value) for value in (minimum, maximum, position)):
                    raise ValueError("Non-finite Zaber position or travel limit")
                self.target.setRange(minimum, maximum)
                self.position_label.setText("Position: {:.6f} mm".format(position))
        except Exception as exc:
            self._proxy = None
            self._state = "FAULT"
            self.state_label.setText("State: unavailable")
            self.status_label.setText(str(exc))
        self._set_controls()

    def _command(self, name, argument=None):
        try:
            device = self._device()
            if argument is None:
                device.command_inout(name)
            else:
                device.command_inout(name, float(argument))
        except Exception as exc:
            QMessageBox.warning(self, "Zaber command failed", str(exc))
        self.refresh()

    def _move(self):
        if self._state == "ON":
            self._command("MoveAbsoluteMm", self.target.value())

    def _home(self):
        if self._state != "ON":
            return
        answer = QMessageBox.question(
            self,
            "Home Zaber stage",
            "The mirror will move to its home switch. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._command("Home")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
