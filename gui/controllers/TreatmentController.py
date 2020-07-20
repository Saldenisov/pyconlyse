"""
Created on 17.07.2020

@author: saldenisov
"""

import logging
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QErrorMessage, QFileDialog

from gui.models.ClientGUIModels import TreatmentModel
from gui.views.ClientsGUIViews import TreatmentView
from utilities.myfunc import info_msg, error_logger

module_logger = logging.getLogger(__name__)


class TreatmentController:

    def __init__(self, in_model):
        self.logger = logging.getLogger('VD2Treatment')
        self.name = 'VD2TreatmentModel:controller'
        info_msg(self, 'INITIALIZING')
        self.model: TreatmentModel = in_model
        self.view = TreatmentView(self)
        self.view.show()

        info_msg(self, 'INITIALIZED')

    def average_noise(self):
        res, comments = self.model.average_noise()
        if not res:
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def calc_abs(self):
        self.view.ui.progressbar_calc.setValue(0)
        exp = TreatmentModel.ExpDataStruct(self.view.ui.combobox_type_exp.currentText())
        if self.view.ui.radiobutton_individual:
            how = 'individual'
        elif self.view.ui.radiobutton_averaged:
            how = 'averaged'

        first_map_with_electrons: bool = self.view.ui.checkbox_first_img_with_pulse.isChecked()
        self.model.calc_abs(exp, how, first_map_with_electrons)

    def combobox_files_changed(self):
        file_path = Path(self.view.ui.combobox_files_selected.currentText())
        if file_path.is_file():
            if self.view.ui.data_slider.value() != 0:
                self.view.ui.data_slider.setValue(0)
            else:
                self.model.read_data(file_path, 0, new=True)

    def data_cursor_update(self, eclick, erelease):
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        if data_path.is_file():
            self.model.update_data_cursors(data_path, eclick.xdata, erelease.xdata, eclick.ydata, erelease.ydata)
        else:
            error_logger(self, self.data_cursor_update, f'Data path is not a file')

    def data_folder_changed(self):
        dialog = QFileDialog()
        foo_dir = dialog.getExistingDirectory(self.view, 'Select a directory')
        folder = Path(str(foo_dir))
        if folder.is_dir():
            self.view.ui.redraw_file_tree(folder)

    def get_average(self, user_type: str='kinetics'):
        error = False
        if user_type == 'kinetics':
            line = self.view.ui.lineedit_kinetics_ranges.text()
        elif user_type == 'spectra':
            line = self.view.ui.lineedit_spectra_ranges.text()
        else:
            error = True
            self.show_error(self.get_average, f'User_type {user_type} is not "kinetics" or "spectra"')

        if not error:
            file = self.view.ui.combobox_files_selected.currentText()
            file_path = Path(file)
            if file_path.exists() and file:
                n = self.view.ui.spinbox.value()
                s = self.model.average_range(line, file_path, user_type, n)
                if s:
                    line_new = []
                    for key, value in s.items():
                        line_new.append(f' {key} {value}')
                    if user_type == 'kinetics':
                        self.view.ui.lineedit_kinetics_ranges.setText(';'.join(line_new).strip())
                    elif user_type == 'spectra':
                        self.view.ui.lineedit_spectra_ranges.setText(';'.join(line_new).strip())
            else:
                self.show_error(self.get_average, f'File_path {file_path} does not exist.')

    def save(self):
        self.model.save()

    def save_file_path_changed(self):
        folder = self.view.ui.lineedit_save_folder.text()
        file = self.view.ui.lineedit_save_file_name.text()
        self.model.save_file_path_change(folder, file)

    def save_file_folder_changed(self):
        folder = self.view.ui.lineedit_save_folder.text()
        file = self.view.ui.lineedit_save_file_name.text()
        self.model.save_file_path_change(folder, file)

    def set_path(self, index: QModelIndex, exp_data_type: TreatmentModel.DataTypes):
        try:
            file_path = Path(self.view.ui.tree.model().filePath(index))
            if file_path.is_file() and file_path.exists():
                self.model.add_data_path(file_path, exp_data_type)
        except Exception as e:
            error_logger(self, self.set_path, f'Error in picking files from Tree: {e}')

    def slider_kinetics(self, index_slider, start, end):
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        self.model.update_data_cursors(data_path=data_path, y1=start, y2=end, pixels=True)

    def slider_spectra(self, index_slider, start, end):
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        self.model.update_data_cursors(data_path=data_path, x1=start, x2=end, pixels=True)

    def spinbox_map_selector_change(self):
        value = int(self.view.ui.spinbox.value())
        self.view.ui.data_slider.setValue(value)

    def slider_map_selector_change(self):
        value = int(self.view.ui.data_slider.value())
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        if data_path.is_file():
            self.model.read_data(data_path, value)
            self.view.ui.spinbox.setValue(value)

    def show_error(self, func: Callable, comments: str = ''):
        error_logger(self, func, comments)
        error_dialog = QErrorMessage()
        error_dialog.showMessage(comments)
        error_dialog.exec_()
