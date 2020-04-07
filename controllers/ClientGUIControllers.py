'''
Created on 15.11.2019

@author: saldenisov
'''

import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox, QApplication, QListWidgetItem
from communication.messaging.message_utils import MsgGenerator
from utilities.myfunc import info_msg, get_local_ip
from utilities.data.messages import Message
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import FuncGetStpMtrControllerStateInput
from views.ClientsGUIViews import SuperUserView, StepMotorsView, VD2TreatmentView
from devices.devices import Device


module_logger = logging.getLogger(__name__)


class SuperClientGUIcontroller():

    def __init__(self, in_model):
        """
        """
        self.logger = module_logger
        self.name = 'SuperClientGUI:controller: ' + get_local_ip()
        self.services_views = {}
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device = self.model.superuser
        self.view = SuperUserView(self, in_model=self.model)
        self.view.show()
        info_msg(self, 'INITIALIZED')

    def exec_user_com(self, widget):
        com = widget.text()
        com_splitted = com.split(';')
        path = self.model.app_folder
        pyexec = str(pathlib.Path(path.parent / 'python_env\mypy37\Scripts' / 'python.exe'))
        for x in com_splitted:
            x = x.split(' ')
            x = [command for command in x if command]
            com = x[0]
            rest = x[1:]
            if com == '-start_service':
                p = str(path / 'bin' / 'service.py')
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
            parameters = self.model.service_parameters[service_id]
        except KeyError as e:
            self.logger.error(f'Service with id {service_id} does not have parameters')
        try:
            self.services_views[service_id] = StepMotorsView(in_controller=self, in_model=self.model,
                                                             service_parameters=parameters)
            self.services_views[service_id].show()
            self.logger.info(f'GUI for service {service_id} is started')
            msg = MsgGenerator.do_it(com='get_controller_state', device=self.device,
                                     service_id=service_id,
                                     input=FuncGetStpMtrControllerStateInput())
            self.device.send_msg_externally(msg)
        except Exception as e:
            print(f'in create_service_gui {e}')

    def send_request_to_server(self, msg: Message):
        self.device.send_msg_externally(msg)

    def lW_devices_double_clicked(self, item: QListWidgetItem):
        service_id = item.text()
        msg = MsgGenerator.info_service_demand(device=self.device, service_id=service_id)
        self.device.send_msg_externally(msg)

    def pB_checkServices_clicked(self):
        msg = MsgGenerator.available_services_demand(device=self.device)
        self.device.thinker.add_task_out(msg)

    def quit_clicked(self, event, total_close=False):
        if total_close:
            try:
                self.device.stop()
            except Exception as e:
                print(e)
            self.logger.info('Closing')
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
        self.name = 'VD2Treatment:controller'
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.view = VD2TreatmentView(self)
        self.view.show()

        info_msg(self, 'INITIALIZED')

    def average_noise(self):
        self.model.average_noise()

    def calc_abs(self):
        self.view.ui.progressbar_calc.setValue(0)
        exp: str = self.view.ui.combobox_type_exp.currentText()
        if self.view.ui.radiobutton_individual:
            how = 'individual'
        elif self.view.ui.radiobutton_averaged:
            how = 'averaged'
        first_map_with_electrons: bool = self.view.ui.checkbox_first_img_with_pulse.isChecked()
        self.model.calc_abs(exp, how, first_map_with_electrons)

    def data_cursor_update(self, eclick, erelease):
        self.model.update_data_cursors(eclick.xdata,
                                       erelease.xdata,
                                       eclick.ydata,
                                       erelease.ydata)

    def save(self):
        self.model.save()

    def save_file_path_changed(self):
        a = self.view.ui.lineedit_save_file_name.text()
        self.model.save_file_path_change(a)

    def set_data(self, signal: str):
        try:
            x = self.view.ui.tree.selectedIndexes()
            file_path = Path(self.view.ui.tree.model().filePath(x[0]))

            if file_path.is_file() and file_path.exists():
                if signal == 'data':
                    self.model.add_data_path(file_path)
                elif signal == 'noise':
                    self.model.add_noise_path(file_path)

        except Exception as e:
            self.logger.error(f'Error in picking files from Tree {e}')

    def spinbox_map_selector_change(self):
        value = int(self.view.ui.spinbox.value())
        self.view.ui.data_slider.setValue(value)

    def slider_map_selector_change(self):
        value = int(self.view.ui.data_slider.value())
        self.model.read_data(value)
        self.view.ui.spinbox.setValue(value)
