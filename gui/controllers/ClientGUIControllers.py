"""
Created on 15.11.2019

@author: saldenisov
"""

import logging
import os
from pathlib import Path
from time import sleep
from PyQt5.QtWidgets import QMessageBox, QApplication, QListWidgetItem

from communication.messaging.messages import MessageExt, MsgComExt
from communication.messaging.messengers import PUB_Socket_Server
from utilities.errors.myexceptions import DeviceError
from devices.devices import Device
from gui.views.ClientsGUIViews.Cameras import CamerasView
from gui.views.ClientsGUIViews.ProjectManagers import ProjectManagerView
from gui.views.ClientsGUIViews.SuperUser import SuperUserView
from gui.views.ClientsGUIViews.StepMotors import StepMotorsView
from gui.views.ClientsGUIViews.PDUs import PDUsView
from gui.views.ClientsGUIViews.DAQmxes import DAQmxView
from devices.devices_dataclass import *
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

    def create_service_gui(self, service_id_ext=''):
        if service_id_ext:
            service_id = service_id_ext
        else:
            service_id = self.view.ui.lW_devices.currentItem().text()

        try:
            parameters: ControllerInfoExt = self.model.service_parameters[service_id]
            if 'StpMtr' in parameters.device_description.class_name:
                view = StepMotorsView
            elif 'ProjectManager' in parameters.device_description.class_name:
                view = ProjectManagerView
            elif 'Camera' in parameters.device_description.class_name:
                view = CamerasView
            elif 'PDU' in parameters.device_description.class_name:
                view = PDUsView
            elif 'DAQmx' in parameters.device_description.class_name:
                view = DAQmxView

            self.services_views[service_id] = view(in_controller=self, in_model=self.model,
                                                   service_parameters=parameters)
            self.services_views[service_id].show()
            info_msg(self, 'INFO', f'GUI for service {service_id} is started')
        except KeyError as e:
            error_logger(self, self.create_service_gui,
                         f'Parameters for service id={service_id} was not loaded: {e}')

    def send_request_to_server(self, msg: MessageExt):
        self.device.send_msg_externally(msg)

    def lW_devices_double_clicked(self, item: QListWidgetItem):
        service_id = item.text()
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id(service_id),
                                  forward_to=service_id, func_input=FuncServiceInfoInput())
        client.send_msg_externally(msg)

    def pB_checkServices_clicked(self):
        client = self.device
        for server_id in client.messenger.connections.keys():
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=server_id,
                                      func_input=FuncAvailableServicesInput())
            client.send_msg_externally(msg)

    def server_change(self, connect=True):
        selected_index = self.view.ui.comboBox_servers.currentIndex()
        selected_addr = self.view.ui.comboBox_servers.itemText(selected_index)
        connections = list(self.device.connections.values())
        active_server_pub_addr = ''
        if connections:
            connection: Connection = connections[0]
            active_server_pub_addr = connection.device_public_sockets[PUB_Socket_Server]

        if not connect and self.device.connections:
            self.view.ui.label_HB.setText(f'Disconnecting from {selected_addr}...wait')
            sleep(1)
            self.device.stop()
            sleep(1)
            self.model.superuser = None
            self.view.ui.label_HB.setText(f'Disconnected from {selected_addr}')

        if selected_addr in self.device.messenger.addresses[PUB_Socket_Server] and \
                selected_addr != active_server_pub_addr and connect:
            self.device.stop()
            self.model.superuser = None
            self.model.create_device()
            self.device = self.model.superuser
            self.device.messenger.pref_server_pub_addr = selected_addr
            self.device.start()

        elif selected_addr in self.device.messenger.addresses[PUB_Socket_Server] and connect:
            self.view.ui.label_HB.setText(f'Trying to connect {selected_addr}...wait')
            self.model.create_device()
            self.device = self.model.superuser
            self.device.messenger.pref_server_pub_addr = selected_addr
            self.device.start()

    def quit_clicked(self, event, total_close=False):
        if total_close:
            try:
                self.view._state_observing = False
                self.device.stop()
            except DeviceError as e:
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
        reply = QMessageBox.question(self.view, 'Quiting', "Are you sure to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info('Closing')
            QApplication.quit()
        else:
            event.ignore()
