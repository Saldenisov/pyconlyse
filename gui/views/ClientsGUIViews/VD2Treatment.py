'''
Created on 01.04.2020

@author: saldenisov
'''
import logging
from _functools import partial

from PyQt5.QtWidgets import QMainWindow, QCheckBox, QLineEdit, QProgressBar
from devices.service_devices.project_treatment.openers import CriticalInfoHamamatsu
from utilities.myfunc import info_msg
from datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D
from gui.views import Ui_GraphVD2Window

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
        self.controller.model.progressbar = self.ui.progressbar_calc

        self.ui.data_slider.valueChanged.connect(self.controller.slider_map_selector_change)
        self.ui.button_average_noise.clicked.connect(self.controller.average_noise)
        self.ui.button_calc.clicked.connect(self.controller.calc_abs)
        self.ui.button_left.clicked.connect(partial(self.map_step, -1))
        self.ui.button_play.clicked.connect(self.button_play_maps)
        self.ui.button_right.clicked.connect(partial(self.map_step, 1))
        self.ui.button_save_result.clicked.connect(self.controller.save)
        self.ui.button_set_data.clicked.connect(partial(self.controller.set_data, 'datastructures'))
        self.ui.button_set_noise.clicked.connect(partial(self.controller.set_data, 'noise'))
        self.ui.kinetics_slider.ValueChanged.connect(self.controller.slider_kinetics)
        self.ui.spectrum_slider.ValueChanged.connect(self.controller.slider_spectra)
        self.ui.lineedit_save_file_name.textChanged.connect(self.controller.save_file_path_changed)
        self.ui.spinbox.valueChanged.connect(self.controller.spinbox_map_selector_change)

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
            elif isinstance(widget, QProgressBar):
                widget.setValue(value[0] / value[1] * 100)


    def modelIsChanged(self, measurement: Measurement, map_index: int, critical_info: CriticalInfoHamamatsu = None,
                       new=False, cursors: Cursors2D = None):
        self.ui.spinbox.setValue(map_index)
        self.ui.data_slider.setValue(map_index)
        if new:
            # datacanvas update
            self.ui.data_slider.setMaximum(critical_info.number_maps-1)
            self.ui.spinbox.setMaximum(critical_info.number_maps-1)
            self.ui.datacanvas.new_data(measurement, cursors, map_index)
            # kineticscanvas update
            # kineticscanvas update
            self.ui.kineticscanvas.new_data(measurement, cursors)
            self.update_kinetics_slider(critical_info.timedelays_length - 1, cursors)
            # spectrumcanvas update
            self.ui.spectracanvas.new_data(measurement, cursors)
            self.update_spectrum_slider(critical_info.wavelengths_length - 1, cursors)
        else:
            self.ui.datacanvas.update_data(measurement, cursors=cursors, map_index=map_index)
            self.ui.kineticscanvas.update_data(measurement, cursors=cursors)
            self.ui.spectracanvas.update_data(measurement, cursors=cursors)
        if cursors:
            self.ui.datacanvas.draw_cursors(cursors=cursors, draw=True)
            self.ui.kineticscanvas.draw_cursors(cursors=cursors, draw=True)
            self.ui.spectracanvas.draw_cursors(cursors=cursors, draw=True)

    def update_kinetics_slider(self, maxValue: int, cursors: Cursors2D):
        self.ui.kinetics_slider.setMax(maxValue)
        self.ui.kinetics_slider.setStart(cursors.y1[0])
        self.ui.kinetics_slider.setEnd(cursors.y2[0])
        self.ui.kinetics_slider.update_Sliderpos()

    def update_spectrum_slider(self, maxValue: int, cursors: Cursors2D):
        self.ui.spectrum_slider.setMax(maxValue)
        self.ui.spectrum_slider.setStart(cursors.x1[0])
        self.ui.spectrum_slider.setEnd(cursors.x2[0])
        self.ui.spectrum_slider.update_Sliderpos()