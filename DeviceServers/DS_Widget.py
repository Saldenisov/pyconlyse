from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusWheelEdit
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus import Device
from taurus.external.qt import Qt
from PyQt5 import QtWidgets
from PyQt5.QtGui import QMouseEvent

from typing import List
from abc import abstractmethod
from _functools import partial


class DS_General_Widget(Qt.QWidget):

    def __init__(self, device_name: str,  parent=None):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.panel_parent = parent
        self.layout_main = Qt.QVBoxLayout()
        self.dev_name = device_name
        setattr(self, f'ds_{self.dev_name}', Device(self.dev_name))
        setattr(self, f'lo_group_{1}', Qt.QHBoxLayout())
        self.layout_main.addLayout(getattr(self, f'lo_group_{1}'))
        self.setLayout(self.layout_main)

    @abstractmethod
    def register_DS(self, dev_name, group_number=1):
        pass