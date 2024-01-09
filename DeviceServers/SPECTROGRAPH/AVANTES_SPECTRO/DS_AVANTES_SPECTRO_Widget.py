import numpy
import pyqtgraph as pg
import numpy as np
import zlib
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox, TaurusWheelEdit
from PyQt5 import QtWidgets
from DeviceServers.DS_Widget import DS_General_Widget, VisType
from taurus.core import TaurusDevState
from collections import deque
from utilities.datastructures.mes_independent.measurments_dataclass import DataXY, GammaSpectrometerBG, \
    GammaSpectrometerBlank, GammaSpectrometerMeasurement


class AVANTES_SPECTRO(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.grabbing = False
        super().__init__(device_name, parent, vis_type)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.data_listener)
        self.order = None
        self.od_deque = deque(maxlen=50)

    def before_ds(self):
        super().before_ds()

    def register_DS_full(self, group_number=1):
        super().register_DS_full()

        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')
        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
        lo_parameters_od: Qt.QLayout = getattr(self, f'layout_parameters_od_{dev_name}')
        lo_image: Qt.QLayout = getattr(self, f'layout_image_{dev_name}')

        # State and status
        self.set_state_status(False)


        lo_device.addWidget(QtWidgets.QLabel('Spectrometer control'))

        lo_device.addSpacerItem(QtWidgets.QSpacerItem(0, 5, QtWidgets.QSizePolicy.Expanding,
                                                                QtWidgets.QSizePolicy.Minimum))

        lo_sig_ref = QtWidgets.QHBoxLayout()
        lo_sig_ref.addWidget(QtWidgets.QLabel('Signal spectrometer'))
        lo_sig_ref.addWidget(QtWidgets.QLabel('Reference spectrometer'))

        rb_group = QtWidgets.QGroupBox('Sync for:')
        rb_lo = QtWidgets.QHBoxLayout()
        rb_bg = QtWidgets.QRadioButton('BG')
        rb_measurement = QtWidgets.QRadioButton('Measurement')
        rb_measurement.setChecked(True)
        rb_measurement.toggled.connect(lambda: self.sync_type(rb_measurement, rb_bg, self.widgets))
        rb_bg.toggled.connect(lambda: self.sync_type(rb_measurement, rb_bg, self.widgets))
        rb_lo.addWidget(rb_bg)
        rb_lo.addWidget(rb_measurement)
        rb_group.setLayout(rb_lo)
        lo_sig_ref.addWidget(rb_group)

        button_measure_bg = QtWidgets.QPushButton('Measure BG')
        button_measure_blank = QtWidgets.QPushButton('Measure Blank')
        button_measure_sample = QtWidgets.QPushButton('Measure Sample Once')
        button_measure_cyclic = QtWidgets.QPushButton('Measure Sample Cyclic')
        
        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)

        lo_buttons.addWidget(button_measure_bg)
        lo_buttons.addWidget(button_measure_blank)
        lo_buttons.addWidget(button_measure_sample)
        lo_buttons.addWidget(button_measure_cyclic)

        # parameters
        lo_parameters.addWidget(QtWidgets.QLabel('Average'))
        sb_average = QtWidgets.QSpinBox()
        sb_average.setValue(3)
        lo_parameters.addWidget(sb_average)
        lo_parameters.addWidget(QtWidgets.QLabel('Exposure, us'))
        dsb_exposure = QtWidgets.QDoubleSpinBox()
        dsb_exposure.setMinimum(20)
        dsb_exposure.setMaximum(1000000.0)
        dsb_exposure.setValue(500.0)
        lo_parameters.addWidget(dsb_exposure)
        lo_parameters.addWidget(QtWidgets.QLabel('Every n sec'))
        sb_every_sec = QtWidgets.QSpinBox()
        sb_every_sec.setValue(5)
        lo_parameters.addWidget(sb_every_sec)
        lo_parameters.addWidget(QtWidgets.QLabel('N measurement'))
        sb_n_measurements = QtWidgets.QSpinBox()
        sb_n_measurements.setValue(100)
        lo_parameters.addWidget(sb_n_measurements)

        # Image
        self.set_image(lo_image)

        # data
        lo_parameters_od.addWidget(QtWidgets.QLabel('Name of sample:'))
        le_data_name = QtWidgets.QLineEdit()
        lo_parameters_od.addWidget(le_data_name)
        button_save_data = QtWidgets.QPushButton('Save')
        lo_parameters_od.addWidget(button_save_data)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_sig_ref)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_image)
        lo_device.addLayout(lo_parameters_od)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def set_image(self, lo_image):
        view = pg.GraphicsLayoutWidget(parent=self, title='DATA')
        pg.setConfigOptions(antialias=True)

        self.plot_od = view.addPlot(title="Spectra", row=0, column=0)
        self.plot_od.curves = []

        self.plot_od.setLabel('left', "O.D.", units='counts')
        self.plot_od.setLabel('bottom', "Wavelength", units='nm')
        self.add_curve(self.plot_od, DataXY(X=np.arange(200, 800, 1), Y=np.zeros(600)))  # spectra

        view.setMinimumSize(450, 250)

        lo_image_buttons = QtWidgets.QVBoxLayout()
        self.button_clear_image = QtWidgets.QPushButton('Clear all')
        lo_image_buttons.addWidget(self.button_clear_image)

        lo_image.addWidget(view)
        lo_image.addLayout(lo_image_buttons)

    def sync_type(self, rb_measure: QtWidgets.QRadioButton, rb_bg: QtWidgets.QRadioButton, ds_widgets):
        for ds_widget in ds_widgets.values():
            if rb_measure.isChecked():
                ds_widget.ds.bg_measurement = 0
            elif rb_bg.isChecked():
                ds_widget.bg_measurement = 1

    def update_curve(self, plot, i, data: DataXY):
        plot.curves[i].setData(data.X, data.Y)

    def add_curve(self, plot, data: DataXY):  # add a curve
        plot.curves.append(plot.plot(data.X, data.Y))

    def del_curve(self, plot, i):
        plot.curves[i].clear()

    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f'layout_parameters_{self.dev_name}', QtWidgets.QHBoxLayout())
        setattr(self, f'layout_parameters_od_{self.dev_name}', QtWidgets.QHBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}', QtWidgets.QHBoxLayout())

    def register_min_layouts(self):
        super().register_min_layouts()
        setattr(self, f'layout_image_{self.dev_name}', Qt.QHBoxLayout())

    def make_order(self):
        order = self.ds.register_order([int(self.number_average.value)])
        return order

    def data_listener(self):
        if self.order:
            is_order_ready = self.ds.is_order_ready(self.order)
            if is_order_ready:
                data = self.ds.give_order(self.order)
                data_b = zlib.decompress(eval(data))
                data_array = np.frombuffer(data_b, dtype=np.int16)
                data_array = data_array.reshape(-1, 2068)
                self.wavelengths = data_array[0]
                averaged_data = np.average(data_array[1:], axis=0)
                self.update_curve(self.plot_spectra, 0, averaged_data)
                self.order = self.make_order()
        else:
            self.order = self.make_order()

    def update_param(self):
        if self.ds.state == TaurusDevState.Ready:
            res = int(self.ds.trigger_mode)
            self.trigger_mode.setCurrentIndex(res)
            res = int(self.ds.trigger_source)
            self.trigger_source.setCurrentIndex(res)
            res = int(self.ds.trigger_type)
            self.trigger_type.setCurrentIndex(res)
            self.exposure_time.setValue(self.ds.exposure_time)
            self.number_kinetics.setValue(self.ds.number_kinetics)
            self.number_average.setValue(self.ds.number_average)