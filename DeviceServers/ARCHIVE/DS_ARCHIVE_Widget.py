from collections import deque

import numpy as np
import pyqtgraph as pg
from taurus import Device
from taurus.core import TaurusDevState
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox
from PyQt5 import QtWidgets

from DeviceServers.DS_Widget import DS_General_Widget, VisType


class Archive(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.grabbing = False
        self.positions = {'X': deque([], maxlen=120), 'Y': deque([], maxlen=120)}
        super().__init__(device_name, parent, vis_type)

    def register_DS_full(self, group_number=1):
        super(Archive, self).register_DS_full()
        dev_name = self.dev_name

        ds: Device = getattr(self, f'ds_{dev_name}')
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
        lo_calendar: Qt.QLayout = getattr(self, f'layout_calendar_{dev_name}')

        # State and status
        self.set_state_status(False)

        # Calendar
        self.calendar = QtWidgets.QCalendarWidget(parent=self)
        lo_calendar.addWidget(self.calendar)

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
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_calendar)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def register_full_layouts(self):
        super(Archive, self).register_full_layouts()
        setattr(self, f'layout_parameters_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_calendar_{self.dev_name}', Qt.QHBoxLayout())

    def register_min_layouts(self):
        self.register_full_layouts()

