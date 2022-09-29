import subprocess
import sys
from _functools import partial
from pathlib import Path
from threading import Thread
from typing import Dict
from time import sleep
import imageio
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from tango import Database
from taurus import Device
from taurus.core.tango import DevState
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.input import TaurusValueComboBox
from typing import List
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from DeviceServers.DS_Widget import VisType
from functools import partial

type_vis = VisType.FULL
from gui.MyWidgets import MyQLabel


def start_cmd(call: str, cbox: TaurusValueComboBox):
    c_idx = cbox.currentIndex()
    arg = cbox.itemText(c_idx)
    global type_vis
    calling = f'{call} {arg} {type_vis.value}'
    print(f'Calling {calling}')
    subprocess.call([call, arg, type_vis.value])


def rb_clicked(value: str):
    global type_vis
    type_vis = VisType(value)


def set_devices_states(layout_devices: QtWidgets.QLayout, check=False):
    db = Database()
    servers = ['ELYSE', 'manip']
    devices = []
    for server in servers:
        devices = devices + list(db.get_device_exported(f"{server}*"))
    labels = {}
    taurus_devices = {}
    columns = 3
    r = 0
    c = 0
    i = 1
    for dev_name in devices:
        # print(f'Device {dev_name} {i}/{len(devices)}')
        # dev = Device(dev_name)
        # taurus_devices[dev_name] = dev
        lab = MyQLabel(dev_name)
        labels[dev_name] = lab

        layout_devices.addWidget(lab, r, c)
        c += 1
        if c == columns:
            c = 0
            r += 1
        i += 1
    return labels
    # return taurus_devices, labels


def set_state(labels):
    from time import sleep
    db = Database()
    servers = ['ELYSE', 'manip']
    devices = []
    for server in servers:
        devices = devices + list(db.get_device_exported(f"{server}*"))
    taurus_devices = {}
    i = 0
    for dev_name in devices:
        i += 1
        print(f'Device {dev_name} {i}/{len(devices)}')
        dev = Device(dev_name)
        taurus_devices[dev_name] = dev
    while True:
        for dev_name, dev in taurus_devices.items():
            sleep(0.15)
            state_ds = dev.state
            if state_ds == 4:
                labels[dev_name].update_style(f"background-color: red")
            else:
                state = dev.State()
                if state == DevState.ON:
                    labels[dev_name].update_style(f"background-color: green")
                elif state == DevState.STANDBY:
                    labels[dev_name].update_style(f"background-color: yellow")
                elif state == DevState.OFF:
                    labels[dev_name].update_style(f"background-color: gray")
                elif state == DevState.FAULT:
                    labels[dev_name].update_style(f"background-color: red")
                else:
                    labels[dev_name].update_style(f"background-color: purple")
        sleep(2)


def label_focus(map, event):

    positions = {'ELYSE/clocks/SYNC_MAIN': (300, 300), 'ELYSE/motorized_devices/DE1': (11705, 1584),
                 'ELYSE/motorized_devices/DE2': (4118, 2366), 'ELYSE/motorized_devices/MM1_X': (11152, 1578),
                 'ELYSE/motorized_devices/MM1_Y': (11152, 1578), 'ELYSE/motorized_devices/MM2_X': (11171, 2381),
                 'ELYSE/motorized_devices/MM2_Y': (11171, 2381), 'ELYSE/motorized_devices/MME_X': (11521, 2118),
                 'ELYSE/motorized_devices/MME_Y': (11521, 2118), 'manip/ELYSE/PDU_ELYSE': (300, 300),
                 'manip/general/DS_OWIS_PS90': (3273, 664), 'manip/SD1/PDU_SD1': (300, 300),
                 'manip/SD2/PDU_SD2': (300, 300), 'manip/V0/Cam1_V0': (157, 3501), 'manip/V0/Cam2_V0': (1888, 2559),
                 'manip/V0/Cam3_V0': (300, 300), 'manip/V0/DV01': (1010, 2235), 'manip/V0/DV02': (754, 2363),
                 'manip/V0/DV03': (2921, 2247), 'manip/V0/DV04': (920, 540), 'manip/V0/F1': (300, 300),
                 'manip/V0/L-2_1': (300, 300), 'manip/V0/LaserPointing-Cam1': (226, 3936),
                 'manip/V0/LaserPointing-Cam2': (2331, 2270), 'manip/V0/LaserPointing-Cam3': (300, 300),
                 'manip/V0/MM3_X': (60, 630), 'manip/V0/MM3_Y': (60, 630), 'manip/V0/MM4_X': (60, 1100),
                 'manip/V0/MM4_Y': (60, 1100), 'manip/V0/OPA_X': (300, 300), 'manip/V0/OPA_Y': (300, 300),
                 'manip/V0/PDU_VO': (300, 300), 'manip/V0/S1': (209, 3961), 'manip/V0/S2': (2351, 2261),
                 'manip/V0/S3': (300, 300), 'manip/V0/TS_OPA_m': (2620, 3697), 'manip/V0/TS_SC_m': (2192, 4194),
                 'manip/VD2/PDU_VD2': (300, 300)}

    if event in positions:
        x = 120
        y = 120
        if event not in map.circles:
            pos = list(positions[event])
            circle = pg.CircleROI([pos[0] - x/2, pos[1] - y/2], [x, y], movable=False, resizable=False,
                                  pen=pg.mkPen('r', width=2))
            map.view.addItem(circle)
            map.circles[event] = circle
        else:
            circle = map.circles[event]
            del map.circles[event]
            map.view.removeItem(circle)


