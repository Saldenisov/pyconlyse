"""
Created on 01.04.2020

@author: saldenisov
"""
import logging
from _functools import partial

from PyQt5.QtWidgets import QMainWindow, QCheckBox, QLineEdit, QProgressBar, QMenu

from gui.controllers.openers import CriticalInfoHamamatsu
from gui.models.ClientGUIModels import TreatmentModel
from gui.views.ui import Ui_GraphWindow
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D
from utilities.myfunc import info_msg

module_logger = logging.getLogger(__name__)


ExpDataStruct: TreatmentModel.ExpDataStruct = TreatmentModel.ExpDataStruct
DataTypes: TreatmentModel.DataTypes = TreatmentModel.DataTypes


class TreatmentView(QMainWindow):

    def __init__(self, in_controller, parent=None):
        super().__init__(parent)
        self.controller = in_controller
        self.name = f'VD2Treatment:view'
        self.logger = logging.getLogger('VD2Treatment')
        info_msg(self, 'INITIALIZING')

        self.ui = Ui_GraphWindow()
        self.ui.setupUi(self, data_folder=in_controller.model.data_folder)

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
        self.ui.button_get_kinetics.clicked.connect(partial(self.controller.get_average, 'kinetics'))
        self.ui.button_get_spectra.clicked.connect(partial(self.controller.get_average, 'spectra'))
        self.ui.kinetics_slider.ValueChanged.connect(self.controller.slider_kinetics)
        self.ui.spectrum_slider.ValueChanged.connect(self.controller.slider_spectra)
        self.ui.button_set_folder.clicked.connect(self.controller.data_folder_changed)
        self.ui.lineedit_save_file_name.returnPressed.connect(self.controller.save_file_path_changed)
        self.ui.lineedit_save_folder.returnPressed.connect(self.controller.save_file_folder_changed)
        self.ui.spinbox.valueChanged.connect(self.controller.spinbox_map_selector_change)
        self.ui.combobox_type_exp.currentIndexChanged.connect(self._combobox_index_change)
        self.ui.tree.customContextMenuRequested.connect(self.menuContextTree)
        self.ui.combobox_files_selected.customContextMenuRequested.connect(self.menuContextComboBoxFiles)
        self.ui.combobox_files_selected.currentIndexChanged.connect(self.controller.combobox_files_changed)
        self.ui.button_calc_sam.clicked.connect(self.controller.calc_sam)
        self.ui.button_clean_sam.clicked.connect(self.controller.clean_his_sam)
        self.ui.button_save_clean.clicked.connect(self.controller.save_clean_h5)
        info_msg(self, 'INITIALIZED')

    def menuContextComboBoxFiles(self, point):
        menu = QMenu()
        action_remove_this = menu.addAction('Remove This')
        action_remove_all = menu.addAction('Remove All')

        action = menu.exec_(self.ui.combobox_files_selected.mapToGlobal(point))

        if action:
            if action == action_remove_all:
                self.ui.combobox_files_selected.clear()
            elif action == action_remove_this:
                idx = self.ui.combobox_files_selected.currentIndex()
                self.ui.combobox_files_selected.removeItem(idx)

    def menuContextTree(self, point):
        # Infos about the node selected.
        index = self.ui.tree.indexAt(point)
        if not index.isValid():
            return

        # We build the menu.
        menu = QMenu()
        action_set_ABS=action_set_BASE=action_set_NOISE=action_set_DATA_HIS=action_set_NOISE=action_set_DATA_NOISE_HIS=\
            None
        action_plus = menu.addAction('Add file')
        if ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.ABS_BASE_NOISE:
            action_set_ABS = menu.addAction("set ABS HIS or IMG")
            action_set_BASE = menu.addAction("set BASE HIS or IMG")
            action_set_NOISE = menu.addAction("set NOISE HIS or IMG")
        elif ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.HIS_NOISE:
            action_set_DATA_HIS = menu.addAction("set ABS+BASE HIS")
            action_set_NOISE= menu.addAction("set NOISE HIS or IMG")
        elif ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.HIS:
            action_set_DATA_NOISE_HIS = menu.addAction("set ABS+BASE+NOISE HIS")

        action = menu.exec_(self.ui.tree.mapToGlobal(point))

        if action:
            if action == action_set_NOISE:
                self.controller.set_path(index, DataTypes.NOISE)
            elif action == action_set_ABS:
                self.controller.set_path(index, DataTypes.ABS)
            elif action == action_set_BASE:
                self.controller.set_path(index, DataTypes.BASE)
            elif action == action_set_DATA_HIS:
                self.controller.set_path(index, DataTypes.ABS_BASE)
            elif action == action_set_DATA_NOISE_HIS:
                self.controller.set_path(index, DataTypes.ABS_BASE_NOISE)
            elif action == action_plus:
                idx = self.ui.tree.selectedIndexes()[0]
                file_path = self.ui.tree.model().filePath(idx)
                chk = []
                combox_l = self.ui.combobox_files_selected.count()
                for i in range(combox_l):
                    if file_path != self.ui.combobox_files_selected.itemText(i):
                        chk.append(True)
                    else:
                        chk.append(False)
                        break
                if all(chk):
                    self.ui.combobox_files_selected.addItem(file_path)
                    self.ui.combobox_files_selected.setCurrentIndex(combox_l)

    def _combobox_index_change(self):
        if ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.ABS_BASE_NOISE:
            self.ui.radiobutton_individual.setDisabled(True)
            self.ui.radiobutton_averaged.setChecked(True)
            self.ui.checkbox_first_img_with_pulse.setDisabled(True)
        else:
            self.ui.radiobutton_individual.setDisabled(False)
            self.ui.checkbox_first_img_with_pulse.setDisabled(False)
            self.ui.radiobutton_individual.setChecked(True)

    def map_step(self, dir: int):
        value_now = int(self.ui.spinbox.value())
        self.ui.spinbox.setValue(value_now + dir)

    def f(self):
        from time import sleep
        for i in range(1, 500):
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
                if name not in ['lineedit_save_folder']:
                    if name == 'lineedit_save_file_name':
                        short_value = [value]
                        value = self.ui.lineedit_save_folder.text() + '\\' + value
                    if not isinstance(value, list):
                        value = [value]
                    for val in value:
                        chk = []
                        for i in range(self.ui.combobox_files_selected.count()):
                            if val != self.ui.combobox_files_selected.itemText(i):
                                chk.append(True)
                            else:
                                chk.append(False)
                                break
                        if all(chk):
                            self.ui.combobox_files_selected.addItem(val)
                    if name != 'lineedit_save_file_name':
                        widget.setText('; '.join(value))
                    else:
                        widget.setText('; '.join(short_value))

            elif isinstance(widget, QProgressBar):
                widget.setValue(int(value[0] / value[1] * 100))

    def modelIsChanged(self,
                       measurement: Measurement,
                       map_index: int,
                       critical_info: CriticalInfoHamamatsu = None,
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
            self.ui.kinetics_average_canvas.new_data(critical_info)
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
            self.update_kinetics_slider(cursors=cursors)
            self.update_spectrum_slider(cursors=cursors)

    def update_kinetics_slider(self, maxValue: int = -1, cursors: Cursors2D=None):
        self.ui.kinetics_slider.setStart(int(cursors.y1[0]))
        self.ui.kinetics_slider.setEnd(int(cursors.y2[0]))
        if maxValue > 0:
            self.ui.kinetics_slider.setMax(maxValue)
        self.ui.kinetics_slider.update_Sliderpos()

    def update_spectrum_slider(self, maxValue: int = -1, cursors: Cursors2D = None):
        self.ui.spectrum_slider.setStart(int(cursors.x1[0]))
        self.ui.spectrum_slider.setEnd(int(cursors.x2[0]))
        if maxValue > 0:
            self.ui.spectrum_slider.setMax(maxValue)
        self.ui.spectrum_slider.update_Sliderpos()
