import sys
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit, TaurusValueCheckBox
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device, Attribute
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
import tango

from _functools import partial


class Netio_pdu(Qt.QWidget):

    def __init__(self, device_name: str, parent=None):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.layout_main = Qt.QVBoxLayout()
        self.dev_name = device_name
        setattr(self, f'lo_group_{1}', Qt.QHBoxLayout())
        self.layout_main.addLayout(getattr(self, f'lo_group_{1}'))

        setattr(self, f'ds_{device_name}', Device(device_name))
        self.register_DS(device_name)
        self.setLayout(self.layout_main)

        # state_attr = Attribute(f'{device_name}/states')
        # state_attr.addListener(self.state_listener)

        cb = tango.utils.EventCallback()
        ds: Device = getattr(self, f'ds_{device_name}')
        ds.subscribe_event("states", tango.EventType.CHANGE_EVENT, self.state_listener)


    def register_DS(self, dev_name, group_number=1):
        ds: Device = getattr(self, f'ds_{dev_name}')
        # Logging level
        try:
            pass
            #ds.set_logging_level(3)
        except Exception as e:
            print(e)
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')
        setattr(self, f'name_{dev_name}', ds.get_property('friendly_name')['friendly_name'][0])
        name = getattr(self, f'name_{dev_name}')

        setattr(self, f'layout_main_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_state_{dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_error_info_{dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_buttons_{dev_name}', Qt.QHBoxLayout())
        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_state: Qt.QLayout = getattr(self, f'layout_state_{dev_name}')
        lo_error_info: Qt.QLayout = getattr(self, f'layout_error_info_{dev_name}')
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

        # state positions
        number_outputs = int(ds.get_property('number_outputs')['number_outputs'][0])
        names = list(ds.names)
        ids = list(ds.ids)
        states = list(ds.states)
        widgets = [TaurusValueCheckBox(f'{name}:id:{id}') for _, t, id in zip(range(number_outputs), names, ids)]
        setattr(self, f'checkbox_group_{dev_name}', Qt.QGroupBox('Channels states'))
        group: Qt.QGroupBox = getattr(self, f'checkbox_group_{dev_name}')
        for cb, state, name, id in zip(widgets, states, names, ids):
            setattr(self, f'cb{id}_{dev_name}', cb)
            cb: TaurusValueCheckBox = getattr(self, f'cb{id}_{dev_name}')
            cb.setChecked(bool(state))
            cb.setText(f'{name}:id:{id}')
            lo_state.addWidget(cb)
            cb.stateChanged.connect(partial(self.cb_clicked, dev_name))
        group.setLayout(lo_state)

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

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)

        lo_device.addLayout(lo_status)
        lo_device.addWidget(group)
        lo_device.addLayout(lo_error_info)
        lo_device.addLayout(lo_buttons)

        lo_group.addLayout(lo_device)

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

    def cb_clicked(self, dev_name: str):
        ds: Device = getattr(self, f'ds_{dev_name}')
        states = []
        for id, name in zip(ds.ids, ds.names):
            cb: TaurusValueCheckBox = getattr(self, f'cb{id}_{dev_name}')
            states.append(int(cb.isChecked()))
            cb.setText(f'{name}:id:{id}')
        ds.set_channels_states(states)

    def state_listener(self, event):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        for id, name, state in zip(ds.ids, ds.names, ds.states):
            cb: TaurusValueCheckBox = getattr(self, f'cb{id}_{self.dev_name}')
            cb.setChecked(bool(state))
            cb.setText(f'{name}:id:{id}')


layouts = {'V0': ['manip/V0/PDU_VO', 'manip/SD1/PDU_SD1', 'manip/SD2/PDU_SD2'],
           'VD2': ['manip/VD2/PDU_VD2', 'manip/SD2/PDU_SD2'],
           'all': ['manip/V0/PDU_VO', 'manip/VD2/PDU_VD2', 'manip/SD1/PDU_SD1', 'manip/SD2/PDU_SD2',
                   'manip/ELYSE/PDU_ELYSE']
          }


from taurus.external.qt import Qt
def main():
    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )
            width = 1
            panel = QtWidgets.QWidget()
            panel.setWindowTitle('NETIO')
            panel.setWindowIcon(QIcon('icons//NETIO.ico'))

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
            for dev_name in choice:
                group_number = i // width
                if dev_name:
                    lo: Qt.QLayout = getattr(panel, f'lo_DS_{group_number}')
                    lo.addWidget(Netio_pdu(dev_name))
                i += 1

            panel.setLayout(layout_main)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
