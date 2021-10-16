import sys
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusValueSpinBox, TaurusWheelEdit
from taurus.qt.qtgui.panel.taurusmodelchooser import TaurusModelSelectorItem
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon

from typing import List
from _functools import partial



class OWIS_PS90(Qt.QWidget):

    def __init__(self, device_name: str,  parent=None):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.layout_main = Qt.QVBoxLayout()
        self.register_DS(device_name)

        self.setLayout(self.layout_main)

    def register_DS(self, dev_name, group_number=1):
        setattr(self, f'ds_{dev_name}', Device(dev_name))
        ds: Device = getattr(self, f'ds_{dev_name}')
        # Logging level
        try:
            ds.set_logging_level(3)
        except Exception as e:
            print(e)

        setattr(self, f'name_{dev_name}', ds.get_property('friendly_name')['friendly_name'][0])

        name = getattr(self, f'name_{dev_name}')

        setattr(self, f'layout_main_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_pos_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_preset_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_info_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_error_info_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_buttons_{dev_name}', Qt.QHBoxLayout())
        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_pos: Qt.QLayout = getattr(self, f'layout_pos_{dev_name}')
        lo_info: Qt.QLayout = getattr(self, f'layout_info_{dev_name}')
        lo_error_info: Qt.QLayout = getattr(self, f'layout_error_info_{dev_name}')
        lo_preset: Qt.QLayout = getattr(self, f'layout_preset_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')

        # State and status PS90
        widgets = [TaurusLabel(), TaurusLed(), TaurusLabel()]
        i = 1
        for s in widgets:
            setattr(self, f's{i}_{dev_name}', s)
            i += 1
        s1: TaurusLabel = getattr(self, f's1_{dev_name}')
        s2 = getattr(self, f's2_{dev_name}')
        s3 = getattr(self, f's3_{dev_name}')

        s1.setText(name)
        s2.model = f'{dev_name}/state'
        s3.model = f'{dev_name}/status'
        lo_status.addWidget(s1)
        lo_status.addWidget(s2)
        lo_status.addWidget(s3)

        # ERRORS and INFO
        error = TaurusLabel()
        comments = TaurusLabel()
        error.model = f'{dev_name}/last_error'
        comments.model = f'{dev_name}/last_comments'
        lo_error_info.addWidget(error)
        lo_error_info.addWidget(comments)

        separator = Qt.QFrame()
        separator.setFrameShape(Qt.QFrame.VLine)
        separator.setSizePolicy(Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
        separator.setLineWidth(2)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_pos)
        lo_device.addLayout(lo_info)
        lo_device.addLayout(lo_error_info)
        lo_device.addLayout(lo_buttons)

        self.layout_main.addLayout(lo_device)


    def set_clicked(self, dev_name):
        p: TaurusValueLineEdit = getattr(self, f'p4_{dev_name}')
        try:
            val = p.text()
            val = float(val)
        except (ValueError, TypeError):
            val = 0
            p.setText('0')
        device: Device = getattr(self, f'ds_{dev_name}')
        device.define_position(val)

    def rb_clicked(self, value: str, dev_name: str):
        pos = float(value)
        ds: Device = getattr(self, f'ds_{dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{dev_name}')
        p3.setValue(pos)
        ds.move_axis_abs(pos)


layouts = {'V0': [2, 3, 4], 'VD2': [1]}


def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None, )
    panel = QtWidgets.QWidget()
    panel.setWindowTitle('OWIS')
    panel.setWindowIcon(QIcon('icons//OWIS.png'))

    layout_main = Qt.QVBoxLayout()
    setattr(panel, f'layout_main', layout_main)

    layout_main.addWidget(OWIS_PS90(device_name='manip/general/ds_owis_ps90'))

    panel.setLayout(layout_main)
    panel.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