def show_map(main_widget, labels: Dict):
    map = QtWidgets.QWidget()
    layout_map_main = QtWidgets.QVBoxLayout()
    layout_map_image = QtWidgets.QHBoxLayout()
    layout_map_labels = QtWidgets.QHBoxLayout()
    layout_map_main.addLayout(layout_map_image)
    layout_map_main.addLayout(layout_map_labels)

    imageWidget = pg.GraphicsLayoutWidget()
    vb = imageWidget.addViewBox(row=1, col=1)
    im = imageio.imread('C:\\dev\\pyconlyse\\bin\\icons\\Main_layout_1200.png')

    img = pg.ImageItem()
    img.setImage(np.transpose(im, (1, 0, 2)))

    label = QtWidgets.QLabel('Position')
    layout_map_labels.addWidget(label)

    def mouseMoved(label, img, evt):
        pos = evt[0]
        if img.sceneBoundingRect().contains(pos):
            mousePoint = vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            label.setText("<span style='font-size: 12pt'>x=%0.1f,   <span style='color: red'>y1=%0.1f</span>" %
                          (mousePoint.x(), mousePoint.y()))
            # vLine.setPos(mousePoint.x())
            # hLine.setPos(mousePoint.y())

    proxy = pg.SignalProxy(vb.scene().sigMouseMoved, rateLimit=30, slot=partial(mouseMoved, label, img))
    map.proxy = proxy
    vb.addItem(img)

    vb.setAspectLocked(True)
    vb.invertY(True)
    map.view = vb
    map.img = img
    map.circles = {}
    map.labels = labels
    layout_map_image.addWidget(imageWidget)
    map.setLayout(layout_map_main)
    main_widget.map_widget = map
    map.setGeometry(300, 300, 1200, 700)
    map.setWindowTitle('Map')
    map.show()

    for label in labels.values():
        label: MyQLabel = label
        label.clicked.connect(partial(label_focus, map))


def rpi_toggle_pin(rpi_device: Device, pin):
    state = rpi_device.get_pin_state(pin)
    if state == -1:
        print(f'Wrong pin {pin} state.')
    else:
        rpi_device.set_pin_state([pin, 1])
        sleep(0.25)
        rpi_device.set_pin_state([pin, 0])


def activate_buttons(widgets: List[QtWidgets.QWidget]):
    import keyboard
    while True:
        sleep(0.15)
        if keyboard.is_pressed('q'):
            for widget in widgets:
                widget.setEnabled(True)
        else:
            for widget in widgets:
                widget.setEnabled(False)


