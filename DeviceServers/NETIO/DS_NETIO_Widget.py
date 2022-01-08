from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusValueCheckBox
from PyQt5.QtWidgets import QCheckBox
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from _functools import partial
import tango


from DeviceServers.DS_Widget import DS_General_Widget, VisType


class Netio_pdu(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        super().__init__(device_name, parent, vis_type)

        ds: Device = getattr(self, f'ds_{self.dev_name}')

        self.ids = list(ds.ids)
        self.names = list(ds.names)
        self.states = list(ds.states)

        ds.subscribe_event("states", tango.EventType.CHANGE_EVENT, self.state_listener)
        ds.subscribe_event("names", tango.EventType.CHANGE_EVENT, self.state_listener)
        ds.subscribe_event("ids", tango.EventType.CHANGE_EVENT, self.state_listener)

    def register_DS_full(self, dev_name, group_number=1):
        super().register_DS_full(dev_name, group_number=1)

        ds: Device = getattr(self, f'ds_{self.dev_name}')
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
        widgets = [QCheckBox(f'{name}:id:{id}') for _, t, id in zip(range(number_outputs), names, ids)]
        setattr(self, f'checkbox_group_{dev_name}', Qt.QGroupBox('Channels states'))
        group: Qt.QGroupBox = getattr(self, f'checkbox_group_{dev_name}')
        for cb, state, name, id in zip(widgets, states, names, ids):
            setattr(self, f'cb{id}_{dev_name}', cb)
            cb: QCheckBox = getattr(self, f'cb{id}_{dev_name}')
            cb.setChecked(bool(state))
            cb.setText(f'{name}:id:{id}')
            lo_state.addWidget(cb)
            cb.clicked.connect(partial(self.cb_clicked, dev_name))
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

    def register_DS_min(self, dev_name, group_number=1):
        pass

    def cb_clicked(self, dev_name: str):
        ds: Device = getattr(self, f'ds_{dev_name}')
        states = []
        for id, name in zip(ds.ids, ds.names):
            cb: QCheckBox = getattr(self, f'cb{id}_{dev_name}')
            states.append(int(cb.isChecked()))
            #cb.setText(f'{name}:id:{id}')
        ds.set_channels_states(states)

    def state_listener(self, event):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        names_new, states_new = list(ds.names), list(ds.states)
        for new_name, new_state, id in zip(names_new, states_new, self.ids):
            cb: QCheckBox = getattr(self, f'cb{id}_{self.dev_name}')

            if self.names[id - 1] != new_name:
                cb.setText(f'{new_name}:id:{id}')

            if self.states[id - 1] != new_state:
                cb.setChecked(bool(new_state))

        self.names = names_new
        self.states = states_new