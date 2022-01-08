import sys
import os
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit, TaurusValueCheckBox, TaurusValueComboBox
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from _functools import partial
import subprocess

from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from DeviceServers.DS_Widget import VisType


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


def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None)
    panel = QtWidgets.QWidget()
    panel.setWindowTitle('PYCONLYSE')
    panel.setWindowIcon(QIcon('icons//main_icon.png'))

    layout_main = Qt.QVBoxLayout()
    setattr(panel, f'layout_main', layout_main)

    lo_type= Qt.QHBoxLayout()
    lo_NETIO = Qt.QHBoxLayout()
    lo_STANDA= Qt.QHBoxLayout()
    lo_TOPDIRECT= Qt.QHBoxLayout()
    lo_OWIS = Qt.QHBoxLayout()
    lo_Basler = Qt.QHBoxLayout()

    button_NETIO = TaurusCommandButton(text='NETIO', parent=panel, icon=QIcon('icons//NETIO.ico'))
    button_STANDA = TaurusCommandButton(text='STANDA', parent=panel, icon=QIcon('icons//STANDA.svg'))
    button_OWIS = TaurusCommandButton(text='OWIS', parent=panel, icon=QIcon('icons//OWIS.png'))
    button_TopDirect = TaurusCommandButton(text='TopDirect', parent=panel, icon=QIcon('icons//TopDirect.svg'))
    button_Basler = TaurusCommandButton(text='BASLER', parent=panel, icon=QIcon('icons//basler_camera.svg'))

    cbox_NETIO = TaurusValueComboBox(parent=panel)
    cbox_NETIO.addItems(['all', 'V0', 'VD2'])
    cbox_OWIS = TaurusValueComboBox(parent=panel)
    cbox_OWIS.addItems(['V0', 'VD2', 'all'])
    cbox_STANDA = TaurusValueComboBox(parent=panel)
    cbox_STANDA.addItems(['alignment', 'V0',  'V0_short', 'ELYSE'])
    cbox_TOPDIRECT = TaurusValueComboBox(parent=panel)
    cbox_TOPDIRECT.addItems(['all'])
    cbox_BASLER = TaurusValueComboBox(parent=panel)
    cbox_BASLER.addItems(['V0', 'test'])

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

    layout_main.addLayout(lo_type)
    layout_main.addLayout(lo_NETIO)
    layout_main.addLayout(lo_OWIS)
    layout_main.addLayout(lo_STANDA)
    layout_main.addLayout(lo_TOPDIRECT)
    layout_main.addLayout(lo_Basler)

    button_NETIO.clicked.connect(partial(start_cmd, 'start_NETIO_client.cmd', cbox_NETIO))
    button_STANDA.clicked.connect(partial(start_cmd, 'start_STANDA_client.cmd', cbox_STANDA))
    button_TopDirect.clicked.connect(partial(start_cmd, 'start_TOPDIRECT_client.cmd', cbox_TOPDIRECT))
    button_OWIS.clicked.connect(partial(start_cmd, 'start_OWIS_client.cmd', cbox_OWIS))
    button_Basler.clicked.connect(partial(start_cmd, 'start_BASLER_client.cmd', cbox_BASLER))

    panel.setMinimumWidth(300)
    panel.setLayout(layout_main)
    panel.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
