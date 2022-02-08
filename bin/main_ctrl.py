import sys
import os
from taurus import Device
from taurus.core.tango import DevState
import imageio
import numpy as np
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit, TaurusValueCheckBox, TaurusValueComboBox
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from _functools import partial
import subprocess
from threading import Thread
from tango import Database
import pyqtgraph as pg

from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from DeviceServers.DS_Widget import VisType
from functools import partial

type_vis = VisType.FULL


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
        print(f'Device {dev_name} {i}/{len(devices)}')
        dev = Device(dev_name)
        taurus_devices[dev_name] = dev
        if check:
            state = dev.state
        else:
            state = '-1'
        lab = QtWidgets.QLabel(dev_name)
        labels[dev_name] = lab

        layout_devices.addWidget(lab, r, c)
        c += 1
        if c == columns:
            c = 0
            r += 1
        i += 1
        break

    return taurus_devices, labels


def set_state(taurus_devices, labels):
    from time import sleep
    while True:
        for dev_name, dev in taurus_devices.items():
            sleep(0.15)
            state_ds = dev.state
            if state_ds == 4:
                labels[dev_name].setStyleSheet(f"background-color: red")
            else:
                state = dev.State()
                if state == DevState.ON:
                    labels[dev_name].setStyleSheet(f"background-color: green")
                elif state == DevState.STANDBY:
                    labels[dev_name].setStyleSheet(f"background-color: yellow")
                elif state == DevState.OFF:
                    labels[dev_name].setStyleSheet(f"background-color: gray")
                elif state == DevState.FAULT:
                    labels[dev_name].setStyleSheet(f"background-color: red")
                else:
                    labels[dev_name].setStyleSheet(f"background-color: purple")

        sleep(2)


def show_map(main_widget):
    map = QtWidgets.QWidget()
    layout_map_main = QtWidgets.QHBoxLayout()
    layout_map_image = QtWidgets.QHBoxLayout()
    layout_map_labels = QtWidgets.QHBoxLayout()
    layout_map_main.addLayout(layout_map_image)
    layout_map_main.addLayout(layout_map_labels)
    from PIL import Image
    imageWidget = pg.GraphicsLayoutWidget()
    vb = imageWidget.addViewBox(row=1, col=1)
    # im = imageio.imread('C:\\dev\\pyconlyse\\bin\\icons\\layout.jpg')
    im = np.array(Image.open('C:\\dev\\pyconlyse\\bin\\icons\\layout.jpg'))

    img = pg.ImageItem()
    img.setImage(np.transpose(im, (1, 0, 2)))
    vb.addItem(img)
    vb.setAspectLocked(True)
    vb.invertY(True)


    layout_map_image.addWidget(imageWidget)
    map.setLayout(layout_map_main)
    main_widget.map_widget = map
    map.setGeometry(300, 300, 1000, 800)
    map.setWindowTitle('Map')
    map.show()


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
    lo_laser_pointing = Qt.QHBoxLayout()

    # Buttons
    button_NETIO = TaurusCommandButton(text='NETIO', parent=panel, icon=QIcon('icons//NETIO.ico'))
    button_STANDA = TaurusCommandButton(text='STANDA', parent=panel, icon=QIcon('icons//STANDA.svg'))
    button_OWIS = TaurusCommandButton(text='OWIS', parent=panel, icon=QIcon('icons//OWIS.png'))
    button_TopDirect = TaurusCommandButton(text='TopDirect', parent=panel, icon=QIcon('icons//TopDirect.svg'))
    button_Basler = TaurusCommandButton(text='BASLER', parent=panel, icon=QIcon('icons//basler_camera.svg'))
    button_laser_pointing = TaurusCommandButton(text='Pointing', parent=panel, icon=QIcon('icons//laser_pointing.svg'))

    # Cboxes
    cbox_NETIO = TaurusValueComboBox(parent=panel)
    cbox_NETIO.addItems(['all', 'V0', 'VD2'])
    cbox_OWIS = TaurusValueComboBox(parent=panel)
    cbox_OWIS.addItems(['V0', 'VD2', 'all'])
    cbox_STANDA = TaurusValueComboBox(parent=panel)
    cbox_STANDA.addItems(['alignment', 'V0',  'V0_short', 'ELYSE'])
    cbox_TOPDIRECT = TaurusValueComboBox(parent=panel)
    cbox_TOPDIRECT.addItems(['all'])
    cbox_BASLER = TaurusValueComboBox(parent=panel)
    cbox_BASLER.addItems(['V0', 'Cam1', 'Cam2', 'Cam3'])
    cbox_laser_pointing = TaurusValueComboBox(parent=panel)
    cbox_laser_pointing.addItems(['Cam1', 'Cam2', 'Cam3', 'V0', '3P'])

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
    lo_laser_pointing.addWidget(button_laser_pointing)
    lo_laser_pointing.addWidget(cbox_laser_pointing)

    layout_clients.addLayout(lo_type)
    layout_clients.addLayout(lo_NETIO)
    layout_clients.addLayout(lo_OWIS)
    layout_clients.addLayout(lo_STANDA)
    layout_clients.addLayout(lo_TOPDIRECT)
    layout_clients.addLayout(lo_Basler)

    separator_devices = QtWidgets.QFrame()
    separator_devices.setFrameShape(QtWidgets.QFrame.HLine)
    separator_devices.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
    separator_devices.setLineWidth(2)

    layout_clients.addWidget(separator_devices)
    layout_clients.addLayout(lo_laser_pointing)
    vspacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
    layout_clients.addSpacerItem(vspacer)

    button_NETIO.clicked.connect(partial(start_cmd, 'start_NETIO_client.cmd', cbox_NETIO))
    button_STANDA.clicked.connect(partial(start_cmd, 'start_STANDA_client.cmd', cbox_STANDA))
    button_TopDirect.clicked.connect(partial(start_cmd, 'start_TOPDIRECT_client.cmd', cbox_TOPDIRECT))
    button_OWIS.clicked.connect(partial(start_cmd, 'start_OWIS_client.cmd', cbox_OWIS))
    button_Basler.clicked.connect(partial(start_cmd, 'start_BASLER_client.cmd', cbox_BASLER))
    button_laser_pointing.clicked.connect(partial(start_cmd, 'start_laser_pointing_client.cmd', cbox_laser_pointing))

    tab1.setLayout(layout_clients)
    layout_devices_tab = QtWidgets.QVBoxLayout()
    layout_devices_tab.addLayout(layout_devices)
    button_map = QtWidgets.QPushButton('Map')
    button_map.clicked.connect(partial(show_map, panel))
    layout_devices_tab.addWidget(button_map)
    tab2.setLayout(layout_devices_tab)

    layout_main.addWidget(tabs)
    taurus_devices, labels = set_devices_states(layout_devices, False)

    panel.setMinimumWidth(300)
    panel.setLayout(layout_main)
    panel.show()
    states_thread = Thread(target=set_state, args=[taurus_devices, labels])
    states_thread.start()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
