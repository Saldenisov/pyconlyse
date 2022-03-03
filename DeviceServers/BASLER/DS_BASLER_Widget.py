from collections import deque

import numpy as np
import pyqtgraph as pg
from taurus import Device
from taurus.core import TaurusDevState
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox

from DeviceServers.DS_Widget import DS_General_Widget, VisType


class Basler_camera(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.grabbing = False
        self.positions = {'X': deque([], maxlen=120), 'Y': deque([], maxlen=120)}
        super().__init__(device_name, parent, vis_type)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.image_listener)

    def register_DS_full(self, group_number=1):
        super(Basler_camera, self).register_DS_full()
        dev_name = self.dev_name

        ds: Device = getattr(self, f'ds_{dev_name}')
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
        lo_parameters2: Qt.QLayout = getattr(self, f'layout_parameters2_{dev_name}')
        lo_image: Qt.QLayout = getattr(self, f'layout_image_{dev_name}')

        # State and status
        self.set_state_status(False)

        # Image
        self.set_image(lo_image)

        # Buttons and commands
        grabbing_led = TaurusLed()
        grabbing_led.model = f'{dev_name}/isgrabbing'
        setattr(self, f'button_start_grabbing_{dev_name}', TaurusCommandButton(text='Grab'))
        button_start_grabbing: TaurusCommandButton = getattr(self, f'button_start_grabbing_{dev_name}')
        button_start_grabbing.clicked.connect(self.grab_clicked)

        setattr(self, f'button_init_{dev_name}', TaurusCommandButton(command='init'))
        button_init: TaurusCommandButton = getattr(self, f'button_init_{dev_name}')
        button_init.setModel(dev_name)

        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        lo_buttons.addWidget(grabbing_led)
        lo_buttons.addWidget(button_start_grabbing)
        lo_buttons.addWidget(button_init)
        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)

        # Camera parameters
        self.set_camera_parameters()

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_image)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_parameters2)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        super(Basler_camera, self).register_DS_min()
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

    def set_camera_parameters(self):
        dev_name = self.dev_name
        ds = self.ds
        self.width = TaurusValueSpinBox()
        self.width.model = f'{dev_name}/width'

        self.height = TaurusValueSpinBox()
        self.height.model = f'{dev_name}/height'

        self.offsetX = TaurusValueSpinBox()
        self.offsetX.model = f'{dev_name}/offsetX'

        self.offsetY = TaurusValueSpinBox()
        self.offsetY.model = f'{dev_name}/offsetY'

        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
        lo_parameters2: Qt.QLayout = getattr(self, f'layout_parameters2_{dev_name}')

        lo_parameters.addWidget(TaurusLabel('Width'))
        lo_parameters.addWidget(self.width)
        lo_parameters.addWidget(TaurusLabel('Height'))
        lo_parameters.addWidget(self.height)
        lo_parameters.addWidget(TaurusLabel('offsetX'))
        lo_parameters.addWidget(self.offsetX)
        lo_parameters.addWidget(TaurusLabel('offsetY'))
        lo_parameters.addWidget(self.offsetY)

        self.pixel = TaurusValueComboBox()
        self.pixel.addItems(['Mono8', 'BayerRG8', 'BayerRG12', 'BayerRG12p'])
        self.pixel.model = f'{dev_name}/format_pixel'

        self.trigger_mode = TaurusValueComboBox()
        self.trigger_mode.addItems(['On', 'Off'])
        self.trigger_mode.currentIndexChanged.connect(self.trigger_mode_changed)

        self.trigger_delay = TaurusValueSpinBox()
        self.trigger_delay.model = f'{dev_name}/trigger_delay'

        self.exposure_time = TaurusValueSpinBox()
        self.exposure_time.model = f'{dev_name}/exposure_time'

        if ds.state == TaurusDevState.Ready:
            self.width.setValue(ds.width)
            self.height.setValue(ds.height)
            self.offsetX.setValue(ds.offsetX)
            self.offsetY.setValue(ds.offsetY)
            self.trigger_delay.setValue(ds.trigger_delay)
            self.exposure_time.setValue(ds.exposure_time_local)

        lo_parameters2.addWidget(TaurusLabel('Trigger'))
        lo_parameters2.addWidget(self.trigger_mode)
        lo_parameters2.addWidget(TaurusLabel('Format'))
        lo_parameters2.addWidget(self.pixel)
        lo_parameters2.addWidget(TaurusLabel('Trigger Delay'))
        lo_parameters2.addWidget(self.trigger_delay)
        lo_parameters2.addWidget(TaurusLabel('Exposure Time'))
        lo_parameters2.addWidget(self.exposure_time)

    def set_image(self, lo_image):
        self.view = pg.ImageView()
        image = np.ones(shape=(512, 512))
        self.view.setImage(image)
        self.view.autoRange()
        self.view.setMinimumSize(300, 300)
        lo_image.addWidget(self.view)

        self.roi_circle = pg.CircleROI([0, 0], size=2, pen=pg.mkPen('r', width=2))
        self.view.addItem(self.roi_circle)

        layout_cg_threshold = Qt.QHBoxLayout()
 
        self.cg_threshold = TaurusValueSpinBox()
        self.cg_threshold.model = f'{self.dev_name}/center_gravity_threshold'
        self.cg_threshold.setValue(self.ds.center_gravity_threshold)
        self.cg_threshold.setMaximumWidth(60)
        self.label_X_pos = TaurusLabel(f'X position: ')
        self.label_Y_pos = TaurusLabel(f'Y position: ')

        layout_cg_threshold.addWidget(self.label_X_pos)
        layout_cg_threshold.addWidget(self.label_Y_pos)
        layout_cg_threshold.addWidget(TaurusLabel('Threshold CG'))
        layout_cg_threshold.addWidget(self.cg_threshold)

        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)
        win = pg.GraphicsLayoutWidget(show=True, title="Point Tracking")
        p1 = win.addPlot(title="X position", y=self.positions['X'])
        p1.setLabel('left', "X pos", units='pixel')
        p1.setLabel('bottom', "N of measurement", units='')
        p1.showGrid(x=True, y=True)
        self.x_pos = p1.plot(self.positions['X'])

        p2 = win.addPlot(title="Y position", y=self.positions['Y'])
        p2.setLabel('left', "Y pos", units='pixel')
        p2.setLabel('bottom', "N of measurement", units='')
        p2.showGrid(x=True, y=True)
        self.y_pos = p2.plot(self.positions['Y'])
        lo_image.addLayout(layout_cg_threshold)
        lo_image.addWidget(win)

        cmap = pg.colormap.get('CET-L9')
        self.view.setColorMap(cmap)

    def register_full_layouts(self):
        super(Basler_camera, self).register_full_layouts()
        setattr(self, f'layout_parameters_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_parameters2_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}', Qt.QVBoxLayout())

    def register_min_layouts(self):
        super(Basler_camera, self).register_min_layouts()
        setattr(self, f'layout_image_{self.dev_name}', Qt.QVBoxLayout())

    def trigger_mode_changed(self):
        state = self.trigger_mode.currentText()
        self.ds.set_trigger_mode = 1 if state == 'On' else 0

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
            self.timer.start(150)
            self.grabbing = True
            button_start_grabbing.setText('Grabbing')

    def image_listener(self):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        self.view.setImage(self.convert_image(ds.image))

        positions = eval(ds.cg)
        x_pos = self.positions['X']
        x_pos.append(positions['X'])
        self.positions['X'] = x_pos
        y_pos = self.positions['Y']
        y_pos.append(positions['Y'])
        self.positions['Y'] = y_pos
        x = positions['X']
        y = positions['Y']
        self.label_X_pos.setText(f'X position: {x}')
        self.label_Y_pos.setText(f'Y position: {y}')
        self.x_pos.setData(self.positions['X'])
        self.y_pos.setData(self.positions['Y'])
        self.roi_circle.setPos([x, y])


    def convert_image(self, image):
        image2D = image
        shp = (int(image2D.shape[0] / 3), image2D.shape[1], 3)
        image3D = image2D.reshape(np.roll(shp, 1)).transpose(1, 2, 0)
        return np.transpose(image3D)