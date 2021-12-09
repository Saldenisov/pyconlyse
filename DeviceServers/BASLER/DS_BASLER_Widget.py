import pyqtgraph as pg
import numpy as np
from taurus import Device
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox
import taurus_pyqtgraph as tpg
from DeviceServers.DS_Widget import DS_General_Widget


class Basler_camera(DS_General_Widget):

    def __init__(self, device_name: str, parent=None):
        super().__init__(device_name, parent)
        self.register_DS(device_name)
        ds: Device = getattr(self, f'ds_{self.dev_name}')

        # ds.subscribe_event("image", tango.EventType.CHANGE_EVENT, self.image_listener)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.image_listener)
        self.grabbing = False

    def register_DS(self, dev_name, group_number=1):
        super().register_DS(dev_name, group_number=1)

        ds: Device = getattr(self, f'ds_{self.dev_name}')
        # Logging level
        try:
            pass
            #ds.set_logging_level(3)
        except Exception as e:
            print(e)
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        setattr(self, f'layout_main_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_state_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_error_info_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_buttons_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_parameters_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_parameters2_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_image_{dev_name}', Qt.QHBoxLayout())
        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_state: Qt.QLayout = getattr(self, f'layout_state_{dev_name}')
        lo_error_info: Qt.QLayout = getattr(self, f'layout_error_info_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
        lo_parameters2: Qt.QLayout = getattr(self, f'layout_parameters2_{dev_name}')
        lo_image: Qt.QLayout = getattr(self, f'layout_image_{dev_name}')

        # State and status
        widgets = [TaurusLabel(), TaurusLed(), TaurusLabel()]
        i = 1
        for s in widgets:
            setattr(self, f's{i}_{dev_name}', s)
            i += 1
        s1: TaurusLabel = getattr(self, f's1_{dev_name}')
        s2 = getattr(self, f's2_{dev_name}')
        s3 = getattr(self, f's3_{dev_name}')

        s1.model = f'{dev_name}/camera_friendly_name'
        s2.model = f'{dev_name}/state'
        s3.model = f'{dev_name}/status'
        lo_status.addWidget(s1)
        lo_status.addWidget(s2)
        lo_status.addWidget(s3)

        self.view = pg.ImageView()
        image = ds.image
        self.view.setImage(self.convert_image(image))
        self.view.autoRange()
        self.view.setMinimumSize(450, 450)
        lo_image.addWidget(self.view)

        ## Set a custom color map
        colors = [
            (0, 0, 0),
            (45, 5, 61),
            (84, 42, 55),
            (150, 87, 60),
            (208, 171, 141),
            (255, 255, 255)
        ]
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)
        self.view.setColorMap(cmap)



        # Buttons and commands
        grabbing_led = TaurusLed()
        grabbing_led.model = f'{dev_name}/isgrabbing'
        setattr(self, f'button_start_grabbing_{dev_name}', TaurusCommandButton(text='Grab'))
        button_start_grabbing: TaurusCommandButton = getattr(self, f'button_start_grabbing_{dev_name}')
        button_start_grabbing.clicked.connect(self.grab_clicked)

        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        lo_buttons.addWidget(grabbing_led)
        lo_buttons.addWidget(button_start_grabbing)
        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)


        # Camera parameters
        self.pixel = TaurusValueComboBox()
        self.pixel.addItems(['Mono8', 'BayerRG8', 'BayerRG12', 'BayerRG12packed'])
        self.pixel.model = f'{dev_name}/format_pixel'

        self.width = TaurusValueSpinBox()
        self.width.model = f'{dev_name}/width'
        self.width.setValue(ds.width)

        self.height = TaurusValueSpinBox()
        self.height.model = f'{dev_name}/height'
        self.height.setValue(ds.height)

        self.offsetX = TaurusValueSpinBox()
        self.offsetX.model = f'{dev_name}/offsetX'
        self.offsetX.setValue(ds.offsetX)

        self.offsetY = TaurusValueSpinBox()
        self.offsetY.model = f'{dev_name}/offsetY'
        self.offsetY.setValue(ds.offsetY)


        lo_parameters.addWidget(TaurusLabel('Width'))
        lo_parameters.addWidget(self.width)
        lo_parameters.addWidget(TaurusLabel('Height'))
        lo_parameters.addWidget(self.height)
        lo_parameters.addWidget(TaurusLabel('offsetX'))
        lo_parameters.addWidget(self.offsetX)
        lo_parameters.addWidget(TaurusLabel('offsetY'))
        lo_parameters.addWidget(self.offsetY)

        lo_parameters2.addWidget(TaurusLabel('Format'))
        lo_parameters2.addWidget(self.pixel)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_parameters2)
        lo_group.addLayout(lo_device)

    def width_change(self):
        print(self.width.getValue())

    def grab_clicked(self):
        ds: Device = getattr(self, f'ds_{self.dev_name}')

        button_start_grabbing: TaurusCommandButton = getattr(self, f'button_start_grabbing_{self.dev_name}')
        if self.grabbing:
            self.timer.stop()
            ds.stop_grabbing()
            self.grabbing = False
            button_start_grabbing.setText('Grab')
        else:
            ds.start_grabbing()
            self.timer.start(250)
            self.grabbing = True
            button_start_grabbing.setText('Grabbing')

    def image_listener(self):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        self.view.setImage(self.convert_image(ds.image))

    def convert_image(self, image):
        image2D = image
        shp = (int(image2D.shape[0] / 3), image2D.shape[1], 3)
        image3D = image2D.reshape(np.roll(shp, 1)).transpose(1, 2, 0)
        return np.transpose(image3D)