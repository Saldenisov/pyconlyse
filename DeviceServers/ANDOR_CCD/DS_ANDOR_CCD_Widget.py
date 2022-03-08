import pyqtgraph as pg
import numpy as np
import zlib
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox, TaurusWheelEdit
from PyQt5 import QtWidgets
from DeviceServers.DS_Widget import DS_General_Widget, VisType


class ANDOR_CCD(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.grabbing = False
        super().__init__(device_name, parent, vis_type)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.data_listener)
        self.order = None

    def before_ds(self):
        super().before_ds()
        waves = self.ds.get_property('wavelengths')['wavelengths'][0]
        self.wavelengths = np.array(eval(waves))

    def register_DS_full(self, group_number=1):
        super(ANDOR_CCD, self).register_DS_full()

        dev_name = self.dev_name

        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
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
        self.number_spectra = TaurusWheelEdit()
        self.number_spectra.setValue(2)

        self.trigger_mode = TaurusValueComboBox()
        self.trigger_mode.addItems(['Internal', 'External'])
        self.trigger_mode.currentIndexChanged.connect(self.trigger_mode_changed)

        self.exposure_time = TaurusValueSpinBox()
        self.exposure_time.model = f'{dev_name}/exposure_time'
        # self.exposure_time.setValue(ds.exposure_time)

        lo_parameters.addWidget(TaurusLabel('N spectra'))
        lo_parameters.addWidget(self.number_spectra)
        lo_parameters.addWidget(TaurusLabel('Trigger'))
        lo_parameters.addWidget(self.trigger_mode)

        lo_parameters.addWidget(TaurusLabel('Exposure Time'))
        lo_parameters.addWidget(self.exposure_time)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        super(ANDOR_CCD, self).register_DS_min()
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
        self.curves = []
        self.plot_spectra = self.view.addPlot(title="Spectra",)
        self.plot_spectra.setLabel('left', "Intensity", units='counts')
        self.plot_spectra.setLabel('bottom', "Wavelength", units='nm')
        self.add_curve(self.wavelengths)
        self.add_curve(self.wavelengths)
        self.add_curve(self.wavelengths)
        self.view.setMinimumSize(1000, 450)
        lo_image.addWidget(self.view)

    def update(self, i, y): # update a curve
        self.curves[i].setData(self.wavelengths, y)

    def del_curve(self, i): # remove a curve
        self.curves[i].clear()

    def add_curve(self, y): # add a curve
        self.curves.append(self.plot_spectra.plot(self.wavelengths, y))


    def register_full_layouts(self):
        super(ANDOR_CCD, self).register_full_layouts()
        setattr(self, f'layout_parameters_{self.dev_name}', QtWidgets.QHBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}',  QtWidgets.QHBoxLayout())

    def register_min_layouts(self):
        super(ANDOR_CCD, self).register_min_layouts()
        setattr(self, f'layout_image_{self.dev_name}', Qt.QHBoxLayout())

    def trigger_mode_changed(self):
        state = self.trigger_mode.currentText()
        self.ds.set_trigger_mode(1 if state == 'External' else 0)

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
        order = self.ds.register_order(int(self.number_spectra.value))
        return order

    def data_listener(self):
        if self.order:
            is_order_ready = self.ds.is_order_ready(self.order)
            if is_order_ready:
                data = self.ds.give_order(self.order)
                data_b = zlib.decompress(eval(data))
                data_array = np.frombuffer(data_b, dtype=np.int32)
                data_array = data_array.reshape(-1, 1024)
                self.wavelengths = data_array[0]
                averaged_data = self.average_data_ELYSE_seq(data_array[1:])
                self.update(0, data_array[1])
                self.update(1, data_array[2])
                self.update(2, data_array[3])
                self.order = self.make_order()
        else:
            self.order = self.make_order()

    def average_data_ELYSE_seq(self, data: np.ndarray) -> np.ndarray:
        back_idx = 0
        with_idx = 1
        without_idx = 2
        background = np.average(data[back_idx::3], axis=0)
        with_e = np.average(data[with_idx::3], axis=0)
        without_e = np.average(data[without_idx::3], axis=0)
        return np.vstack((background, with_e, without_e))

    def convert_image(self, image):
        image2D = image
        shp = (int(image2D.shape[0] / 3), image2D.shape[1], 3)
        image3D = image2D.reshape(np.roll(shp, 1)).transpose(1, 2, 0)
        return np.transpose(image3D)