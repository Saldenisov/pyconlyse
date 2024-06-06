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


class AVANTES_CCD(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.grabbing = False
        super().__init__(device_name, parent, vis_type)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.data_listener)
        self.order = None
        self.od_deque = deque(maxlen=50)

    def before_ds(self):
        super().before_ds()
        waves = self.ds.get_property('wavelengths')['wavelengths'][0]
        self.wavelengths = np.array(eval(waves))

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

        # Image
        self.set_image(lo_image)

        # Buttons and commands
        setattr(self, f'button_start_grabbing_{dev_name}', TaurusCommandButton(text='Grab'))
        button_start_grabbing: TaurusCommandButton = getattr(self, f'button_start_grabbing_{dev_name}')
        button_start_grabbing.clicked.connect(self.grab_clicked)

        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        lo_buttons.addWidget(button_start_grabbing)
        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)

        # CCD parameters
        self.number_average = TaurusWheelEdit()
        self.number_average.model = f'{dev_name}/number_average'
        self.number_average.setDigitCount(2, 0)

        self.number_kinetics = TaurusWheelEdit()
        self.number_kinetics.model = f'{dev_name}/number_kinetics'
        self.number_kinetics.setDigitCount(2, 0)

        """
        Trigger Settimgs
            1) Trigger Mode:
                Software - 0
                Hardware - 1
                Single Scan - n
            2) Trigger Source:
                External - 0
                Synchronized - 1
            3) Trigger Type
                Edge - 0
                Level - 1
                
        """
        self.trigger_mode = TaurusValueComboBox()
        self.trigger_mode.addItems(['Software', 'Hardware', 'Single Scan'])

        self.trigger_source = TaurusValueComboBox()
        self.trigger_source.addItems(['External', 'Synchronized'])

        self.trigger_type = TaurusValueComboBox()
        self.trigger_type.addItems(['Edge', 'Level'])

        self.exposure_time = TaurusWheelEdit()
        self.exposure_time.setDigitCount(3, 3)
        self.exposure_time.setValue(10)
        self.exposure_time.model = f'{dev_name}/exposure_time'

        self.update_param()

        lo_parameters.addWidget(TaurusLabel('N kinetics'))
        lo_parameters.addWidget(self.number_kinetics)

        lo_parameters.addWidget(TaurusLabel('N average'))
        lo_parameters.addWidget(self.number_average)
        # lo_parameters.addWidget(TaurusLabel('N kinetics'))
        # lo_parameters.addWidget(self.number_kinetics)
        # lo_parameters.addWidget(TaurusLabel('Trigger Mode'))
        # lo_parameters.addWidget(self.trigger_mode)
        # lo_parameters.addWidget(TaurusLabel('Trigger Source'))
        # lo_parameters.addWidget(self.trigger_source)
        # lo_parameters.addWidget(TaurusLabel('Trigger Type'))
        # lo_parameters.addWidget(self.trigger_type)
        lo_parameters.addWidget(TaurusLabel('Exposure Time, ms'))
        lo_parameters.addWidget(self.exposure_time)
        lo_parameters.addSpacerItem(QtWidgets.QSpacerItem(0, 5, QtWidgets.QSizePolicy.Expanding,
                                                          QtWidgets.QSizePolicy.Minimum))

        # lo_parameters_od.addWidget(QtWidgets.QLabel('BG level'))
        # self.bg_level = QtWidgets.QSpinBox()
        # self.bg_level.setValue(50000)
        # lo_parameters_od.addWidget(self.bg_level)
        # lo_parameters_od.addWidget(QtWidgets.QLabel('OD err range'))
        # self.od_err_left = QtWidgets.QDoubleSpinBox()
        # self.od_err_left.setValue(360.0)
        # self.od_err_right = QtWidgets.QDoubleSpinBox()
        # self.od_err_right.setValue(770.0)
        # lo_parameters_od.addWidget(self.od_err_left)
        # lo_parameters_od.addWidget(self.od_err_right)
        lo_parameters_od.addSpacerItem(QtWidgets.QSpacerItem(0, 5, QtWidgets.QSizePolicy.Expanding,
                                                             QtWidgets.QSizePolicy.Minimum))
        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_parameters_od)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        super().register_DS_min()
        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_image: Qt.QLayout = getattr(self, f'layout_image_{dev_name}')

        # State and status
        self.set_state_status(False)

        # Image
        self.set_image(lo_image)

        # Button
        grabbing_led = TaurusLed()
        grabbing_led.model = f'{dev_name}/isgrabbing'
        setattr(self, f'button_start_grabbing_{dev_name}', TaurusCommandButton(text='Grab'))
        button_start_grabbing: TaurusCommandButton = getattr(self, f'button_start_grabbing_{dev_name}')
        button_start_grabbing.clicked.connect(self.grab_clicked)

        lo_status.addWidget(grabbing_led)
        lo_status.addWidget(button_start_grabbing)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_group.addLayout(lo_device)

    def set_image(self, lo_image):
        self.view = pg.GraphicsLayoutWidget(parent=self, title='DATA')
        pg.setConfigOptions(antialias=True)

        self.plot_spectra = self.view.addPlot(title="Spectra", row=0, column=0)
        self.plot_spectra.curves = []
        self.plot_spectra.setLabel('left', "Intensity", units='counts')
        self.plot_spectra.setLabel('bottom', "Wavelength", units='nm')
        self.add_curve(self.plot_spectra, self.wavelengths)  # spectra

        self.view.setMinimumSize(450, 250)
        lo_image.addWidget(self.view)

    def update_curve(self, plot, i, y):
        plot.curves[i].setData(self.wavelengths, y)

    def add_curve(self, plot, y):  # add a curve
        plot.curves.append(plot.plot(self.wavelengths, y))

    def del_curve(self, plot, i):
        plot.curves[i].clear()

    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f'layout_parameters_{self.dev_name}', QtWidgets.QHBoxLayout())
        setattr(self, f'layout_parameters_od_{self.dev_name}', QtWidgets.QHBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}',  QtWidgets.QHBoxLayout())

    def register_min_layouts(self):
        super().register_min_layouts()
        setattr(self, f'layout_image_{self.dev_name}', Qt.QHBoxLayout())

    def trigger_mode_changed(self):
        state = self.trigger_mode.currentText()
        self.ds.trigger_mode = 1 if state == 'External' else 0

    def exposure_time_changed(self):
        self.ds.exposure_time = float(self.exposure_time.value)

    def grab_clicked(self):
        button_start_grabbing: TaurusCommandButton = getattr(self, f'button_start_grabbing_{self.dev_name}')
        if self.grabbing:
            self.timer.stop()
            self.ds.stop_grabbing()
            self.grabbing = False
            button_start_grabbing.setText('Grab')
            self.order = None
        else:
            self.ds.start_grabbing()
            self.timer.start(50)
            self.order = self.make_order()
            self.grabbing = True
            button_start_grabbing.setText('Grabbing')

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