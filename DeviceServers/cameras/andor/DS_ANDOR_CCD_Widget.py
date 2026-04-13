import zlib
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLed
from taurus.qt.qtgui.input import TaurusValueComboBox, TaurusValueSpinBox, TaurusWheelEdit

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class ANDOR_CCD(DS_General_Widget):
    TRACK_COLORS = [
        "#1f77b4",
        "#d62728",
        "#2ca02c",
        "#9467bd",
        "#8c564b",
        "#e377c2",
    ]

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.grabbing = False
        self.order = None
        self.wavelengths = np.arange(1064, dtype=np.float32)
        self.od_deque = deque(maxlen=50)
        super().__init__(device_name, parent, vis_type)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.data_listener)

    def before_ds(self):
        super().before_ds()
        try:
            self.wavelengths = np.asarray(self.ds.wavelengths_axis, dtype=np.float32)
        except Exception:
            self.wavelengths = np.arange(1064, dtype=np.float32)

    def register_DS_full(self, group_number=1):
        super().register_DS_full()
        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_buttons: Qt.QLayout = getattr(self, f"layout_buttons_{dev_name}")
        lo_parameters: Qt.QLayout = getattr(self, f"layout_parameters_{dev_name}")
        lo_info: Qt.QLayout = getattr(self, f"layout_info_{dev_name}")
        lo_image: Qt.QLayout = getattr(self, f"layout_image_{dev_name}")

        self.set_state_status(False)
        self.set_image(lo_image)

        setattr(
            self, f"button_start_grabbing_{dev_name}", TaurusCommandButton(text="Grab")
        )
        button_start_grabbing: TaurusCommandButton = getattr(
            self, f"button_start_grabbing_{dev_name}"
        )
        button_start_grabbing.clicked.connect(self.grab_clicked)

        setattr(self, f"button_on_{dev_name}", TaurusCommandButton(command="turn_on"))
        button_on: TaurusCommandButton = getattr(self, f"button_on_{dev_name}")
        button_on.setModel(dev_name)

        setattr(self, f"button_off_{dev_name}", TaurusCommandButton(command="turn_off"))
        button_off: TaurusCommandButton = getattr(self, f"button_off_{dev_name}")
        button_off.setModel(dev_name)

        setattr(
            self,
            f"button_refresh_calib_{dev_name}",
            TaurusCommandButton(command="RefreshCalibration"),
        )
        button_refresh: TaurusCommandButton = getattr(
            self, f"button_refresh_calib_{dev_name}"
        )
        button_refresh.setModel(dev_name)

        lo_buttons.addWidget(button_start_grabbing)
        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)
        lo_buttons.addWidget(button_refresh)

        self.number_spectra = TaurusWheelEdit()
        self.number_spectra.setValue(5)
        self.number_spectra.setDigitCount(2, 0)
        self.number_spectra.setMinValue(1)
        self.number_spectra.setMaxValue(100)

        self.number_kinetics = TaurusValueSpinBox()
        self.number_kinetics.setMinimumWidth(80)
        try:
            self.number_kinetics.setValue(int(self.ds.number_kinetics))
        except Exception:
            self.number_kinetics.setValue(1)
        self.number_kinetics.valueChanged.connect(self.number_kinetics_changed)

        self.trigger_mode = TaurusValueComboBox()
        self.trigger_mode.addItems(["Internal", "External", "Software"])
        self.trigger_mode.currentIndexChanged.connect(self.trigger_mode_changed)

        self.exposure_time = TaurusWheelEdit()
        try:
            self.exposure_time.setValue(float(self.ds.exposure_time))
        except Exception:
            self.exposure_time.setValue(0.001)
        self.exposure_time.setDigitCount(1, 6)
        self.exposure_time.valueChanged.connect(self.exposure_time_changed)

        lo_parameters.addWidget(QtWidgets.QLabel("Frames per order"))
        lo_parameters.addWidget(self.number_spectra)
        lo_parameters.addWidget(QtWidgets.QLabel("Kinetics"))
        lo_parameters.addWidget(self.number_kinetics)
        lo_parameters.addWidget(QtWidgets.QLabel("Trigger"))
        lo_parameters.addWidget(self.trigger_mode)
        lo_parameters.addWidget(QtWidgets.QLabel("Exposure, s"))
        lo_parameters.addWidget(self.exposure_time)
        lo_parameters.addStretch()

        self.info_label = QtWidgets.QLabel("Waiting for data")
        lo_info.addWidget(self.info_label)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_info)
        lo_group.addLayout(lo_device)
        self.update_param()

    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_image: Qt.QLayout = getattr(self, f"layout_image_{dev_name}")

        self.set_state_status(False)
        self.set_image(lo_image)

        grabbing_led = TaurusLed()
        grabbing_led.model = f"{dev_name}/isgrabbing"
        setattr(
            self, f"button_start_grabbing_{dev_name}", TaurusCommandButton(text="Grab")
        )
        button_start_grabbing: TaurusCommandButton = getattr(
            self, f"button_start_grabbing_{dev_name}"
        )
        button_start_grabbing.clicked.connect(self.grab_clicked)

        lo_status.addWidget(grabbing_led)
        lo_status.addWidget(button_start_grabbing)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_group.addLayout(lo_device)

    def set_image(self, lo_image):
        self.view = pg.GraphicsLayoutWidget(parent=self, title="DATA")
        pg.setConfigOptions(antialias=True)

        self.plot_spectra = self.view.addPlot(title="Spectral tracks", row=0, column=0)
        self.plot_spectra.setLabel("left", "Intensity", units="counts")
        self.plot_spectra.setLabel("bottom", "Wavelength", units="nm")
        self.plot_spectra.showGrid(x=True, y=True, alpha=0.3)
        self.plot_spectra.curves = []

        self.plot_difference = self.view.addPlot(
            title="Track difference", row=0, column=1
        )
        self.plot_difference.setLabel("left", "Track 1 - Track 2", units="counts")
        self.plot_difference.setLabel("bottom", "Wavelength", units="nm")
        self.plot_difference.showGrid(x=True, y=True, alpha=0.3)
        self.diff_curve = self.plot_difference.plot(self.wavelengths, np.zeros_like(self.wavelengths))

        self.view.setMinimumSize(1000, 420)
        lo_image.addWidget(self.view)

    def _ensure_track_curves(self, track_count: int):
        while len(self.plot_spectra.curves) < track_count:
            color = self.TRACK_COLORS[len(self.plot_spectra.curves) % len(self.TRACK_COLORS)]
            pen = pg.mkPen(color=color, width=2)
            self.plot_spectra.curves.append(self.plot_spectra.plot(self.wavelengths, np.zeros_like(self.wavelengths), pen=pen))

        for idx, curve in enumerate(self.plot_spectra.curves):
            curve.setVisible(idx < track_count)

    def update_curve(self, curve, x, y):
        curve.setData(x, y)

    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f"layout_parameters_{self.dev_name}", QtWidgets.QHBoxLayout())
        setattr(self, f"layout_image_{self.dev_name}", QtWidgets.QHBoxLayout())

    def register_min_layouts(self):
        super().register_min_layouts()
        setattr(self, f"layout_image_{self.dev_name}", Qt.QHBoxLayout())

    def number_kinetics_changed(self):
        try:
            self.ds.number_kinetics = int(self.number_kinetics.value())
        except Exception:
            return

    def trigger_mode_changed(self):
        mode_name = self.trigger_mode.currentText()
        mapping = {"Internal": 0, "External": 1, "Software": 10}
        try:
            self.ds.trigger_mode = mapping.get(mode_name, 1)
        except Exception:
            return

    def exposure_time_changed(self):
        try:
            self.ds.exposure_time = float(self.exposure_time.value)
        except Exception:
            return

    def grab_clicked(self):
        button_start_grabbing: TaurusCommandButton = getattr(
            self, f"button_start_grabbing_{self.dev_name}"
        )
        if self.grabbing:
            self.timer.stop()
            self.ds.stop_grabbing()
            self.grabbing = False
            button_start_grabbing.setText("Grab")
            self.order = None
        else:
            self.ds.start_grabbing()
            self.timer.start(80)
            self.order = self.make_order()
            self.grabbing = True
            button_start_grabbing.setText("Grabbing")

    def make_order(self):
        return self.ds.register_order([int(self.number_spectra.value)])

    def _decode_order(self, data):
        data_b = zlib.decompress(eval(data))
        data_array = np.frombuffer(data_b, dtype=np.float32)
        width = max(1, int(getattr(self.ds, "width", len(self.wavelengths) or 1)))
        if data_array.size % width != 0:
            width = len(self.wavelengths) or width
        if data_array.size % width != 0:
            return None
        return data_array.reshape(-1, width)

    def _split_groups(self, data_array: np.ndarray):
        if data_array is None or data_array.shape[0] < 2:
            return self.wavelengths, np.empty((0, 0, 0), dtype=np.float32), np.empty((0, 0), dtype=np.float32)

        wavelengths = np.asarray(data_array[0], dtype=np.float32)
        payload = np.asarray(data_array[1:], dtype=np.float32)
        track_count = max(1, int(getattr(self.ds, "track_count", payload.shape[0] or 1)))
        if payload.shape[0] < track_count:
            track_count = payload.shape[0]
        group_count = max(1, payload.shape[0] // max(1, track_count))
        payload = payload[: group_count * track_count]
        grouped = payload.reshape(group_count, track_count, -1)
        averaged = np.mean(grouped, axis=0)
        return wavelengths, grouped, averaged

    def data_listener(self):
        if not self.order:
            self.order = self.make_order()
            return

        try:
            is_order_ready = self.ds.is_order_ready(self.order)
        except Exception:
            return

        if not is_order_ready:
            return

        try:
            data = self.ds.give_order(self.order)
            data_array = self._decode_order(data)
            wavelengths, grouped, averaged = self._split_groups(data_array)
            if averaged.size == 0:
                self.order = self.make_order()
                return

            self.wavelengths = wavelengths
            self._ensure_track_curves(averaged.shape[0])
            for idx in range(averaged.shape[0]):
                self.update_curve(self.plot_spectra.curves[idx], wavelengths, averaged[idx])

            if averaged.shape[0] >= 2:
                difference = averaged[0] - averaged[1]
                self.diff_curve.setData(wavelengths, difference)
            else:
                self.diff_curve.setData(wavelengths, np.zeros_like(wavelengths))

            self.info_label.setText(
                f"Tracks: {averaged.shape[0]} | Frames grouped: {grouped.shape[0]} | Pixels: {wavelengths.size}"
            )
            self.order = self.make_order()
        except Exception as exc:
            self.info_label.setText(f"Data update failed: {exc}")

    def update_param(self):
        try:
            self.wavelengths = np.asarray(self.ds.wavelengths_axis, dtype=np.float32)
        except Exception:
            pass

        try:
            exposure = float(self.ds.exposure_time)
            self.exposure_time.blockSignals(True)
            self.exposure_time.setValue(exposure)
            self.exposure_time.blockSignals(False)
        except Exception:
            pass

        try:
            kinetics = int(self.ds.number_kinetics)
            self.number_kinetics.blockSignals(True)
            self.number_kinetics.setValue(kinetics)
            self.number_kinetics.blockSignals(False)
        except Exception:
            pass

        try:
            mode = int(self.ds.trigger_mode)
            mapping = {0: 0, 1: 1, 10: 2}
            self.trigger_mode.blockSignals(True)
            self.trigger_mode.setCurrentIndex(mapping.get(mode, 1))
            self.trigger_mode.blockSignals(False)
        except Exception:
            pass

    def set_the_control_value(self, value):
        return value
