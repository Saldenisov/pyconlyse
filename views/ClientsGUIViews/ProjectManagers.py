'''
Created on 15.11.2019

@author: saldenisov
'''
import copy
import logging

from PyQt5.QtWidgets import (QMainWindow, QTreeWidgetItem)
from PyQt5 import QtCore
from enum import Enum, auto
from utilities.myfunc import info_msg, error_logger, get_local_ip, paths_to_dict
from devices.devices import Device
from utilities.data.messages import Message, ServiceInfoMes, DoneIt, Error
from utilities.data.datastructures.mes_independent.devices_dataclass import *
from utilities.data.datastructures.mes_independent.projects_dataclass import *
from communication.messaging.message_utils import MsgGenerator
from views.ui.ProjectManager import Ui_ProjectManager
from devices.service_devices.project_treatment import ProjectManager_controller


module_logger = logging.getLogger(__name__)


class Flags(Enum):
    DEFAULT = auto()
    FILES = auto()
    FILE_DESC = auto()
    OPERATORS = auto()
    PROJECTS = auto()
    STATUS = auto()


class ProjectManagerView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: ServiceInfoMes, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.view_state: ProjectManagerViewState = None
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
        self.ui.pushButton_get_operators.clicked.connect(self.get_operators)
        self.ui.treeWidget.clicked.connect(self.file_tree_click)
        self.ui.treeWidget.doubleClicked.connect(self.file_tree_double_click)

        info_msg(self, 'INITIALIZED')

    def get_files(self):
        com = ProjectManager_controller.GET_FILES.name
        operator_email = self.ui.comboBox_operators.itemText(self.ui.comboBox_operators.currentIndex())
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 device_id=self.service_parameters.device_id,
                                 input=ProjectManager_controller.GET_FILES.func_input(operator_email))
        self.device.send_msg_externally(msg)

    def get_projects(self):
        pass

    def get_operators(self):
        com = ProjectManager_controller.GET_OPERATORS.name
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 device_id=self.service_parameters.device_id,
                                 input=ProjectManager_controller.GET_OPERATORS.func_input())
        self.device.send_msg_externally(msg)

    def get_state(self):
        com = ProjectManager_controller.GET_CONTROLLER_STATE.name
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 device_id=self.service_parameters.device_id,
                                 input=ProjectManager_controller.GET_CONTROLLER_STATE.func_input())
        self.device.send_msg_externally(msg)

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
                    result: Union[FuncGetFilesOutput, FuncGetFileDescirptionOutput] = info.result
                    self.ui.comments.setText(result.comments)
                    if info.com == ProjectManager_controller.GET_CONTROLLER_STATE.name:
                        flag = Flags.STATE
                    elif info.com == ProjectManager_controller.GET_FILES.name:
                        flag = Flags.FILES
                    elif info.com == ProjectManager_controller.GET_FILE_DESCRIPTION.name:
                        flag = Flags.FILE_DESC
                    elif info.com == ProjectManager_controller.GET_OPERATORS.name:
                        flag = Flags.OPERATORS
                    elif info.com == ProjectManager_controller.GET_PROJECTS.name:
                        flag = Flags.PROJECTS
                    else:
                        flag = Flags.DEFAULT
                    self.update_state(result, flag)
                elif com == MsgGenerator.ERROR.mes_name:
                    self.ui.comments.setText(info.comments)

        except Exception as e:
            self.logger.error(e)

    def update_state(self, res: FuncOutput, changed=Flags.DEFAULT):
        def operators(self):
            operators: List[str] = self.controller_state.operators
            self.ui.label_operators.setText(f'Operators: {len(operators)}')
            self.ui.update_operators(operators)

        all_func = [operators]

        if changed == 'all':
            for func in all_func:
                func(self)

        elif changed == 'operators':
            operators(self)

    def diff_state_action(self, new_state: ProjectManagerControllerState):
        if not self.view_state:
            self.view_state = ProjectManagerViewState(controller_state=new_state)

        controller_state = self.view_state.controller_state

        if controller_state != new_state:
            if controller_state.files_len != new_state.files_len:
                self.get_files()
            if controller_state.projects_len != new_state.projects_len:
                self.get_projects()
            if controller_state.operators_len != new_state.operators_len:
                self.get_operators()

            self.view_state.controller_state = new_state

