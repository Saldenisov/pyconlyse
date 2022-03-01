from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from PyQt5 import QtWidgets, QtCore
import tango
from PyQt5.QtGui import QMouseEvent, QKeyEvent

from typing import List
from _functools import partial

from DeviceServers.DS_Widget import DS_General_Widget, VisType
from gui.MyWidgets import MyQLabel


class Standa_motor(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.relative_shift = 1
        super().__init__(device_name, parent, vis_type)
        self.ds.subscribe_event("position", tango.EventType.CHANGE_EVENT, self.position_listener)

    def register_DS_full(self, group_number=1):
        super(Standa_motor, self).register_DS_full()
        dev_name = self.dev_name

        ds: Device = getattr(self, f'ds_{dev_name}')

        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')
        unit = ds.get_property('unit')['unit'][0]
        setattr(self, f'l_min_{dev_name}', float(ds.get_property('limit_min')['limit_min'][0]))
        setattr(self, f'l_max_{dev_name}', float(ds.get_property('limit_max')['limit_max'][0]))
        setattr(self, f'name_{dev_name}', ds.get_property('friendly_name')['friendly_name'][0])
        setattr(self, f'preset_pos_{dev_name}',
                list([float(pos) for pos in ds.get_property('preset_pos')['preset_pos']]))
        l_min, l_max = getattr(self, f'l_min_{dev_name}'), getattr(self, f'l_max_{dev_name}')
        name = getattr(self, f'name_{dev_name}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_pos: Qt.QLayout = getattr(self, f'layout_pos_{dev_name}')
        lo_info: Qt.QLayout = getattr(self, f'layout_info_{dev_name}')
        lo_error_info: Qt.QLayout = getattr(self, f'layout_error_info_{dev_name}')
        lo_preset: Qt.QLayout = getattr(self, f'layout_preset_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')

        # State and status
        self.set_state_status(False)

        # Position controls
        widgets = [TaurusLabel(), TaurusLabel(), TaurusWheelEdit(), TaurusValueLineEdit(),
                   MyQLabel(f'Relative shift: {self.relative_shift}')]
        i = 1
        for p in widgets:
            name = f'p{i}_{dev_name}'
            setattr(self, f'{name}', p)
            i += 1
        p1: TaurusLabel = getattr(self, f'p1_{dev_name}')
        p2: TaurusLabel = getattr(self, f'p2_{dev_name}')
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

        p1.setText(unit)
        p2.model = f'{dev_name}/position'
        p2.setFixedWidth(50)
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

    def register_DS_min(self, group_number=1):
        super(Standa_motor, self).register_DS_min(group_number=1)
        dev_name = self.dev_name

        ds: Device = getattr(self, f'ds_{self.dev_name}')

        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')
        unit = ds.get_property('unit')['unit'][0]
        setattr(self, f'l_min_{dev_name}', float(ds.get_property('limit_min')['limit_min'][0]))
        setattr(self, f'l_max_{dev_name}', float(ds.get_property('limit_max')['limit_max'][0]))
        setattr(self, f'name_{dev_name}', ds.get_property('friendly_name')['friendly_name'][0])
        setattr(self, f'preset_pos_{dev_name}',
                list([float(pos) for pos in ds.get_property('preset_pos')['preset_pos']]))
        l_min, l_max = getattr(self, f'l_min_{dev_name}'), getattr(self, f'l_max_{dev_name}')
        name = getattr(self, f'name_{dev_name}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_min: Qt.QLayout = getattr(self, f'layout_min_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')

        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')

        # State and status
        self.set_state_status()
        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)
        lo_status.addWidget(button_on)

        # Position controls
        widgets = [TaurusLabel(), TaurusLabel(), TaurusWheelEdit(), MyQLabel(f'Relative shift: {self.relative_shift}')]
        i = 1
        for p in widgets:
            name = f'p{i}_{dev_name}'
            setattr(self, f'{name}', p)
            i += 1
        p1: TaurusLabel = getattr(self, f'p1_{dev_name}')
        p2: TaurusLabel = getattr(self, f'p2_{dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{dev_name}')
        p4: MyQLabel = getattr(self, f'p{4}_{dev_name}')

        p4.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        p4.customContextMenuRequested.connect(partial(self.context_menu))

        limit = abs(l_min) if abs(l_min) >= abs(l_max) else abs(l_max)
        n_digits = len(str(int(limit)))

        lo_min.addWidget(p1)
        lo_min.addWidget(p2)
        lo_min.addWidget(p3)

        p1.setText(unit)
        p2.model = f'{dev_name}/position'
        p2.setFixedWidth(50)
        p3.model = f'{dev_name}/position'

        p3.setMinValue(l_min)
        p3.setMaxValue(l_max)
        p3.setDigitCount(n_digits, 3)

        self.pos_widget = p2
        self.wheel = p3

        # preset positions
        preset_positions: List[float] = getattr(self, f'preset_pos_{dev_name}')
        preset_positions_cb = QtWidgets.QComboBox()
        setattr(self, f'combobox_prepos_{dev_name}', preset_positions_cb)
        for pr_pos in preset_positions:
            preset_positions_cb.addItem(str(pr_pos))

        preset_positions_cb.currentIndexChanged.connect(self.combobox_selected)

        lo_min.addWidget(preset_positions_cb)
        # Buttons and commands
        setattr(self, f'button_left_{dev_name}', QtWidgets.QPushButton('<<'))
        button_left: TaurusCommandButton = getattr(self, f'button_left_{dev_name}')

        setattr(self, f'button_right_{dev_name}', QtWidgets.QPushButton('>>'))
        button_right: TaurusCommandButton = getattr(self, f'button_right_{dev_name}')

        button_left.clicked.connect(partial(self.move_button_clicked, -1))
        button_right.clicked.connect(partial(self.move_button_clicked, 1))

        setattr(self, f'p{5}_{dev_name}', MyQLabel(f'Relative shift: {self.relative_shift}'))
        p5: MyQLabel = getattr(self, f'p{5}_{dev_name}')

        p5.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        p5.customContextMenuRequested.connect(partial(self.context_menu))

        lo_buttons.addWidget(button_left)
        lo_buttons.addWidget(p5)
        lo_buttons.addWidget(button_right)

        separator = Qt.QFrame()
        separator.setFrameShape(Qt.QFrame.VLine)
        separator.setSizePolicy(Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
        separator.setLineWidth(2)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_min)
        lo_device.addLayout(lo_buttons)
        lo_group.addLayout(lo_device)
        lo_group.addWidget(separator)

    def position_listener(self, event):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        p2: TaurusLabel = getattr(self, f'p2_{self.dev_name}')
        p2.setText(str(ds.position))

    def register_full_layouts(self):
        super(Standa_motor, self).register_full_layouts()
        setattr(self, f'layout_pos_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_preset_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_info_{self.dev_name}', Qt.QHBoxLayout())

    def register_min_layouts(self):
        super(Standa_motor, self).register_min_layouts()
        setattr(self, f'layout_main_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_min_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_buttons_{self.dev_name}', Qt.QHBoxLayout())

    def combobox_selected(self):
        cb: QtWidgets.QComboBox = getattr(self, f'combobox_prepos_{self.dev_name}')
        pos = float(cb.currentText())
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{self.dev_name}')
        p3.setValue(pos)
        ds.move_axis_abs(pos)

    def move_button_clicked(self, direction: int):
        relative_move = self.relative_shift * direction
        pos = self.ds.position + relative_move
        self.ds.move_axis_abs(pos)

    def set_clicked(self, dev_name):
        p: TaurusValueLineEdit = getattr(self, f'p4_{dev_name}')
        try:
            val = p.text()
            val = float(val)
        except (ValueError, TypeError):
            val = 0
            p.setText('0')
        self.ds.define_position(val)

    def rb_clicked(self, value: str, dev_name: str):
        pos = float(value)
        ds: Device = getattr(self, f'ds_{dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{dev_name}')
        p3.setValue(pos)
        ds.move_axis_abs(pos)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if self.parent:
            print(f'{self.dev_name} is selected.')
            self.setStyleSheet("background-color: lightgreen; border: 1px solid black;")
            self.parent.active_widget = self.dev_name
            self.parent.update_active_widget()

    def context_menu(self, point):
        menu = QtWidgets.QMenu()
        tens = menu.addAction('0.1')
        half = menu.addAction('0.5')
        one = menu.addAction('1')
        two = menu.addAction('2')
        five = menu.addAction('5')
        ten = menu.addAction('10')
        twenty = menu.addAction('20')
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
            elif action == two:
                move = 2
            elif action == one:
                move = 1
            elif action == five:
                move = 5
            elif action == ten:
                move = 10
            elif action == twenty:
                move = 20
            elif action == fifty:
                move = 50
            elif action == hundred:
                move = 100

            self.relative_shift = move

            label_shift.setText(f"Relative shift: {move}")

    def set_the_control_value(self, value):
        try:
            p3: TaurusWheelEdit = getattr(self, f'p3_{self.dev_name}')
            p3.setValue(float(value))
            self.execute_action(float(value), self.ds, 'move_axis_abs', True)
        except Exception as e:
            print(e)

    def keyPressEvent(self, event: QKeyEvent):
        from PyQt5.QtCore import Qt
        if self.widget_active:
            ds_widget = self
            pos = self.ds.position
            if event.key() in [Qt.Key_Left, Qt.Key_Down, Qt.Key_Right, Qt.Key_Up]:
                move_step = self.relative_shift
                if event.key() in [Qt.Key_Left, Qt.Key_Down]:
                    pos = pos - move_step
                elif event.key() in [Qt.Key_Right, Qt.Key_Up]:
                    pos = pos + move_step
                self.ds.move_axis_abs(pos)
