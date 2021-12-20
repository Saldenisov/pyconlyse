from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from PyQt5 import QtWidgets, QtCore
import tango

from PyQt5.QtGui import QMouseEvent

from typing import List
from _functools import partial

from DeviceServers.DS_Widget import DS_General_Widget
from gui.MyWidgets import MyQLabel


class Standa_motor(DS_General_Widget):

    def __init__(self, device_name: str, parent=None):
        super().__init__(device_name, parent)
        self.relative_shift = 1
        self.register_DS(device_name)
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        ds.subscribe_event("position", tango.EventType.CHANGE_EVENT, self.position_listener)

    def position_listener(self):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        p2: TaurusLabel = getattr(self, f'p2_{self.dev_name}')
        p2.setText(str(ds.position))

    def register_DS(self, dev_name, group_number=1):
        super(Standa_motor, self).register_DS(dev_name, group_number=1)

        ds: Device = getattr(self, f'ds_{self.dev_name}')


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
        widgets = [TaurusLabel(), TaurusLabel(), TaurusWheelEdit(), TaurusValueLineEdit(),
                   MyQLabel(f'Relative shift: {self.relative_shift}')]
        i = 1
        for p in widgets:
            name = f'p{i}_{dev_name}'
            setattr(self, f'{name}', p)
            i += 1
        p1 = getattr(self, f'p1_{dev_name}')
        p2 = getattr(self, f'p2_{dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{dev_name}')
        p4: TaurusValueLineEdit = getattr(self, f'p{4}_{dev_name}')
        p5: MyQLabel = getattr(self, f'p{5}_{dev_name}')

        p5.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        p5.customContextMenuRequested.connect(partial(self.context_menu))

        limit = abs(l_min) if abs(l_min) >= abs(l_max) else abs(l_max)
        n_digits = len(str(int(limit)))

        lo_pos.addWidget(p1)
        lo_pos.addWidget(p2)
        lo_pos.addWidget(p3)
        lo_pos.addWidget(p4)
        lo_pos.addWidget(p5)

        p1.model, p1.bgRole = f'{dev_name}/position#label', ''
        p2.model = f'{dev_name}/position'
        p2.setFixedWidth(60)
        p3.model = f'{dev_name}/position'

        p3.setMinValue(l_min)
        p3.setMaxValue(l_max)
        p3.setDigitCount(n_digits, 3)

        p4.setText('0')
        p4.setFixedWidth(50)

        self.pos_widget = p2
        self.wheel = p3
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
        # lo_info.addWidget(inf4)

        inf1.model = f'{dev_name}/temperature'
        inf2.model = f'{dev_name}/power_current'
        inf3.model = f'{dev_name}/power_voltage'
        # inf4.model = f'{dev_name}/power_status'

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

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        print(f'{self.dev_name} is selected.')
        self.setStyleSheet("background-color: lightgreen; border: 1px solid black;")
        self.panel_parent.active_widget = self.dev_name
        self.panel_parent.update_background_widgets()

    def context_menu(self, point):
        menu = QtWidgets.QMenu()
        tens = menu.addAction('0.1')
        half = menu.addAction('0.5')
        one = menu.addAction('1')
        five = menu.addAction('5')
        ten = menu.addAction('10')
        fifty = menu.addAction('50')
        hundred = menu.addAction('100')

        label_shift: MyQLabel = getattr(self, f'p{5}_{self.dev_name}')

        action = menu.exec_(label_shift.mapToGlobal(point))

        if action:
            move = 1
            if action == tens:
                move = 0.1
            elif action == half:
                move = 0.5
            elif action == one:
                move = 1
            elif action == five:
                move = 5
            elif action == ten:
                move = 10
            elif action == fifty:
                move = 50
            elif action == hundred:
                move = 100

            self.relative_shift = move

            label_shift.setText(f"Relative shift: {move}")