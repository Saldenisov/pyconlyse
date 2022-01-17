import pyqtgraph as pg
import numpy as np
from taurus import Device
from taurus.core import TaurusDevState
from tango import AttrWriteType, DispLevel, DevState, Database
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox
import taurus_pyqtgraph as tpg
from DeviceServers.DS_Widget import DS_General_Widget, VisType
from collections import OrderedDict
from typing import Dict
from PyQt5 import QtWidgets
from _functools import partial


from DeviceServers import *


class LaserPointing(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.widgets = {}
        self.device_servers = {}
        self.db = Database()
        super().__init__(device_name, parent, vis_type)

    def register_DS_full(self, group_number=1):
        super(LaserPointing, self).register_DS_full()
        dev_name = self.dev_name
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_states: Qt.QLayout = getattr(self, f'layout_states_{dev_name}')
        lo_controls: Qt.QLayout = getattr(self, f'layout_controls_{dev_name}')
        lo_image: Qt.QLayout = getattr(self, f'layout_image_{dev_name}')
        lo_total: Qt.QLayout = getattr(self, f'layout_total_{dev_name}')

        if ds.state == TaurusDevState.Ready:
            def register_ds(device_role, device_name):
                if isinstance(device_name, tuple):
                    extra = device_name[1]
                    device_name = device_name[0]
                ds = Device(device_name)
                state = ds.state
                if state == TaurusDevState.Ready:
                    ds_class_name = self.db.get_device_info(device_name).class_name
                    ds_class_widget = class_match[ds_class_name]
                    if issubclass(ds_class_widget, OWIS_motor):
                        ds_widget = ds_class_widget(device_name, extra, self, VisType.MIN)
                    else:
                        ds_widget = ds_class_widget(device_name, self, VisType.MIN)

                    self.widgets[device_role] = ds_widget
                    self.device_servers[device_role] = ds

            self.groups: OrderedDict = eval(ds.get_groups)
            self.ds_dict: Dict = eval(ds.get_ds_dict)
            self.rules: Dict = eval(ds.get_rules)

            # States
            group = self.set_states()
            lo_states.addWidget(group)
            # self.groups: OrderedDict = OrderedDict({'Translation stages': ('TranslationStage1')})
            # self.ds_dict: Dict = {'TranslationStage1': ('manip/general/DS_OWIS_PS90', [2])}

            try:
                for device_role, device_name in self.ds_dict.items():
                    register_ds(device_role, device_name)

                for group_name, group_devices in self.groups.items():
                    group_box = Qt.QGroupBox(group_name)
                    lo_group_loc = Qt.QHBoxLayout()
                    if isinstance(group_devices, str):
                        lo_group_loc.addWidget(self.widgets[group_devices])
                    if isinstance(group_devices, tuple):
                        for device_role in group_devices:
                            lo_group_loc.addWidget(self.widgets[device_role])

                    hspacer = QtWidgets.QSpacerItem(0, 40, QtWidgets.QSizePolicy.Expanding,
                                                    QtWidgets.QSizePolicy.Minimum)
                    lo_group_loc.addSpacerItem(hspacer)

                    group_box.setLayout(lo_group_loc)
                    lo_controls.addWidget(group_box)
            except Exception as e:
                print(e)
                raise e
            lo_image.addWidget(self.widgets['Camera'])
            vspacer = QtWidgets.QSpacerItem(20, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            lo_image.addSpacerItem(vspacer)

            control_group = QtWidgets.QGroupBox('Controls')
            control_group.setLayout(lo_controls)

            scroll = QtWidgets.QScrollArea()
            scroll.setWidget(control_group)
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(800)
            scroll.setFixedWidth(700)

            image_group = QtWidgets.QGroupBox('Image')
            image_group.setLayout(lo_image)

            lo_total.addWidget(image_group)
            lo_total.addWidget(scroll)
        else:
            print(f'{self.dev_name} is not ready. Run the Device Server.')

        # State and status
        self.set_state_status(False)



        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_total)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_states)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def register_full_layouts(self):
        super(LaserPointing, self).register_full_layouts()
        setattr(self, f'layout_controls_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_total_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_states_{self.dev_name}', Qt.QHBoxLayout())

    def register_min_layouts(self):
        super(LaserPointing, self).register_min_layouts()
        setattr(self, f'layout_controls_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_total_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_states_{self.dev_name}', Qt.QHBoxLayout())

    def set_states(self):
        dev_name = self.dev_name
        ds: Device = getattr(self, f'ds_{dev_name}')

        lo_states = Qt.QHBoxLayout()
        self.rules: OrderedDict = eval(ds.get_rules)
        group = QtWidgets.QGroupBox('States')
        for state, param in self.rules.items():
            rb = Qt.QRadioButton(text=str(state))
            lo_states.addWidget(rb)
            rb.toggled.connect(partial(self.rb_clicked, param))
        group.setLayout(lo_states)
        return group

    def rb_clicked(self, parameters: OrderedDict):
        for ds_role, state in parameters.items():
            ds_widget: DS_General_Widget = self.widgets[ds_role]
            ds_widget.set_the_control_value(state)

    def set_the_control_value(self, value):
        pass
