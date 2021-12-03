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


def start_cmd(call: str, cbox: TaurusValueComboBox):
    arg = ''
    c_idx = cbox.currentIndex()
    arg = cbox.itemText(c_idx)
    print(f'Calling {call} {arg}')
    subprocess.call(f'{call} {arg}')


def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None, )
    panel = QtWidgets.QWidget()
    panel.setWindowTitle('PYCONLYSE')
    panel.setWindowIcon(QIcon('icons//main_icon.png'))

    layout_main = Qt.QVBoxLayout()
    setattr(panel, f'layout_main', layout_main)

    lo_NETIO = Qt.QHBoxLayout()
    lo_STANDA= Qt.QHBoxLayout()
    lo_TOPDIRECT= Qt.QHBoxLayout()
    lo_OWIS = Qt.QHBoxLayout()
    button_NETIO = TaurusCommandButton(text='NETIO', parent=panel, icon=QIcon('icons//NETIO.ico'))
    button_STANDA = TaurusCommandButton(text='STANDA', parent=panel, icon=QIcon('icons//STANDA.svg'))
    button_OWIS = TaurusCommandButton(text='OWIS', parent=panel, icon=QIcon('icons//OWIS.png'))
    button_TopDirect = TaurusCommandButton(text='TopDirect', parent=panel, icon=QIcon('icons//TopDirect.svg'))

    cbox_NETIO = TaurusValueComboBox(parent=panel)
    cbox_NETIO.addItems(['all', 'V0', 'VD2'])
    cbox_OWIS = TaurusValueComboBox(parent=panel)
    cbox_OWIS.addItems(['V0', 'VD2', 'all'])
    cbox_STANDA = TaurusValueComboBox(parent=panel)
    cbox_STANDA.addItems(['alignment', 'V0',  'V0_short', 'ELYSE'])
    cbox_TOPDIRECT = TaurusValueComboBox(parent=panel)
    cbox_TOPDIRECT.addItems(['all'])

    lo_NETIO.addWidget(button_NETIO)
    lo_NETIO.addWidget(cbox_NETIO)
    lo_OWIS.addWidget(button_OWIS)
    lo_OWIS.addWidget(cbox_OWIS)
    lo_STANDA.addWidget(button_STANDA)
    lo_STANDA.addWidget(cbox_STANDA)
    lo_TOPDIRECT.addWidget(button_TopDirect)
    lo_TOPDIRECT.addWidget(cbox_TOPDIRECT)

    layout_main.addLayout(lo_NETIO)
    layout_main.addLayout(lo_OWIS)
    layout_main.addLayout(lo_STANDA)
    layout_main.addLayout(lo_TOPDIRECT)

    button_NETIO.clicked.connect(partial(start_cmd, 'start_NETIO_client.cmd', cbox_NETIO))
    button_STANDA.clicked.connect(partial(start_cmd, 'start_STANDA_client.cmd', cbox_STANDA))
    button_TopDirect.clicked.connect(partial(start_cmd, 'start_TOPDIRECT_client.cmd', cbox_TOPDIRECT))
    button_OWIS.clicked.connect(partial(start_cmd, 'start_OWIS_client.cmd', cbox_OWIS))


    panel.setMinimumWidth(300)
    panel.setLayout(layout_main)
    panel.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
