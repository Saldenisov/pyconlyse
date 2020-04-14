'''
Created on 15.11.2019

@author: saldenisov
'''
import copy
import logging
from _functools import partial

from PyQt5.QtWidgets import (QMainWindow, QTreeWidgetItem)
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
        self.ui.treeView_file.clicked.connect(self.file_tree_click)
        self.ui.treeView_file.doubleClicked.connect(self.file_tree_double_click)

        info_msg(self, 'INITIALIZED')

    def get_files(self):
        com = ProjectManager_controller.GET_FILE_TREE.name
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 device_id=self.service_parameters.device_id,
                                 input=FuncGetFileTreeInput())
        self.device.send_msg_externally(msg)

    def get_projects(self):
        pass

    def get_users(self):
        pass

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def file_tree_double_click(self, index: QtCore.QModelIndex):
        pass

    def file_tree_click(self, index: QtCore.QModelIndex):
        name: str = index.data()
        if '~ID~' in name:
            file_id = name.split('~ID~')[1].split('.')[0]
            com = ProjectManager_controller.GET_FILE_DESCRIPTION.name
            msg = MsgGenerator.do_it(device=self.device, com=com,
                                     device_id=self.service_parameters.device_id,
                                     input=FuncGetFileDescirptionInput(file_id=file_id))
            self.device.send_msg_externally(msg)

    def model_is_changed(self, msg: Message):
        try:
            if self.service_parameters.device_id in msg.body.sender_id:
                com = msg.data.com
                info: Union[DoneIt, Error] = msg.data.info
                if com == MsgGenerator.DONE_IT.mes_name:
                    result: Union[FuncGetFileTreeOutput, FuncGetFileDescirptionOutput] = info.result
                    self.ui.comments.setText(result.comments)
                    if info.com == ProjectManager_controller.GET_FILE_TREE.name:
                        result: FuncGetFileTreeOutput = result
                        self.ui.label_files_number.setText(f'Files: {len(result.files)}')
                        self.ui.fill_file_tree(value=result.file_tree)
                    elif info.com == ProjectManager_controller.GET_CONTROLLER_STATE.name:
                        result: FuncGetProjectManagerControllerStateOutput = result
                        self.ui.comments.setText(f'Device status: {result.device_status}. Comments={result.comments}')
                    elif info.com == ProjectManager_controller.GET_FILE_DESCRIPTION.name:
                        result: FuncGetFileDescirptionOutput = result
                        self.ui.update_table_description(result)
                elif com == MsgGenerator.ERROR.mes_name:
                    self.ui.comments.setText(info.comments)

                #self.update_state()
        except Exception as e:
            self.logger.error(e)