def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None)
    tabs = QtWidgets.QTabWidget()
    tab1 = QtWidgets.QWidget()
    tab2 = QtWidgets.QWidget()
    tabs.addTab(tab1, 'Clients')
    tabs.addTab(tab2, 'Devices')

    panel = QtWidgets.QWidget()
    panel.setWindowTitle('PYCONLYSE')
    panel.setWindowIcon(QIcon('icons//main_icon.png'))

    layout_clients = Qt.QVBoxLayout()
    layout_devices= Qt.QGridLayout()
    layout_main = Qt.QVBoxLayout()
    setattr(panel, f'layout_main', layout_main)

    lo_type= Qt.QHBoxLayout()
    lo_NETIO = Qt.QHBoxLayout()
    lo_STANDA= Qt.QHBoxLayout()
    lo_TOPDIRECT= Qt.QHBoxLayout()
    lo_OWIS = Qt.QHBoxLayout()
    lo_Basler = Qt.QHBoxLayout()
    lo_Laser_pointing = Qt.QHBoxLayout()
    lo_Andor_ccd = Qt.QHBoxLayout()
    lo_Avantes_ccd = Qt.QHBoxLayout()
    lo_Archive = Qt.QHBoxLayout()
    lo_Experiment = Qt.QHBoxLayout()
    lo_lights = Qt.QHBoxLayout()

    # Buttons
    button_NETIO = TaurusCommandButton(text='NETIO', parent=panel, icon=QIcon('icons//NETIO.ico'))
    button_STANDA = TaurusCommandButton(text='STANDA', parent=panel, icon=QIcon('icons//STANDA.svg'))
    button_OWIS = TaurusCommandButton(text='OWIS', parent=panel, icon=QIcon('icons//OWIS.png'))
    button_TopDirect = TaurusCommandButton(text='TopDirect', parent=panel, icon=QIcon('icons//TopDirect.svg'))
    button_Basler = TaurusCommandButton(text='BASLER', parent=panel, icon=QIcon('icons//basler_camera.svg'))
    button_laser_pointing = TaurusCommandButton(text='Pointing', parent=panel, icon=QIcon('icons//laser_pointing.svg'))
    button_andor_ccd = TaurusCommandButton(text='ANDOR CCD', parent=panel, icon=QIcon('icons//Andor_CCD.svg'))
    button_avantes_ccd = TaurusCommandButton(text='AVANTES CCD', parent=panel, icon=QIcon('icons//AVANTES_CCD.svg'))
    button_light_room = TaurusCommandButton(text='SM light', parent=panel, icon=QIcon('icons//light.png'))
    button_laser = TaurusCommandButton(text='Laser', parent=panel, icon=QIcon('icons//laser.svg'))
    button_laser.setEnabled(False)
    button_archive = TaurusCommandButton(text='Archive', parent=panel, icon=QIcon('icons//archive.svg'))
    button_experiment = TaurusCommandButton(text='Experiment', parent=panel, icon=QIcon('icons//experiment.png'))

    # Cboxes
    cbox_NETIO = TaurusValueComboBox(parent=panel)
    cbox_NETIO.addItems(['all', 'V0', 'VD2'])
    cbox_OWIS = TaurusValueComboBox(parent=panel)
    cbox_OWIS.addItems(['V0', 'VD2', 'all'])
    cbox_STANDA = TaurusValueComboBox(parent=panel)
    cbox_STANDA.addItems(['alignment', 'V0',  'V0_short', 'ELYSE', 'OPA'])
    cbox_TOPDIRECT = TaurusValueComboBox(parent=panel)
    cbox_TOPDIRECT.addItems(['VD2','all'])
    cbox_BASLER = TaurusValueComboBox(parent=panel)
    cbox_BASLER.addItems(['V0', 'Cam1', 'Cam2', 'Cam3'])
    cbox_andor_ccd = TaurusValueComboBox(parent=panel)
    cbox_andor_ccd.addItems(['V0'])
    cbox_avantes_ccd = TaurusValueComboBox(parent=panel)
    cbox_avantes_ccd.addItems(['Spectrometer'])
    cbox_laser_pointing = TaurusValueComboBox(parent=panel)
    cbox_laser_pointing.addItems(['Cam1', 'Cam2', 'Cam3', 'V0', '3P'])
    cbox_archive = TaurusValueComboBox(parent=panel)
    cbox_archive.addItems(['Main'])
    cbox_experiment = TaurusValueComboBox(parent=panel)
    cbox_experiment.addItems(['Pump-Probe', '3P', 'Streak-camera'])

    # Type of vizualization
    group_visualization = QtWidgets.QGroupBox('Type')
    group_layout = Qt.QHBoxLayout()
    for typ in VisType:
        rb = QtWidgets.QRadioButton(text=f'{typ.value}')
        group_layout.addWidget(rb)
        rb.toggled.connect(partial(rb_clicked, rb.text()))
    rb.setChecked(True)
    group_visualization.setLayout(group_layout)
    lo_type.addWidget(group_visualization)

    lo_NETIO.addWidget(button_NETIO)
    lo_NETIO.addWidget(cbox_NETIO)
    lo_OWIS.addWidget(button_OWIS)
    lo_OWIS.addWidget(cbox_OWIS)
    lo_STANDA.addWidget(button_STANDA)
    lo_STANDA.addWidget(cbox_STANDA)
    lo_TOPDIRECT.addWidget(button_TopDirect)
    lo_TOPDIRECT.addWidget(cbox_TOPDIRECT)
    lo_Basler.addWidget(button_Basler)
    lo_Basler.addWidget(cbox_BASLER)
    lo_Laser_pointing.addWidget(button_laser_pointing)
    lo_Laser_pointing.addWidget(cbox_laser_pointing)
    lo_Andor_ccd.addWidget(button_andor_ccd)
    lo_Andor_ccd.addWidget(cbox_andor_ccd)
    lo_Avantes_ccd.addWidget(button_avantes_ccd)
    lo_Avantes_ccd.addWidget(cbox_avantes_ccd)
    lo_lights.addWidget(button_laser)
    lo_lights.addWidget(button_light_room)
    lo_Archive.addWidget(button_archive)
    lo_Archive.addWidget(cbox_archive)
    lo_Experiment.addWidget(button_experiment)
    lo_Experiment.addWidget(cbox_experiment)

    layout_clients.addLayout(lo_type)
    layout_clients.addLayout(lo_NETIO)
    layout_clients.addLayout(lo_OWIS)
    layout_clients.addLayout(lo_STANDA)
    layout_clients.addLayout(lo_TOPDIRECT)
    layout_clients.addLayout(lo_Basler)
    layout_clients.addLayout(lo_Andor_ccd)
    layout_clients.addLayout(lo_Avantes_ccd)

    separator_devices = QtWidgets.QFrame()
    separator_devices.setFrameShape(QtWidgets.QFrame.HLine)
    separator_devices.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
    separator_devices.setLineWidth(2)

    separator_light = QtWidgets.QFrame()
    separator_light.setFrameShape(QtWidgets.QFrame.HLine)
    separator_light.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
    separator_light.setLineWidth(2)

    layout_clients.addWidget(separator_devices)
    layout_clients.addWidget(QtWidgets.QLabel('Derivative clients'))
    layout_clients.addLayout(lo_Laser_pointing)
    layout_clients.addLayout(lo_Archive)
    layout_clients.addLayout(lo_Experiment)
    layout_clients.addWidget(separator_light)
    layout_clients.addLayout(lo_lights)
    layout_clients.addWidget(QtWidgets.QLabel("Press 'q' if you want to activate buttons."))
    vspacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
    layout_clients.addSpacerItem(vspacer)

    button_NETIO.clicked.connect(partial(start_cmd, 'start_NETIO_client.cmd', cbox_NETIO))
    button_STANDA.clicked.connect(partial(start_cmd, 'start_STANDA_client.cmd', cbox_STANDA))
    button_TopDirect.clicked.connect(partial(start_cmd, 'start_TOPDIRECT_client.cmd', cbox_TOPDIRECT))
    button_OWIS.clicked.connect(partial(start_cmd, 'start_OWIS_client.cmd', cbox_OWIS))
    button_Basler.clicked.connect(partial(start_cmd, 'start_BASLER_client.cmd', cbox_BASLER))
    button_laser_pointing.clicked.connect(partial(start_cmd, 'start_laser_pointing_client.cmd', cbox_laser_pointing))
    button_andor_ccd.clicked.connect(partial(start_cmd, 'start_ANDOR_CCD_client.cmd', cbox_andor_ccd))
    button_avantes_ccd.clicked.connect(partial(start_cmd, 'start_AVANTES_CCD_client.cmd', cbox_avantes_ccd))
    button_archive.clicked.connect(partial(start_cmd, 'start_ARCHIVE_client.cmd', cbox_archive))
    button_experiment.clicked.connect(partial(start_cmd, 'start_EXPERIMENT_client.cmd', cbox_experiment))

    rpi_device = Device('manip/v0/rpi4_gpio_v0')
    light_pin = 3
    laser_pin = 4
    button_laser.clicked.connect(partial(rpi_toggle_pin, rpi_device, laser_pin))
    button_light_room.clicked.connect(partial(rpi_toggle_pin, rpi_device, light_pin))

    tab1.setLayout(layout_clients)
    layout_devices_tab = QtWidgets.QVBoxLayout()
    layout_devices_tab.addLayout(layout_devices)
    button_map = QtWidgets.QPushButton('Map')
    layout_devices_tab.addWidget(button_map)
    tab2.setLayout(layout_devices_tab)

    layout_main.addWidget(tabs)
    labels = set_devices_states(layout_devices, False)

    button_map.clicked.connect(partial(show_map, panel, labels))

    panel.setMinimumWidth(300)
    panel.setLayout(layout_main)
    panel.show()
    states_thread = Thread(target=set_state, args=[labels])
    states_thread.start()
    buttons_activate = Thread(target=activate_buttons, args=[[button_laser]])
    buttons_activate.start()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
