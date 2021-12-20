from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from PyQt5.QtWidgets import QCheckBox, QVBoxLayout, QHBoxLayout
from PyQt5 import QtWidgets, QtGui, QtCore
import PyQt5
from PyQt5.QtGui import QMouseEvent
import tango

from typing import List, Dict
from _functools import partial

from DeviceServers.DS_Widget import DS_General_Widget
from gui.MyWidgets import MyQLabel


class OWIS_motor(DS_General_Widget):

    def __init__(self, device_name: str, axes, parent=None):
        super().__init__(device_name, parent)
        self.register_DS(device_name, axes)
        self.axis_selected = None
        self.axes = axes

        ds: Device = getattr(self, f'ds_{self.dev_name}')

        self.states: Dict[int, tango.DevState] = eval(ds.states)
        self.positions: Dict[int, tango.DevState] = eval(ds.positions)

        ds.subscribe_event("states", tango.EventType.CHANGE_EVENT, self.states_listener)
        ds.subscribe_event("positions", tango.EventType.CHANGE_EVENT, self.positions_listener)

    def register_DS(self, dev_name, axes, group_number=1):
        ds: Device = getattr(self, f'ds_{dev_name}')

        delay_lines_parameters = ds.get_property('delay_lines_parameters')['delay_lines_parameters'][0]
        delay_lines_parameters = eval(delay_lines_parameters)
        self.delay_lines_parameters = delay_lines_parameters

        name = ds.get_property('friendly_name')['friendly_name'][0]

        lo_device = Qt.QVBoxLayout()
        lo_status = Qt.QHBoxLayout()
        lo_status_axes = Qt.QHBoxLayout()
        lo_pos = Qt.QHBoxLayout()
        lo_preset = Qt.QHBoxLayout()
        lo_buttons = Qt.QHBoxLayout()

        # State and status DS
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

        lo_device.addLayout(lo_status)

        # States of axes
        names = eval(ds.friendly_names)
        states = eval(ds.states)
        widgets = [(QCheckBox(f'{names[axis]}:id:{axis}'), TaurusLabel()) for axis in axes]
        self.checkbox_group_axes = Qt.QGroupBox('Axes states')

        for axis, wheel in zip(axes, widgets):
            cb, lab = wheel
            setattr(self, f'cb{axis}_{dev_name}', cb)
            setattr(self, f'lab{axis}_{dev_name}', lab)
            cb: QCheckBox = getattr(self, f'cb{axis}_{dev_name}')
            lab: TaurusLabel = getattr(self, f'lab{axis}_{dev_name}')

            state = True if states[axis] == tango.DevState.ON else False

            cb.setChecked(state)
            cb.setText(f'{names[axis]}:id:{axis}')

            lab.setText(str(states[axis]))

            lo_status_axes.addWidget(lab)
            lo_status_axes.addWidget(cb)

            cb.clicked.connect(partial(self.cb_clicked, axis))

        self.checkbox_group_axes.setLayout(lo_status_axes)

        lo_device.addWidget(self.checkbox_group_axes)

        # Positions of axes
        positions = eval(ds.positions)

        widgets = [(TaurusLabel(), TaurusWheelEdit(), TaurusValueLineEdit(),
                    TaurusCommandButton(text='Set'), TaurusCommandButton(text='STOP')) for axis in axes]
        self.checkbox_group_positions = Qt.QGroupBox('Axes positions')
        for axis, widget in zip(axes, widgets):
            lo_h_pos = QHBoxLayout()
            lo_v_pos = QVBoxLayout()
            lo_h_pos_lab = QHBoxLayout()
            lo_h_move_set = QHBoxLayout()
            pos_lab_name, wheel, lineedit, button_set, button_stop = widget
            setattr(self, f'pos_lab_name{axis}_{dev_name}', pos_lab_name)
            setattr(self, f'pos_wheel{axis}_{dev_name}', wheel)
            setattr(self, f'pos_lineedit{axis}_{dev_name}', lineedit)
            setattr(self, f'pos_set{axis}_{dev_name}', button_set)
            setattr(self, f'pos_button_stop{axis}_{dev_name}', button_stop)
            lineedit.setMaximumWidth(80)
            pos_lab_name.setStyleSheet("background-color: lightgreen; border: 1px solid black;")
            pos_lab_name.setText(str(positions[axis]))
            pos_lab_name.setFixedWidth(50)
            wheel.setValue(positions[axis])
            l_min = delay_lines_parameters[axis]['limit_min']
            l_max = delay_lines_parameters[axis]['limit_max']
            wheel.setMinValue(l_min)
            wheel.setMaxValue(l_max)
            limit = abs(l_min) if abs(l_min) >= abs(l_max) else abs(l_max)
            n_digits = len(str(int(limit)))
            wheel.setDigitCount(n_digits, 3)
            #wheel.returnPressed.connect(partial(self.wheel_value_change, axis))
            wheel.model = f'{dev_name}/pos{axis}'
            button_set.clicked.connect(partial(self.set_clicked, axis))
            button_stop.clicked.connect(partial(self.stop_clicked, axis))

            lab_name = MyQLabel(f'Axis: {names[axis]}')
            lab_name.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            lab_name.customContextMenuRequested.connect(partial(self.context_menu_label, axis))
            setattr(self, f'label_name_{axis}_{dev_name}', lab_name)
            lab_name.clicked.connect(partial(self.label_name_clicked, axis))


            lab_name_relative_shift = MyQLabel(f'Relative shift: {self.delay_lines_parameters[axis]["relative_shift"]}')
            setattr(self, f'lab_name_relative_shift_{axis}_{dev_name}', lab_name_relative_shift)

            setattr(self, f'radio_button_group_{axis}_{dev_name}', Qt.QGroupBox('Preset Positions'))
            group_rb: Qt.QGroupBox = getattr(self, f'radio_button_group_{axis}_{dev_name}')
            lo_rb_preset = QVBoxLayout()
            for rb in [Qt.QRadioButton(text=str(pos)) for pos in self.delay_lines_parameters[axis]['preset_positions']]:
                setattr(self, f'rb{i}_{axis}_{dev_name}', rb)
                lo_rb_preset.addWidget(rb)
                rb.toggled.connect(partial(self.rb_clicked, float(rb.text()), axis))
            spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            lo_rb_preset.addItem(spacer)
            group_rb.setLayout(lo_rb_preset)

            lo_v_pos.addWidget(lab_name)
            lo_h_pos_lab.addWidget(pos_lab_name)
            lo_h_pos_lab.addWidget(wheel)
            lo_h_move_set.addWidget(lineedit)
            lo_h_move_set.addWidget(button_set)
            lo_v_pos.addLayout(lo_h_pos_lab)
            lo_v_pos.addWidget(lab_name_relative_shift)
            lo_v_pos.addWidget(button_stop)
            lo_v_pos.addLayout(lo_h_move_set)
            lo_v_pos.addWidget(group_rb)

            separator = QtWidgets.QFrame()
            separator.setFrameShape(QtWidgets.QFrame.VLine)
            separator.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            separator.setLineWidth(2)

            lo_h_pos.addLayout(lo_v_pos)
            lo_h_pos.addWidget(separator)
            lo_pos.addLayout(lo_h_pos)

        self.checkbox_group_positions.setLayout(lo_pos)
        lo_device.addWidget(self.checkbox_group_positions)

        # Buttons for DS_server and commands
        self.button_on = TaurusCommandButton(command='turn_on')
        self.button_on.setModel(dev_name)

        self.button_off = TaurusCommandButton(command='turn_off')
        self.button_off.setModel(dev_name)

        lo_buttons.addWidget(self.button_on)
        lo_buttons.addWidget(self.button_off)

        lo_device.addLayout(lo_buttons)

        self.layout_main.addLayout(lo_device)

    def context_menu_label(self, axis, point):
        menu = QtWidgets.QMenu()
        tens = menu.addAction('0.1')
        half = menu.addAction('0.5')
        one = menu.addAction('1')
        five = menu.addAction('5')
        ten = menu.addAction('10')
        fifty = menu.addAction('50')
        hundred = menu.addAction('100')

        label = getattr(self, f'label_name_{axis}_{self.dev_name}')

        action = menu.exec_(label.mapToGlobal(point))

        if action and self.axis_selected:
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
            self.delay_lines_parameters[self.axis_selected]['relative_shift'] = move
            label_shift: MyQLabel = getattr(self, f'lab_name_relative_shift_{self.axis_selected}_{self.dev_name}')
            label_shift.setText(f"Relative shift: {self.delay_lines_parameters[self.axis_selected]['relative_shift']}")

    def label_name_clicked(self, axis):
        self.axis_selected = axis
        for ax in self.axes:
            lab_name: TaurusLabel = getattr(self, f'label_name_{ax}_{self.dev_name}')
            if ax == axis:
                lab_name.setStyleSheet("background-color: lightgreen; border: 1px solid black;")
            else:
                lab_name.setStyleSheet("background-color: white;")

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        from PyQt5.QtCore import Qt
        if event.key() in [Qt.Key_Left, Qt.Key_Down, Qt.Key_Right, Qt.Key_Up] and \
                self.axis_selected:
            positions = eval(ds.positions)
            pos_axis = positions[self.axis_selected]
            try:
                move = self.delay_lines_parameters[self.axis_selected]['relative_shift']
            except KeyError:
                move = 1.0
                self.delay_lines_parameters[self.axis_selected]['relative_shift'] = move

            if event.key() in [Qt.Key_Left, Qt.Key_Down]:
                pos = pos_axis - move
            elif event.key() in [Qt.Key_Right, Qt.Key_Up]:
                pos = pos_axis + move

            ds.move_axis([int(self.axis_selected), pos])

    def rb_clicked(self, pos: float, axis: int):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        ds.move_axis([axis, pos])

    def cb_clicked(self, axis):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        cb: QCheckBox = getattr(self, f'cb{axis}_{self.dev_name}')
        new_state = cb.isChecked()
        if new_state:
            ds.turn_on_axis(int(axis))
        else:
            ds.turn_off_axis(int(axis))

    def set_clicked(self, axis):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        lineedit: TaurusValueLineEdit = getattr(self, f'pos_lineedit{axis}_{self.dev_name}')
        try:
            pos = float(lineedit.text())
            ds.define_position_axis([int(axis), pos])
        except ValueError:
            pass

    def stop_clicked(self, axis):
        print('STOP CLICKED')
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        ds.stop_axis(int(axis))

    def states_listener(self, event):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        states_new = eval(ds.states)
        for axis_id in self.delay_lines_parameters.keys():
            if self.states[axis_id] != states_new[axis_id]:
                self.states[axis_id] = states_new[axis_id]
                cb: QCheckBox = getattr(self, f'cb{axis_id}_{self.dev_name}')
                lab: TaurusLabel = getattr(self, f'lab{axis_id}_{self.dev_name}')
                state = True if self.states[axis_id] == tango.DevState.ON else False
                cb.setChecked(state)
                lab.setText(str(self.states[axis_id]))

    def positions_listener(self, event):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        positions = eval(ds.positions)
        for axis_id in self.delay_lines_parameters.keys():
            if self.positions[axis_id] != positions[axis_id]:
                self.positions[axis_id] = positions[axis_id]
                label: QCheckBox = getattr(self, f'pos_lab_name{axis_id}_{self.dev_name}')
                label.setText(str(self.positions[axis_id]))

    def wheel_value_change(self, axis):
        wheel: TaurusWheelEdit = getattr(self, f'pos_wheel{axis}_{self.dev_name}')
        pos = float(wheel.getValue())
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        ds.move_axis([axis, pos])
