from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from PyQt5.QtWidgets import QCheckBox, QVBoxLayout, QHBoxLayout
from PyQt5 import QtWidgets
from PyQt5.QtGui import QMouseEvent
import tango

from typing import List, Dict
from _functools import partial

from DeviceServers.DS_Widget import DS_General_Widget


class OWIS_motor(DS_General_Widget):

    def __init__(self, device_name: str, axes, parent=None):
        super().__init__(device_name, parent)
        self.register_DS(device_name, axes)

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
            wheel.returnPressed.connect(partial(self.wheel_value_change, axis))
            button_set.clicked.connect(partial(self.set_clicked, axis))
            button_stop.clicked.connect(partial(self.stop_clicked, axis))

            lab_name = TaurusLabel(f'Axis: {names[axis]}')

            lo_v_pos.addWidget(lab_name)
            lo_h_pos_lab.addWidget(pos_lab_name)
            lo_h_pos_lab.addWidget(wheel)
            lo_h_move_set.addWidget(lineedit)
            lo_h_move_set.addWidget(button_set)
            lo_v_pos.addLayout(lo_h_pos_lab)
            lo_v_pos.addWidget(button_stop)
            lo_v_pos.addLayout(lo_h_move_set)

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

    def rb_clicked(self, value: str, dev_name: str):
        pos = float(value)
        ds: Device = getattr(self, f'ds_{dev_name}')
        p3: TaurusWheelEdit = getattr(self, f'p3_{dev_name}')
        p3.setValue(pos)
        ds.move_axis_abs(pos)

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
                wheel: TaurusWheelEdit = getattr(self, f'pos_wheel{axis_id}_{self.dev_name}')
                label.setText(str(self.positions[axis_id]))

    def wheel_value_change(self, axis):
        wheel: TaurusWheelEdit = getattr(self, f'pos_wheel{axis}_{self.dev_name}')
        pos = float(wheel.getValue())
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        ds.move_axis([axis, pos])
