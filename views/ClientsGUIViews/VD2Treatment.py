'''
Created on 01.04.2020

@author: saldenisov
'''
import copy
import logging
from _functools import partial

from PyQt5.QtWidgets import (QWidget, QMainWindow,
                             QPushButton, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QRadioButton,
                             QLabel, QLineEdit, QLayout,
                             QSpacerItem, QSizePolicy, QWidgetItem)
from PyQt5 import QtCore

from utilities.myfunc import info_msg, error_logger, get_local_ip
from views.ui.VD2_treatment_ui import Ui_GraphVD2Window


module_logger = logging.getLogger(__name__)


class VD2TreatmentView(QMainWindow):

    def __init__(self, in_controller, parent=None):
        super().__init__(parent)
        self.controller = in_controller
        self.name = f'VD2Treatment:view'
        self.logger = logging.getLogger("VD2Treatment")
        info_msg(self, 'INITIALIZING')

        self.ui = Ui_GraphVD2Window()
        self.ui.setupUi(self)

        #self.model.add_observer(self)

        info_msg(self, 'INITIALIZED')

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()