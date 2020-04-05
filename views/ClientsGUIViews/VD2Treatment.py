'''
Created on 01.04.2020

@author: saldenisov
'''
import logging
from _functools import partial

from PyQt5.QtWidgets import QMainWindow, QCheckBox, QLineEdit
from devices.service_devices.project_treatment.openers import CriticalInfoHamamatsu
from utilities.myfunc import info_msg
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement
from views.ui.VD2_treatment_ui import Ui_GraphVD2Window


module_logger = logging.getLogger(__name__)


class VD2TreatmentView(QMainWindow):

    def __init__(self, in_controller, parent=None):
        super().__init__(parent)
        self.controller = in_controller
        self.name = f'VD2Treatment:view'
        self.logger = logging.getLogger("VD2Treatment:view")
        info_msg(self, 'INITIALIZING')

        self.ui = Ui_GraphVD2Window()
        self.ui.setupUi(self)

        self.controller.model.add_measurement_observer(self)
        self.controller.model.add_ui_observer(self)

        self.ui.button_set_data.clicked.connect(partial(self.controller.set_data, 'data'))
        self.ui.button_set_noise.clicked.connect(partial(self.controller.set_data, 'noise'))
        self.ui.button_left.clicked.connect(partial(self.map_step, -1))
        self.ui.button_right.clicked.connect(partial(self.map_step, 1))
        self.ui.button_average_noise.clicked.connect(self.controller.average_noise)
        self.ui.button_calc.clicked.connect(self.controller.calc_abs)
        self.ui.button_save_result.clicked.connect(self.controller.save)
        self.ui.spinbox.valueChanged.connect(self.controller.spinbox_map_selector_change)
        self.ui.data_slider.valueChanged.connect(self.controller.slider_map_selector_change)
        self.ui.button_play.clicked.connect(self.button_play_maps)

        info_msg(self, 'INITIALIZED')

    def map_step(self, dir: int):
        value_now = int(self.ui.spinbox.value())
        self.ui.spinbox.setValue(value_now + dir)

    def f(self):
        from time import sleep
        for i in range(1,500):
            self.ui.spinbox.setValue(i)
            sleep(0.2)

    def button_play_maps(self):
        from threading import Thread
        t = Thread(target=self.f)
        t.start()

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()

    def modelIsChanged_ui(self, ui: dict):
        for name, value in ui.items():
            widget = getattr(self.ui, name)
            if isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)

    def modelIsChanged(self, measurement: Measurement, map_index: int,
                       critical_info: CriticalInfoHamamatsu=None, new=False):
        """
        """
        self.logger.info(f'Map_index={map_index}')
        self.ui.datacanvas.measurement = measurement
        self.ui.spinbox.setValue(map_index)
        self.ui.data_slider.setValue(map_index)
        if new:
            v = critical_info.number_maps-1
            self.ui.data_slider.setMaximum(v)
            self.ui.spinbox.setMaximum(v)
            self.ui.datacanvas.new_data()
        else:
            self.ui.datacanvas.update_image_data()





