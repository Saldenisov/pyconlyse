'''
Created on 15.11.2019

@author: saldenisov
'''
import copy
import logging
from _functools import partial

from PyQt5.QtWidgets import (QMainWindow)
from PyQt5 import QtCore

from utilities.myfunc import info_msg, error_logger, get_local_ip
from devices.devices import Device
from utilities.data.messages import Message, ServiceInfoMes, DoneIt, Error
from utilities.data.datastructures.mes_independent.devices_dataclass import *
from utilities.data.datastructures.mes_independent.projects_dataclass import *
from communication.messaging.message_utils import MsgGenerator
from views.ui.ProjectManager import Ui_ProjectManager
from devices.service_devices.project_treatment import ProjectManager_controller


module_logger = logging.getLogger(__name__)


class ProjectManagerView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: ServiceInfoMes, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller

        self.name = f'ProjectsManagerClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("ProjectManager_controller." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: ServiceInfoMes = service_parameters

        self.ui = Ui_ProjectManager()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)  # This allows to catch messaged arriving to SuperClient
        self.ui.pushButton_get_files.clicked.connect(self.get_files)
        self.ui.pushButton_get_projects.clicked.connect(self.get_projects)
        self.ui.pushButton_get_users.clicked.connect(self.get_users)

        info_msg(self, 'INITIALIZED')

    def get_files(self):
        com = ProjectManager_controller.GET_FILE_TREE.name
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 service_id=self.service_parameters.device_id,
                                 input=FuncGetFileTreeInput())
        self.device.send_msg_externally(msg)

    def get_projects(self):
        pass

    def get_users(self):
        pass

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def model_is_changed(self, msg: Message):
        try:
            if self.service_parameters.device_id in msg.body.sender_id:
                com = msg.data.com
                info: Union[DoneIt, Error] = msg.data.info
                if com == MsgGenerator.DONE_IT.mes_name:
                    result: Union[FuncGetFileTreeOutput] = info.result
                    self.ui.comments.setText(result.comments)
                    if info.com == ProjectManager_controller.GET_FILE_TREE.name:
                        result: FuncGetFileTreeOutput = result
                        self.ui.label_files_number.setText(str(len(result.files)))
                    elif info.com == ProjectManager_controller.GET_CONTROLLER_STATE.name:
                        result: FuncGetProjectManagerControllerStateOutput = result
                        self.ui.comments.setText(f'Device status: {result.device_status}. Comments={result.comments}')
                elif com == MsgGenerator.ERROR.mes_name:
                    self.ui.comments.setText(info.comments)

                #self.update_state()
        except Exception as e:
            self.logger.error(e)
