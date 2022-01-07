from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from PyQt5 import QtWidgets
from PyQt5.QtGui import QMouseEvent
from enum import Enum
from typing import List
from abc import abstractmethod
from _functools import partial


class VisType(Enum):
    MIN = 'min'
    FULL = 'full'


class DS_General_Widget(Qt.QWidget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.panel_parent = parent
        self.vis_type = vis_type
        self.layout_main = Qt.QVBoxLayout()
        self.dev_name = device_name
        setattr(self, f'ds_{self.dev_name}', Device(self.dev_name))
        setattr(self, f'lo_group_{1}', Qt.QHBoxLayout())
        self.layout_main.addLayout(getattr(self, f'lo_group_{1}'))
        self.setLayout(self.layout_main)

        if self.vis_type == VisType.FULL:
            self.register_DS_full(device_name)
        elif self.vis_type == VisType.MIN:
            self.register_DS_min(device_name)

    @abstractmethod
    def register_DS_full(self, dev_name, group_number=1):
        pass

    @abstractmethod
    def register_DS_min(self, dev_name, group_number=1):
        pass