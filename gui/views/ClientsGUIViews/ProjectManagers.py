"""
Created on 15.11.2019

@author: saldenisov
"""
import logging
from enum import auto

from PyQt5 import QtCore, QtWidgets, QtGui

from communication.messaging.messages import MessageInt, MsgComInt, MsgComExt
from devices.devices import Device
from devices.service_devices.project_treatment import ProjectManager_controller
from gui.views.ui.ProjectManager import Ui_ProjectManager
from utilities.datastructures.mes_independent import *
from utilities.myfunc import info_msg, get_local_ip, paths_to_dict

module_logger = logging.getLogger(__name__)


class Flags(Enum):
    DEFAULT = auto()
    DRAW_FILES = auto()
    FILES = auto()
    FILE_DESC = auto()
    OPERATORS = auto()
    PROJECTS = auto()
    STATE = auto()


class ProjectManagerView(QtWidgets.QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: ControllerInfoExt, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.view_state: ProjectManagerViewState = None
        self.name = f'ProjectsManagerClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("ProjectManager_controller." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: ControllerInfoExt = service_parameters

        self.ui = Ui_ProjectManager()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)  # This allows to catch messaged arriving to SuperClient
        self.ui.pushButton_get_files.clicked.connect(self.get_files)
        self.ui.pushButton_get_projects.clicked.connect(self.get_projects)
        self.ui.pushButton_get_operators.clicked.connect(self.get_operators)
        self.ui.treeWidget.clicked.connect(self.file_tree_click)
        self.ui.treeWidget.doubleClicked.connect(self.file_tree_double_click)

        msg = self.device.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncGetStpMtrControllerStateInput())
        self.device.send_msg_externally(msg)
        info_msg(self, 'INITIALIZED')

    def get_files(self):
        operator_email = self.ui.comboBox_operators.itemText(self.ui.comboBox_operators.currentIndex())
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetFilesInput(operator_email=operator_email))
        client.send_msg_externally(msg)

    def get_projects(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetProjectsInput())
        client.send_msg_externally(msg)

    def get_operators(self):

        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetOperatorsInput())
        client.send_msg_externally(msg)

    def get_state(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetControllerStateInput())
        client.send_msg_externally(msg)

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def diff_state_action(self, new_state: ProjectManagerControllerState):
        def check_all(self):
            self.get_files()
            self.get_operators()
            self.get_projects()

        if not self.view_state:
            self.view_state = ProjectManagerViewState(controller_state=new_state)
            check_all(self)

        controller_state = self.view_state.controller_state

        if controller_state != new_state:
            if controller_state.files_len != new_state.files_len:
                self.get_files()
            if controller_state.projects_len != new_state.projects_len:
                self.get_projects()
            if controller_state.operators_len != new_state.operators_len:
                self.get_operators()

            self.view_state.controller_state = new_state
        else:
            print('no')

    def file_tree_double_click(self, index: QtCore.QModelIndex):
        pass

    def file_tree_click(self, index: QtCore.QModelIndex):
        name: str = index.data()
        if '~ID~' in name:
            file_id = name.split('~ID~')[1].split('.')[0]
            client = self.device
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                      func_input=FuncGetFileDescriptionInput(file_id=file_id))
            client.send_msg_externally(msg)

    def model_is_changed(self, msg: MessageInt):
        try:
            if self.service_parameters.device_id == msg.forwarded_from or \
                    self.service_parameters.device_id == msg.sender_id:
                com = msg.com
                info: Union[DoneIt, MsgError] = msg.info
                if com == MsgComInt.DONE_IT.msg_name:
                    result: Union[FuncGetFilesOutput, FuncGetFileDescriptionOutput] = info
                    self.ui.comments.setText(result.comments)
                    if result.func_success:
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
                elif com == MsgComExt.ERROR.mes_name:
                    self.ui.comments.setText(info.comments)

        except Exception as e:
            self.logger.error(e)

    def update_state(self, res: FuncOutput, flag=Flags.DEFAULT):
        if flag is Flags.STATE:
            result: FuncGetProjectManagerControllerStateOutput = res
            self.diff_state_action(result.state)
        elif flag is Flags.FILES:
            result: FuncGetFilesOutput = res
            self.view_state.files_paths = result.files
            self.view_state.controller_state.files_len = len(result.files)
            self.ui.label_files.setText(f'Files: {self.view_state.controller_state.files_len}')
            self.update_file_tree(value=paths_to_dict(result.files, d={'dirs': {}, 'files': []}))
        elif flag is Flags.OPERATORS:
            result: FuncGetOperatorsOutput = res
            self.view_state.operators = result.operators
            self.ui.label_operators.setText(f'Operators: {self.view_state.controller_state.operators_len}')
            self.update_operators(result.operators)
        elif flag is Flags.PROJECTS:
            result: FuncGetProjectsOutput = res
            self.view_state.projects_names = result.projects_names
            self.view_state.projects_paths = result.projects_files
            self.ui.label_projects.setText(f'Projects: {self.view_state.controller_state.projects_len}')
            self.update_projects(result.projects_names)
        elif flag is Flags.FILE_DESC:
            result: FuncGetFileDescriptionOutput = res
            self.update_table_description(result)

    def update_file_tree(self, item=None, value={}):

        if not item:
            self.ui.treeWidget.clear()
            item = self.ui.treeWidget.invisibleRootItem()

        def new_item(parent, key, val=None):
            child = QtWidgets.QTreeWidgetItem([key])
            if not isinstance(val, str):
                self.update_file_tree(child, val)
            parent.addChild(child)
            child.setExpanded(True)

        if not value:
            return
        elif isinstance(value, dict):
            for key, val in sorted(value.items()):
                if key not in ['dirs', 'files']:
                    new_item(item, str(key), val)
                else:
                    self.update_file_tree(item, val)
        elif isinstance(value, (list, tuple)):
            for val in value:
                text = (str(val) if not isinstance(val, (dict, list, tuple)) else '[%s]' % type(val).__name__)
                new_item(item, text, val)
        else:
            new_item(item, str(value))

    def update_operators(self, operators: List[Operator]):
        if len(operators) != 0:
            combobox = self.ui.comboBox_operators
            combobox.clear()
            combobox.addItem('')
            i = 1
            for operator in operators:
                text = f'{operator.email}'
                combobox.addItem(text)
                i += 1
            combobox.setCurrentIndex(0)

    def update_projects(self, projects_names: Set[str]):
        if len(projects_names) != 0:
            combobox = self.ui.comboBox_projects
            combobox.clear()
            combobox.addItem('')
            i = 1
            for project_name in projects_names:
                text = f'{project_name}'
                combobox.addItem(text)
                i += 1
            combobox.setCurrentIndex(0)

    def update_table_description(self, info: FuncGetFileDescriptionOutput):
        table = self.ui.tableWidget_description
        labels = info.__annotations__.keys()
        table.setColumnCount(2)
        table.setRowCount(len(labels))
        table.setVerticalHeaderLabels(labels)
        table.setHorizontalHeaderLabels(['Actual', 'Future'])
        i = 0
        for key in labels:
            value = getattr(info, key)

            if key == 'author':
                author_combobox_future = QtWidgets.QComboBox()
                author: Operator = value
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(author.email))
                j = 0
                for operator in self.view_state.operators:
                    author_combobox_future.addItem(operator.email)
                    if operator.email == author.email:
                        author_combobox_future.setCurrentIndex(j)
                    j += 1
                table.setCellWidget(i, 1, author_combobox_future)
            elif key == 'operators':
                operators_combobox_actual = QtWidgets.QComboBox()
                self.operators_list_future = QtWidgets.QListWidget()
                operators_actual = []
                for operator in info.operators:
                    operators_combobox_actual.addItem(operator.email)
                    operators_actual.append(operator.email)
                table.setCellWidget(i, 0, operators_combobox_actual)

                for operator in self.view_state.operators:
                    item = QtWidgets.QListWidgetItem(operator.email)
                    if operator.email in operators_actual:
                        item.setBackground(QtGui.QColor('green'))
                        self.view_state.operators_future.append(operator)
                    self.operators_list_future.addItem(item)
                self.operators_list_future.setMinimumHeight(70)
                self.operators_list_future.setMinimumWidth(150)
                table.setCellWidget(i, 1, self.operators_list_future)
                self.operators_list_future.itemClicked.connect(self.operators_list_desc)
            else:
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(value)))

            i += 1
        table.resizeColumnsToContents()

    def operators_list_desc(self, item: QtWidgets.QListWidgetItem):
        search_index = self.view_state.operators_future_search(item.text())
        if search_index != -1:
            item.setBackground(QtGui.QColor('white'))
            self.view_state.operators_future_remove_by_index(search_index)
        else:
            search_index = self.view_state.operators_search(item.text())
            if search_index != -1:
                item.setBackground(QtGui.QColor('green'))
                self.view_state.operators_future_add_by_index(search_index)
            else:
                self.logger.error('Index of operator is not found in Operators')


