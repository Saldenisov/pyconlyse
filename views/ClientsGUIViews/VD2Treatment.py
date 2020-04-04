'''
Created on 01.04.2020

@author: saldenisov
'''
import logging
from _functools import partial

from PyQt5.QtWidgets import QMainWindow
from utilities.myfunc import info_msg
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement
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

        self.controller.model.add_observer(self)

        self.ui.button_set_data.clicked.connect(partial(self.controller.set_data, 'data'))
        self.ui.spinbox.valueChanged.connect(self.controller.spinbox)

        info_msg(self, 'INITIALIZED')

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()

    def modelIsChanged(self, measurement: Measurement, new=False):
        """
        """
        self.ui.datacanvas.measurement = measurement
        self.ui.datacanvas.new_data()



