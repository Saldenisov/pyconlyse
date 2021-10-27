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


class OWIS_motor(Qt.QWidget):

    def __init__(self, device_name: str, axis: str, parent=None):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.layout_main = Qt.QVBoxLayout()
        setattr(self, f'lo_group_{1}', Qt.QHBoxLayout())
        self.layout_main.addLayout(getattr(self, f'lo_group_{1}'))
        self.register_DS(device_name, axis)

        self.setLayout(self.layout_main)

    def register_DS(self, dev_name, axis, group_number=1):
        try:
            ds: Device = getattr(self, f'ds_{dev_name}')
        except AttributeError:
            setattr(self, f'ds_{dev_name}', Device(dev_name))
            ds: Device = getattr(self, f'ds_{dev_name}')

        try:
            delay_lines_parameters = getattr(self, f'delay_lines_parameters_{dev_name}')
        except AttributeError:
            delay_lines_parameters = ds.get_property('delay_lines_parameters')['delay_lines_parameters'][0]
            delay_lines_parameters = eval(delay_lines_parameters)
            setattr(self, f'ds_{dev_name}', Device(dev_name))
        finally:
            dl_param = delay_lines_parameters[axis]

        # Logging level
        try:
            pass
            #ds.set_logging_level(3)
        except Exception as e:
            print(e)

        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')
        setattr(self, f'l_min_{dev_name}', float(dl_param['limit_min']))
        setattr(self, f'l_max_{dev_name}', float(dl_param['limit_max']))
        setattr(self, f'name_{dev_name}', dl_param['friendly_name'])
        setattr(self, f'preset_pos_{dev_name}', dl_param['preset_positions'])
        l_min, l_max = getattr(self, f'l_min_{dev_name}'), getattr(self, f'l_max_{dev_name}')
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
        limit = abs(l_min) if abs(l_min) >= abs(l_max) else abs(l_max)
        n_digits = len(str(int(limit)))
        p3._setDigits(n_digits)

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
            lo_preset.addWidget(rb)
            rb.toggled.connect(partial(self.rb_clicked, rb.text(), dev_name))
        group.setLayout(lo_preset)

        # # Info
        # widgets = [TaurusLabel(), TaurusLabel(), TaurusLabel(), TaurusLabel()]
        # i = 1
        # for inf in widgets:
        #     name = f'inf{i}_{dev_name}'
        #     setattr(self, f'{name}', inf)
        #     i += 1
        # inf1 = getattr(self, f'inf1_{dev_name}')
        # inf2 = getattr(self, f'inf2_{dev_name}')
        # inf3 = getattr(self, f'inf3_{dev_name}')
        # inf4 = getattr(self, f'inf4_{dev_name}')
        #
        # lo_info.addWidget(inf1)
        # lo_info.addWidget(inf2)
        # lo_info.addWidget(inf3)
        # # lo_info.addWidget(inf4)
        #
        # inf1.model = f'{dev_name}/temperature'
        # inf2.model = f'{dev_name}/power_current'
        # inf3.model = f'{dev_name}/power_voltage'
        # # inf4.model = f'{dev_name}/power_status'

        # # ERRORS and INFO
        # error = TaurusLabel()
        # comments = TaurusLabel()
        # error.model = f'{dev_name}/last_error'
        # comments.model = f'{dev_name}/last_comments'
        # lo_error_info.addWidget(error)
        # lo_error_info.addWidget(comments)

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

        setattr(self, f'button_init_{dev_name}', QtWidgets.QPushButton('init_device'))
        button_init: TaurusCommandButton = getattr(self, f'button_init_{dev_name}')

        # button_set.setModel(dev_name)
        # button_set.setParameters([0])
        button_set.clicked.connect(partial(self.set_clicked, dev_name))

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)
        lo_buttons.addWidget(button_stop)
        lo_buttons.addWidget(button_set)
        lo_buttons.addWidget(button_init)

        separator = Qt.QFrame()
        separator.setFrameShape(Qt.QFrame.VLine)
        separator.setSizePolicy(Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
        separator.setLineWidth(2)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_pos)
        lo_device.addWidget(group)
        lo_device.addLayout(lo_info)
        lo_device.addLayout(lo_error_info)
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

    def rb_clicked(self, value: str, dev_name: str):
        pos = float(value)
        ds: Device = getattr(self, f'ds_{dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{dev_name}')
        p3.setValue(pos)
        ds.move_axis_abs(pos)


layouts = {'V0': [('manip/general/DS_OWIS_PS90', '2'),
                  ('manip/general/DS_OWIS_PS90', '3'),
                  ('manip/general/DS_OWIS_PS90', '4'), None],
           'VD2': [('manip/general/DS_OWIS_PS90', '1'), None],
           'all': [('manip/general/DS_OWIS_PS90', '1'),
                   ('manip/general/DS_OWIS_PS90', '2'),
                   ('manip/general/DS_OWIS_PS90', '3'),
                   ('manip/general/DS_OWIS_PS90', '4')]}


def main():
    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )
            if len(sys.argv) >= 3:
                try:
                    width = int(sys.argv[2])
                except ValueError:
                    width = 2
            elif len(sys.argv) == 2:
                width = 2
            panel = QtWidgets.QWidget()
            panel.setWindowTitle('OWIS')
            panel.setWindowIcon(QIcon('icons//OWIS.png'))

            layout_main = Qt.QVBoxLayout()
            setattr(panel, f'layout_main', layout_main)

            number_ds = len(choice)
            number_lo = 1 if number_ds // width == 0 else number_ds // width

            for lo_i in range(number_lo):
                setattr(panel, f'lo_DS_{lo_i}', Qt.QHBoxLayout())
                lo: Qt.QLayout = getattr(panel, f'lo_DS_{lo_i}')
                panel.layout_main.addLayout(lo)
                separator = Qt.QFrame()
                separator.setFrameShape(Qt.QFrame.HLine)
                separator.setSizePolicy(Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
                separator.setLineWidth(3)
                panel.layout_main.addWidget(separator)

            i = 0
            for dev_name, axis in choice:
                group_number = i // width
                if dev_name:
                    lo: Qt.QLayout = getattr(panel, f'lo_DS_{group_number}')
                    lo.addWidget(OWIS_motor(dev_name, axis))
                i += 1

            panel.setLayout(layout_main)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
