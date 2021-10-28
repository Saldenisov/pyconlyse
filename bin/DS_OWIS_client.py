import sys
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusValueSpinBox, TaurusWheelEdit, TaurusValueCheckBox
from taurus.qt.qtgui.panel.taurusmodelchooser import TaurusModelSelectorItem
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
import tango
from typing import List
from _functools import partial


class OWIS_motor(Qt.QWidget):

    def __init__(self, device_name: str, axes=[], parent=None):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.layout_main = Qt.QVBoxLayout()
        setattr(self, f'lo_group_{1}', Qt.QHBoxLayout())
        self.register_DS(device_name, axes)

        self.setLayout(self.layout_main)
        self.axes = axes
        self.dev_name = device_name
        ds: Device = getattr(self, f'ds_{device_name}')
        ds.subscribe_event("states", tango.EventType.CHANGE_EVENT, self.states_listener)
        # ds.subscribe_event("states", tango.EventType.CHANGE_EVENT, self.positions_listener)

    def register_DS(self, dev_name, axes, group_number=1):
        setattr(self, f'ds_{dev_name}', Device(dev_name))
        ds: Device = getattr(self, f'ds_{dev_name}')

        delay_lines_parameters = ds.get_property('delay_lines_parameters')['delay_lines_parameters'][0]
        delay_lines_parameters = eval(delay_lines_parameters)
        setattr(self, f'delay_lines_parameters_{dev_name}', delay_lines_parameters)

        setattr(self, f'name_{dev_name}', ds.get_property('friendly_name')['friendly_name'][0])
        name = getattr(self, f'name_{dev_name}')

        setattr(self, f'layout_main_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_status_axes_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_pos_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_preset_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_buttons_{dev_name}', Qt.QHBoxLayout())
        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_status_axes: Qt.QLayout = getattr(self, f'layout_status_axes_{dev_name}')
        lo_pos: Qt.QLayout = getattr(self, f'layout_pos_{dev_name}')
        lo_preset: Qt.QLayout = getattr(self, f'layout_preset_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')

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
        widgets = [(TaurusValueCheckBox(f'{names[axis]}:id:{axis}'), TaurusLabel()) for axis in axes]
        setattr(self, f'checkbox_group_{dev_name}', Qt.QGroupBox('Axes states'))
        group: Qt.QGroupBox = getattr(self, f'checkbox_group_{dev_name}')
        for axis, widget in zip(axes, widgets):
            cb, lab = widget
            setattr(self, f'cb{axis}_{dev_name}', cb)
            setattr(self, f'lab{axis}_{dev_name}', lab)
            cb: TaurusValueCheckBox = getattr(self, f'cb{axis}_{dev_name}')
            lab: TaurusValueCheckBox = getattr(self, f'lab{axis}_{dev_name}')
            if states[axis] == tango.DevState.ON:
                state = True
            else:
                state = False
            cb.setChecked(state)
            cb.setText(f'{names[axis]}:id:{axis}')
            lab.setText(str(states[axis]))
            lo_status_axes.addWidget(lab)
            lo_status_axes.addWidget(cb)
            cb.clicked.connect(partial(self.cb_clicked, axis))
        group.setLayout(lo_status_axes)


        lo_device.addWidget(group)

        # Buttons for DS_server and commands
        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)

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

    def cb_clicked(self, axis):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        cb: TaurusValueCheckBox = getattr(self, f'cb{axis}_{self.dev_name}')
        new_state = cb.isChecked()
        if new_state:
            ds.turn_on_axis(int(axis))
        else:
            ds.turn_off_axis(int(axis))


    def states_listener(self, event):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        names = eval(ds.friendly_names)
        states = eval(ds.states)
        for axis in self.axes:
            cb: TaurusValueCheckBox = getattr(self, f'cb{axis}_{self.dev_name}')
            lab: TaurusValueCheckBox = getattr(self, f'lab{axis}_{self.dev_name}')
            if states[axis] == tango.DevState.ON:
                state = True
            else:
                state = False
            cb.setChecked(state)
            cb.setText(f'{names[axis]}:id:{axis}')
            lab.setText(str(states[axis]))

    def positions_listener(self, event):
        pass


layouts = {'V0': ('manip/general/DS_OWIS_PS90', [2, 3, 4]),
           'VD2': ('manip/general/DS_OWIS_PS90', [1]),
           'all': ('manip/general/DS_OWIS_PS90', [1, 2, 3, 4])}


def main():
    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )

            panel = QtWidgets.QWidget()
            panel.setWindowTitle('OWIS')
            panel.setWindowIcon(QIcon('icons//OWIS.svg'))

            layout_main = Qt.QVBoxLayout()
            setattr(panel, f'layout_main', layout_main)


            dev_name, axes = choice
            layout_main.addWidget(OWIS_motor(dev_name, axes))


            panel.setLayout(layout_main)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
