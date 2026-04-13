import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class ANDOR_SPECTROGRAPH(DS_General_Widget):
    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        super().__init__(device_name, parent, vis_type)
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.update_param)
        self.refresh_timer.start()

    def register_DS_full(self, group_number=1):
        super().register_DS_full()
        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_buttons: Qt.QLayout = getattr(self, f"layout_buttons_{dev_name}")
        lo_parameters: Qt.QLayout = getattr(self, f"layout_parameters_{dev_name}")
        lo_plot: Qt.QLayout = getattr(self, f"layout_plot_{dev_name}")

        self.set_state_status(False)
        lo_device.addLayout(lo_status)

        setattr(self, f"button_on_{dev_name}", TaurusCommandButton(command="turn_on"))
        button_on: TaurusCommandButton = getattr(self, f"button_on_{dev_name}")
        button_on.setModel(dev_name)

        setattr(self, f"button_off_{dev_name}", TaurusCommandButton(command="turn_off"))
        button_off: TaurusCommandButton = getattr(self, f"button_off_{dev_name}")
        button_off.setModel(dev_name)

        setattr(
            self,
            f"button_calib_{dev_name}",
            TaurusCommandButton(command="RefreshCalibration"),
        )
        button_calib: TaurusCommandButton = getattr(self, f"button_calib_{dev_name}")
        button_calib.setModel(dev_name)

        setattr(
            self,
            f"button_zero_{dev_name}",
            TaurusCommandButton(command="GoToZeroOrder"),
        )
        button_zero: TaurusCommandButton = getattr(self, f"button_zero_{dev_name}")
        button_zero.setModel(dev_name)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)
        lo_buttons.addWidget(button_calib)
        lo_buttons.addWidget(button_zero)

        self.sb_wavelength = QtWidgets.QDoubleSpinBox()
        self.sb_wavelength.setRange(0.0, 2000.0)
        self.sb_wavelength.setDecimals(3)
        self.sb_wavelength.setSuffix(" nm")
        self.sb_wavelength.editingFinished.connect(self._write_wavelength)

        self.sb_grating = QtWidgets.QSpinBox()
        self.sb_grating.setRange(1, 8)
        self.sb_grating.editingFinished.connect(self._write_grating)

        self.sb_input_side = QtWidgets.QDoubleSpinBox()
        self.sb_input_side.setRange(0.0, 5000.0)
        self.sb_input_side.setSuffix(" um")
        self.sb_input_side.editingFinished.connect(
            lambda: self._write_slit("input_side_slit_um", self.sb_input_side.value())
        )

        self.sb_output_side = QtWidgets.QDoubleSpinBox()
        self.sb_output_side.setRange(0.0, 5000.0)
        self.sb_output_side.setSuffix(" um")
        self.sb_output_side.editingFinished.connect(
            lambda: self._write_slit("output_side_slit_um", self.sb_output_side.value())
        )

        lo_parameters.addWidget(QtWidgets.QLabel("Center"))
        lo_parameters.addWidget(self.sb_wavelength)
        lo_parameters.addWidget(QtWidgets.QLabel("Grating"))
        lo_parameters.addWidget(self.sb_grating)
        lo_parameters.addWidget(QtWidgets.QLabel("Input slit"))
        lo_parameters.addWidget(self.sb_input_side)
        lo_parameters.addWidget(QtWidgets.QLabel("Output slit"))
        lo_parameters.addWidget(self.sb_output_side)
        lo_parameters.addStretch()

        self.lbl_info = QtWidgets.QLabel("No calibration yet")
        lo_plot.addWidget(self.lbl_info)

        self.view = pg.GraphicsLayoutWidget(parent=self, title="Calibration")
        self.plot = self.view.addPlot(title="Calibration axis", row=0, column=0)
        self.plot.setLabel("left", "Wavelength", units="nm")
        self.plot.setLabel("bottom", "Pixel", units="")
        self.calibration_curve = self.plot.plot(np.arange(10), np.zeros(10))
        self.view.setMinimumHeight(260)
        lo_plot.addWidget(self.view)

        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_plot)
        lo_group.addLayout(lo_device)

        self.update_param()

    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        dev_name = self.dev_name
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        self.set_state_status(False)
        lo_device.addLayout(lo_status)
        lo_group.addLayout(lo_device)

    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f"layout_parameters_{self.dev_name}", QtWidgets.QHBoxLayout())
        setattr(self, f"layout_plot_{self.dev_name}", QtWidgets.QVBoxLayout())

    def register_min_layouts(self):
        super().register_min_layouts()

    def _write_wavelength(self):
        try:
            self.ds.wavelength_nm = float(self.sb_wavelength.value())
        except Exception:
            return
        self.update_param()

    def _write_grating(self):
        try:
            self.ds.grating = int(self.sb_grating.value())
        except Exception:
            return
        self.update_param()

    def _write_slit(self, attr_name: str, value: float):
        try:
            setattr(self.ds, attr_name, float(value))
        except Exception:
            return
        self.update_param()

    def update_param(self):
        try:
            self.sb_wavelength.blockSignals(True)
            self.sb_grating.blockSignals(True)
            self.sb_input_side.blockSignals(True)
            self.sb_output_side.blockSignals(True)

            self.sb_wavelength.setValue(float(self.ds.wavelength_nm))
            self.sb_grating.setValue(int(self.ds.grating))
            self.sb_input_side.setValue(float(self.ds.input_side_slit_um))
            self.sb_output_side.setValue(float(self.ds.output_side_slit_um))

            calibration = np.asarray(self.ds.calibration, dtype=np.float32)
            if calibration.size:
                pixels = np.arange(calibration.size, dtype=np.float32)
                self.calibration_curve.setData(pixels, calibration)
                self.lbl_info.setText(
                    f"Pixels: {calibration.size} | Range: {calibration[0]:.2f} - {calibration[-1]:.2f} nm"
                )
            else:
                self.calibration_curve.setData(np.arange(10), np.zeros(10))
                self.lbl_info.setText("Calibration unavailable")
        except Exception:
            return
        finally:
            self.sb_wavelength.blockSignals(False)
            self.sb_grating.blockSignals(False)
            self.sb_input_side.blockSignals(False)
            self.sb_output_side.blockSignals(False)

    def set_the_control_value(self, value):
        return value
