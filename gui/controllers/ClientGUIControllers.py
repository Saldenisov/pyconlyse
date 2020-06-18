"""
Created on 15.11.2019

@author: saldenisov
"""

import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox, QApplication, QListWidgetItem, QErrorMessage
from PyQt5.QtCore import QModelIndex
from communication.messaging.messages import MessageExt, MsgComExt
from gui.models.ClientGUIModels import VD2TreatmentModel
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent import (ProjectManagerDescription,
                                                      FuncGetProjectManagerControllerStateInput)
from utilities.datastructures.mes_independent.stpmtr_dataclass import (FuncGetStpMtrControllerStateInput, StpMtrDescription)
from devices.devices import Device
from gui.views import SuperUserView, StepMotorsView, VD2TreatmentView, ProjectManagerView
from utilities.myfunc import info_msg, get_local_ip, error_logger


module_logger = logging.getLogger(__name__)


class SuperClientGUIcontroller():

    def __init__(self, in_model):
        """
        """
        self.logger = module_logger
        self.name = 'SuperClientGUI:controller: ' + get_local_ip()
        self.services_views = {}
        info_msg(self, 'INITIALIZING')
        self.model= in_model
        self.device = self.model.superuser
        self.view = SuperUserView(self, in_model=self.model)
        self.view.show()
        info_msg(self, 'INITIALIZED')

    def exec_user_com(self, widget):
        com = widget.text()
        com_splitted = com.split(';')
        path = self.model.app_folder
        pyexec = str(Path(path.parent / 'python_env\mypy37\Scripts' / 'python.exe'))
        for x in com_splitted:
            x = x.split(' ')
            x = [command for command in x if command]
            com = x[0]
            rest = x[1:]
            if com == '-start_service':
                p = str(path / 'bin' / 'device_start.py')
                exc = f'start cmd /K {pyexec} {p} {rest[0]} {rest[1]}'
                os.system(exc)
            elif com == '-start':
                p = str(path / 'bin' / rest[0])
                exc = f'start cmd /K {pyexec} {p}'
                for r in rest[1:]:
                    exc = exc + r
                os.system(exc)

    def create_service_gui(self):
        service_id = self.view.ui.lW_devices.currentItem().text()
        try:
            parameters: DeviceInfoExt = self.model.service_parameters[service_id]
            if isinstance(parameters.device_description, StpMtrDescription):
                view = StepMotorsView
            elif isinstance(parameters.device_description, ProjectManagerDescription):
                view = ProjectManagerView

            self.services_views[service_id] = view(in_controller=self, in_model=self.model,
                                                   service_parameters=parameters)
            self.services_views[service_id].show()
            info_msg(self, 'INFO', f'GUI for service {service_id} is started')

        except KeyError:
            error_logger(self, self.create_service_gui, f'Parameters for service id={service_id} was not loaded')
        except Exception as e:
            error_logger(self, self.create_service_gui, e)

    def send_request_to_server(self, msg: MessageExt):
        self.device.send_msg_externally(msg)

    def lW_devices_double_clicked(self, item: QListWidgetItem):
        service_id = item.text()
        client = self.device

        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=service_id,
                                  func_input=FuncServiceInfoInput())
        client.send_msg_externally(msg)

    def pB_checkServices_clicked(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  func_input=FuncAvailableServicesInput())
        client.send_msg_externally(msg)

    def quit_clicked(self, event, total_close=False):
        if total_close:
            try:
                self.device.stop()
            except Exception as e:  # TODO something reasonable
                error_logger(self, self.quit_clicked, f'{self.name}: {e}')
            info_msg(self, 'INFO', 'SuperClientGUI is closing.')
            QApplication.quit()


class StepMotorsController:

    def __init__(self, in_model, device: Device=None):
        self.logger = logging.getLogger('StepMotors' + '.' + __name__)
        self.name = 'StepMotorsClient:controller: ' + get_local_ip()
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        if not Device:
            raise Exception(f"{self} no Device were given")
        self.view = StepMotorsView(self)
        self.view.show()
        info_msg(self, 'INITIALIZED')

    def quit_clicked(self, event):
        reply = QMessageBox.question(self.view, 'Quiting',
                                     "Are you sure to quit?", QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info('Closing')
            QApplication.quit()
        else:
            event.ignore()

    def connect_stpmtrctrl(self, motor_controller_name: str):
        on = self.model.dlines[motor_controller_name].start
        active = self.model.dlines[motor_controller_name].active
        if not active:
            self.model.dlines[motor_controller_name].check()
        elif not on:
            self.model.dlines[motor_controller_name].turn_on()

    def move_stpmtr(self, motor_controller_name: str, axis: int, where: int):
        pass


class VD2TreatmentController:

    def __init__(self, in_model):
        self.logger = logging.getLogger('VD2Treatment')
        self.name = 'VD2TreatmentModel:controller'
        info_msg(self, 'INITIALIZING')
        self.model: VD2TreatmentModel = in_model
        self.view = VD2TreatmentView(self)
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
        exp = VD2TreatmentModel.ExpDataStruct(self.view.ui.combobox_type_exp.currentText())
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

    def set_path(self, index: QModelIndex, exp_data_type: VD2TreatmentModel.DataTypes):
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
