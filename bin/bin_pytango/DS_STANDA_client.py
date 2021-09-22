import sys
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusValueSpinBox, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from PyQt5 import QtWidgets

from typing import List
from _functools import partial


class Standa_panel(Qt.QWidget):
    def __init__(self, devices_names: List[str], window_name='', width=4, parent=None):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.layout_main = Qt.QVBoxLayout()
        number_ds = len(devices_names)
        number_lo = 1 if number_ds // width == 0 else number_ds // width

        for lo_i in range(number_lo):
            setattr(self, f'lo_group_{lo_i}', Qt.QHBoxLayout())
            self.layout_main.addLayout(getattr(self, f'lo_group_{lo_i}'))
            separator = Qt.QFrame()
            separator.setFrameShape(Qt.QFrame.HLine)
            separator.setSizePolicy(Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
            separator.setLineWidth(3)
            self.layout_main.addWidget(separator)

        i = 0
        for dev_name in devices_names:
            group_number = i // width
            if dev_name:
                self.register_DS(dev_name, group_number)
            i += 1

        self.setLayout(self.layout_main)
        self.setWindowTitle(window_name)
        self.show()

    def register_DS(self, dev_name, group_number):
        setattr(self, f'ds_{dev_name}', Device(dev_name))
        ds: Device = getattr(self, f'ds_{dev_name}')
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')
        setattr(self, f'l_min_{dev_name}', float(ds.get_property('limit_min')['limit_min'][0]))
        setattr(self, f'l_max_{dev_name}', float(ds.get_property('limit_max')['limit_max'][0]))
        setattr(self, f'name_{dev_name}', ds.get_property('friendly_name')['friendly_name'][0])
        setattr(self, f'preset_pos_{dev_name}',
                list([float(pos) for pos in ds.get_property('preset_pos')['preset_pos']]))
        l_min, l_max = getattr(self, f'l_min_{dev_name}'), getattr(self, f'l_max_{dev_name}')
        name = getattr(self, f'name_{dev_name}')

        setattr(self, f'layout_main_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_pos_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_preset_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_info_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_buttons_{dev_name}', Qt.QHBoxLayout())
        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_pos: Qt.QLayout = getattr(self, f'layout_pos_{dev_name}')
        lo_info: Qt.QLayout = getattr(self, f'layout_info_{dev_name}')
        lo_preset: Qt.QLayout = getattr(self, f'layout_preset_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')

        # State and status
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

        # Position controls
        widgets = [TaurusLabel(), TaurusLabel(), TaurusWheelEdit(), TaurusValueLineEdit()]
        i = 1
        for p in widgets:
            name = f'p{i}_{dev_name}'
            setattr(self, f'{name}', p)
            i += 1
        p1 = getattr(self, f'p1_{dev_name}')
        p2 = getattr(self, f'p2_{dev_name}')
        p3 = getattr(self, f'p3_{dev_name}')
        p4: TaurusValueLineEdit = getattr(self, f'p{4}_{dev_name}')

        p3.setMinValue(l_min)
        p3.setMaxValue(l_max)
        p3._setDigits(3)

        lo_pos.addWidget(p1)
        lo_pos.addWidget(p2)
        lo_pos.addWidget(p3)
        lo_pos.addWidget(p4)

        p1.model, p1.bgRole = f'{dev_name}/position#label', ''
        p2.model = f'{dev_name}/position'
        p3.model = f'{dev_name}/position'
        p4.setText('0')
        p4.setFixedWidth(50)

        # preset positions
        preset_positions: List[float] = getattr(self, f'preset_pos_{dev_name}')
        i = 1
        setattr(self, f'radio_button_group_{dev_name}', Qt.QGroupBox('Preset Positions'))
        group: Qt.QGroupBox = getattr(self, f'radio_button_group_{dev_name}')
        for rb in [Qt.QRadioButton(text=str(pos)) for pos in preset_positions]:
            setattr(self, f'rb{i}_{dev_name}', rb)
            rb_l: Qt.QRadioButton = getattr(self, f'rb{i}_{dev_name}')
            lo_preset.addWidget(rb_l)
        group.setLayout(lo_preset)

        # Info
        widgets = [TaurusLabel(), TaurusLabel(), TaurusLabel(), TaurusLabel()]
        i = 1
        for inf in widgets:
            name = f'inf{i}_{dev_name}'
            setattr(self, f'{name}', inf)
            i += 1
        inf1 = getattr(self, f'inf1_{dev_name}')
        inf2 = getattr(self, f'inf2_{dev_name}')
        inf3 = getattr(self, f'inf3_{dev_name}')
        inf4 = getattr(self, f'inf4_{dev_name}')

        lo_info.addWidget(inf1)
        lo_info.addWidget(inf2)
        lo_info.addWidget(inf3)
        lo_info.addWidget(inf4)

        inf1.model = f'{dev_name}/temperature'
        inf2.model = f'{dev_name}/power_current'
        inf3.model = f'{dev_name}/power_voltage'
        inf4.model = f'{dev_name}/power_status'

        # Buttons and commands
        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_stop_{dev_name}', TaurusCommandButton(command='stop_movement'))
        button_stop: TaurusCommandButton = getattr(self, f'button_stop_{dev_name}')
        button_stop.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        setattr(self, f'button_set_{dev_name}', QtWidgets.QPushButton('Set'))
        button_set: TaurusCommandButton = getattr(self, f'button_set_{dev_name}')
        # button_set.setModel(dev_name)
        # button_set.setParameters([0])
        button_set.clicked.connect(partial(self.set_clicked, dev_name))

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)
        lo_buttons.addWidget(button_stop)
        lo_buttons.addWidget(button_set)

        separator = Qt.QFrame()
        separator.setFrameShape(Qt.QFrame.VLine)
        separator.setSizePolicy(Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
        separator.setLineWidth(2)


        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_pos)
        lo_device.addWidget(group)
        lo_device.addLayout(lo_info)
        lo_device.addLayout(lo_buttons)

        lo_group.addLayout(lo_device)
        lo_group.addWidget(separator)

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


def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None,)
    p = Standa_panel(['elyse/motorized_devices/de1', 'elyse/motorized_devices/de2',
                      'elyse/motorized_devices/mme_x', 'elyse/motorized_devices/mme_y', None, None,
                      'elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y',
                      'elyse/motorized_devices/mm2_x', 'elyse/motorized_devices/mm2_y',
                      'manip/V0/mm3_x', 'manip/V0/mm3_y',
                      'manip/V0/mm4_x', 'manip/V0/mm4_y',
                      'manip/V0/opa_x', 'manip/V0/opa_y'], 'STANDA')
    # p = Standa_panel(['elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y'], 'STANDA', 2)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
