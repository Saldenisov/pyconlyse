'''
Created on 15.11.2019

@author: saldenisov
'''

import os
import logging
import pathlib
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

    def set_data(self, signal: str):
        from os.path import isfile, exists
        from pathlib import Path
        try:
            x = self.view.ui.tree.selectedIndexes()
            file_path = self.view.ui.tree.model().filePath(x[0])

            if isfile(file_path) and exists(file_path):
                if signal == 'data':
                    self.model.data_path = Path(file_path)
                    self.model.read_data()
                elif signal == 'noise':
                    self.model.noise_path = Path(file_path)

        except:
            self.logger.error('Error in picking files from Tree')