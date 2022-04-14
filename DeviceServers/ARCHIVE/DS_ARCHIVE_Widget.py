from collections import deque

import numpy as np
import pyqtgraph as pg
from taurus import Device
from taurus.core import TaurusDevState
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox
from tango import DevState
from PyQt5 import QtWidgets
from PyQt5.QtCore import QDate


from DeviceServers.DS_Widget import DS_General_Widget, VisType


class ViewTree(QtWidgets.QTreeWidget):
    def __init__(self):
        super().__init__()

    def fill_items(self, item, value):
        self.clean_tree()
        self.fill_item(item, value)

    def fill_item(self, item, value):

        def new_item(parent, text, val=None):
            child = QtWidgets.QTreeWidgetItem([text])
            self.fill_item(child, val)
            parent.addChild(child)
            child.setExpanded(True)

        if value is None:
            return
        elif isinstance(value, dict):
            for key, val in sorted(value.items()):
                new_item(item, str(key), val)
        elif isinstance(value, (list, tuple)):
            for val in value:
                text = (str(val) if not isinstance(val, (dict, list, tuple))
                        else '[%s]' % type(val).__name__)
                new_item(item, text, val)
        else:
            new_item(item, str(value))

    def clean_tree(self):
        parent = self.invisibleRootItem()
        for i in reversed(range(parent.childCount())):
            parent.removeChild(parent.child(i))


class Archive(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.structure = {}
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
        self.calendar.clicked.connect(self.structure_update)
        layout_v_tree = QtWidgets.QVBoxLayout()
        layout_h_tree_selectors = QtWidgets.QHBoxLayout()
        self.tree_structure = ViewTree()
        self.projects_cb = QtWidgets.QCheckBox('Projects')
        self.projects_cb.setChecked(True)
        self.devices_cb = QtWidgets.QCheckBox('Devices')
        self.devices_cb.setChecked(True)
        self.date_cb = QtWidgets.QCheckBox('Selected date?')

        layout_h_tree_selectors.addWidget(self.projects_cb)
        layout_h_tree_selectors.addWidget(self.devices_cb)
        layout_h_tree_selectors.addWidget(self.date_cb)
        layout_v_tree.addWidget(self.tree_structure)
        layout_v_tree.addLayout(layout_h_tree_selectors)
        self.tree_structure.setMinimumWidth(450)
        lo_calendar.addWidget(self.calendar)
        lo_calendar.addLayout(layout_v_tree)

        # Buttons and commands
        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        self.button_update_structure = QtWidgets.QPushButton('Update')
        self.button_update_structure.clicked.connect(self.get_structure)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)
        lo_buttons.addWidget(self.button_update_structure)

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

    def get_structure(self):
        structure = self.ds.archive_structure
        self.structure = eval(structure)
        selected_structure = self.select_structure()
        self.fill_tree_structure(selected_structure)

    def fill_tree_structure(self, structure):
        self.tree_structure.fill_items(self.tree_structure.invisibleRootItem(), structure)

    def select_structure(self, date=None):
        date_structure = {}
        date_s = '...'
        if not self.structure:
            self.get_structure()
        try:
            if self.date_cb.isChecked() and date:
                date_s = date.toString('yyyy-MM-dd')
                date_structure[date_s] = self.structure[date_s]
            else:
                date_structure = self.structure
        except KeyError:
            print(f'Such date {date_s} is not present in Archive.')
        finally:
            return date_structure

    def structure_update(self, date: QDate):
        part_structure = self.select_structure(date)
        self.fill_tree_structure(part_structure)
