# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'C:\dev\pyconlyse\views\ui\ProjectManager.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets
from typing import List, Union
from utilities.data.datastructures.mes_independent.projects_dataclass import *


class Ui_ProjectManager(object):
    def setupUi(self, ProjectManager):
        ProjectManager.setObjectName("ProjectManager")
        ProjectManager.resize(984, 667)
        self.centralwidget = QtWidgets.QWidget(ProjectManager)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.horizontalLayout_group = QtWidgets.QHBoxLayout()
        self.horizontalLayout_group.setObjectName("horizontalLayout_group")
        self.groupBox_files = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox_files.setObjectName("groupBox_files")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.groupBox_files)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.treeWidget = QtWidgets.QTreeWidget(self.groupBox_files)
        self.treeWidget.setMinimumSize(QtCore.QSize(350, 0))
        self.treeWidget.setObjectName("treeWidget")
        self.treeWidget.header().setVisible(False)
        self.horizontalLayout.addWidget(self.treeWidget)
        self.verticalLayout_files_action = QtWidgets.QVBoxLayout()
        self.verticalLayout_files_action.setContentsMargins(10, 20, 10, -1)
        self.verticalLayout_files_action.setObjectName("verticalLayout_files_action")
        self.groupBox_retreive = QtWidgets.QGroupBox(self.groupBox_files)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_retreive.sizePolicy().hasHeightForWidth())
        self.groupBox_retreive.setSizePolicy(sizePolicy)
        self.groupBox_retreive.setMaximumSize(QtCore.QSize(300, 16777215))
        self.groupBox_retreive.setObjectName("groupBox_retreive")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.groupBox_retreive)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.verticalLayout_projects = QtWidgets.QVBoxLayout()
        self.verticalLayout_projects.setContentsMargins(-1, 0, -1, 0)
        self.verticalLayout_projects.setObjectName("verticalLayout_projects")
        self.label_projects = QtWidgets.QLabel(self.groupBox_retreive)
        self.label_projects.setObjectName("label_projects")
        self.verticalLayout_projects.addWidget(self.label_projects)
        self.horizontalLayout_projects = QtWidgets.QHBoxLayout()
        self.horizontalLayout_projects.setContentsMargins(-1, 0, -1, 0)
        self.horizontalLayout_projects.setObjectName("horizontalLayout_projects")
        self.gridLayout_projects = QtWidgets.QGridLayout()
        self.gridLayout_projects.setContentsMargins(-1, 10, 10, -1)
        self.gridLayout_projects.setObjectName("gridLayout_projects")
        self.pushButton_remove_project = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_remove_project.setObjectName("pushButton_remove_project")
        self.gridLayout_projects.addWidget(self.pushButton_remove_project, 2, 1, 1, 1)
        self.pushButton_get_projects = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_get_projects.setMinimumSize(QtCore.QSize(120, 0))
        self.pushButton_get_projects.setObjectName("pushButton_get_projects")
        self.gridLayout_projects.addWidget(self.pushButton_get_projects, 0, 0, 1, 1)
        self.pushButton_new_project = QtWidgets.QPushButton(self.groupBox_retreive)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_new_project.sizePolicy().hasHeightForWidth())
        self.pushButton_new_project.setSizePolicy(sizePolicy)
        self.pushButton_new_project.setObjectName("pushButton_new_project")
        self.gridLayout_projects.addWidget(self.pushButton_new_project, 2, 0, 1, 1)
        self.pushButton_add_file_to_project = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_add_file_to_project.setObjectName("pushButton_add_file_to_project")
        self.gridLayout_projects.addWidget(self.pushButton_add_file_to_project, 0, 1, 1, 1)
        self.horizontalLayout_projects.addLayout(self.gridLayout_projects)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_projects.addItem(spacerItem)
        self.verticalLayout_projects.addLayout(self.horizontalLayout_projects)
        self.comboBox_projects = QtWidgets.QComboBox(self.groupBox_retreive)
        self.comboBox_projects.setObjectName("comboBox_projects")
        self.verticalLayout_projects.addWidget(self.comboBox_projects)
        self.verticalLayout_3.addLayout(self.verticalLayout_projects)
        self.line = QtWidgets.QFrame(self.groupBox_retreive)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout_3.addWidget(self.line)
        self.verticalLayout_files = QtWidgets.QVBoxLayout()
        self.verticalLayout_files.setContentsMargins(-1, 0, -1, 0)
        self.verticalLayout_files.setObjectName("verticalLayout_files")
        self.label_files = QtWidgets.QLabel(self.groupBox_retreive)
        self.label_files.setObjectName("label_files")
        self.verticalLayout_files.addWidget(self.label_files)
        self.horizontalLayout_files = QtWidgets.QHBoxLayout()
        self.horizontalLayout_files.setContentsMargins(-1, 0, -1, 0)
        self.horizontalLayout_files.setObjectName("horizontalLayout_files")
        self.pushButton_get_files = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_get_files.setObjectName("pushButton_get_files")
        self.horizontalLayout_files.addWidget(self.pushButton_get_files)
        self.pushButton_remove_file = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_remove_file.setObjectName("pushButton_remove_file")
        self.horizontalLayout_files.addWidget(self.pushButton_remove_file)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_files.addItem(spacerItem1)
        self.verticalLayout_files.addLayout(self.horizontalLayout_files)
        self.verticalLayout_3.addLayout(self.verticalLayout_files)
        self.line_2 = QtWidgets.QFrame(self.groupBox_retreive)
        self.line_2.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_2.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_2.setObjectName("line_2")
        self.verticalLayout_3.addWidget(self.line_2)
        self.verticalLayout_operators = QtWidgets.QVBoxLayout()
        self.verticalLayout_operators.setContentsMargins(-1, 0, -1, 0)
        self.verticalLayout_operators.setObjectName("verticalLayout_operators")
        self.label_operators = QtWidgets.QLabel(self.groupBox_retreive)
        self.label_operators.setObjectName("label_operators")
        self.verticalLayout_operators.addWidget(self.label_operators)
        self.horizontalLayout_operators = QtWidgets.QHBoxLayout()
        self.horizontalLayout_operators.setContentsMargins(-1, 0, 0, 0)
        self.horizontalLayout_operators.setObjectName("horizontalLayout_operators")
        self.gridLayout_operators = QtWidgets.QGridLayout()
        self.gridLayout_operators.setContentsMargins(-1, 0, 0, -1)
        self.gridLayout_operators.setObjectName("gridLayout_operators")
        self.pushButton_get_operators = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_get_operators.setMinimumSize(QtCore.QSize(120, 0))
        self.pushButton_get_operators.setObjectName("pushButton_get_operators")
        self.gridLayout_operators.addWidget(self.pushButton_get_operators, 0, 0, 1, 1)
        self.pushButton_add_operator = QtWidgets.QPushButton(self.groupBox_retreive)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_add_operator.sizePolicy().hasHeightForWidth())
        self.pushButton_add_operator.setSizePolicy(sizePolicy)
        self.pushButton_add_operator.setMinimumSize(QtCore.QSize(0, 0))
        self.pushButton_add_operator.setObjectName("pushButton_add_operator")
        self.gridLayout_operators.addWidget(self.pushButton_add_operator, 0, 1, 1, 1)
        self.pushButton_remove_operator = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_remove_operator.setObjectName("pushButton_remove_operator")
        self.gridLayout_operators.addWidget(self.pushButton_remove_operator, 1, 1, 1, 1)
        self.pushButton_update_operator = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_update_operator.setObjectName("pushButton_update_operator")
        self.gridLayout_operators.addWidget(self.pushButton_update_operator, 1, 0, 1, 1)
        self.horizontalLayout_operators.addLayout(self.gridLayout_operators)
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_operators.addItem(spacerItem2)
        self.verticalLayout_operators.addLayout(self.horizontalLayout_operators)
        self.comboBox_operators = QtWidgets.QComboBox(self.groupBox_retreive)
        self.comboBox_operators.setMinimumSize(QtCore.QSize(200, 0))
        self.comboBox_operators.setObjectName("comboBox_operators")
        self.comboBox_operators.addItem("")
        self.comboBox_operators.setItemText(0, "")
        self.verticalLayout_operators.addWidget(self.comboBox_operators)
        self.verticalLayout_3.addLayout(self.verticalLayout_operators)
        self.verticalLayout_files_action.addWidget(self.groupBox_retreive)
        spacerItem3 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_files_action.addItem(spacerItem3)
        self.horizontalLayout.addLayout(self.verticalLayout_files_action)
        self.groupBox_description = QtWidgets.QGroupBox(self.groupBox_files)
        self.groupBox_description.setObjectName("groupBox_description")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox_description)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.tableWidget_description = QtWidgets.QTableWidget(self.groupBox_description)
        self.tableWidget_description.setMinimumSize(QtCore.QSize(300, 0))
        self.tableWidget_description.setObjectName("tableWidget_description")
        self.tableWidget_description.setColumnCount(0)
        self.tableWidget_description.setRowCount(0)
        self.verticalLayout_2.addWidget(self.tableWidget_description)
        self.label_search = QtWidgets.QLabel(self.groupBox_description)
        self.label_search.setObjectName("label_search")
        self.verticalLayout_2.addWidget(self.label_search)
        self.lineEdit_search = QtWidgets.QLineEdit(self.groupBox_description)
        self.lineEdit_search.setEnabled(False)
        self.lineEdit_search.setObjectName("lineEdit_search")
        self.verticalLayout_2.addWidget(self.lineEdit_search)
        self.horizontalLayout.addWidget(self.groupBox_description)
        self.horizontalLayout_group.addWidget(self.groupBox_files)
        self.verticalLayout_4.addLayout(self.horizontalLayout_group)
        self.comments = QtWidgets.QTextEdit(self.centralwidget)
        self.comments.setMaximumSize(QtCore.QSize(16777215, 50))
        self.comments.setObjectName("comments")
        self.verticalLayout_4.addWidget(self.comments)
        ProjectManager.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(ProjectManager)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 984, 21))
        self.menubar.setObjectName("menubar")
        self.menuGeneral = QtWidgets.QMenu(self.menubar)
        self.menuGeneral.setObjectName("menuGeneral")
        ProjectManager.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(ProjectManager)
        self.statusbar.setObjectName("statusbar")
        ProjectManager.setStatusBar(self.statusbar)
        self.actionNew_Project = QtWidgets.QAction(ProjectManager)
        self.actionNew_Project.setObjectName("actionNew_Project")
        self.actionQuit = QtWidgets.QAction(ProjectManager)
        self.actionQuit.setObjectName("actionQuit")
        self.menuGeneral.addAction(self.actionNew_Project)
        self.menuGeneral.addSeparator()
        self.menuGeneral.addAction(self.actionQuit)
        self.menubar.addAction(self.menuGeneral.menuAction())

        self.retranslateUi(ProjectManager)
        QtCore.QMetaObject.connectSlotsByName(ProjectManager)

    def retranslateUi(self, ProjectManager):
        _translate = QtCore.QCoreApplication.translate
        ProjectManager.setWindowTitle(_translate("ProjectManager", "Project Manager"))
        self.groupBox_files.setTitle(_translate("ProjectManager", "File tree"))
        self.groupBox_retreive.setTitle(_translate("ProjectManager", "Actions"))
        self.label_projects.setText(_translate("ProjectManager", "Projects: "))
        self.pushButton_remove_project.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Remove File from Selected Project</span></p></body></html>"))
        self.pushButton_remove_project.setText(_translate("ProjectManager", "-"))
        self.pushButton_get_projects.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Retreive Projects</span></p></body></html>"))
        self.pushButton_get_projects.setText(_translate("ProjectManager", "Get Projects"))
        self.pushButton_new_project.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Create New Project</span></p></body></html>"))
        self.pushButton_new_project.setText(_translate("ProjectManager", "New"))
        self.pushButton_add_file_to_project.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Add File to Selected Project</span></p></body></html>"))
        self.pushButton_add_file_to_project.setText(_translate("ProjectManager", "+"))
        self.comboBox_projects.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Projects</span></p></body></html>"))
        self.label_files.setText(_translate("ProjectManager", "Files: "))
        self.pushButton_get_files.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Retreive Files</span></p></body></html>"))
        self.pushButton_get_files.setText(_translate("ProjectManager", "Get Files"))
        self.pushButton_remove_file.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Remove File/Files from DB</span></p></body></html>"))
        self.pushButton_remove_file.setText(_translate("ProjectManager", "-"))
        self.label_operators.setText(_translate("ProjectManager", "Operators:"))
        self.pushButton_get_operators.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Retreive Operators</span></p></body></html>"))
        self.pushButton_get_operators.setText(_translate("ProjectManager", "Get Operators"))
        self.pushButton_add_operator.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Create New Operator</span></p></body></html>"))
        self.pushButton_add_operator.setText(_translate("ProjectManager", "+"))
        self.pushButton_remove_operator.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Remove Operator from DB</span></p></body></html>"))
        self.pushButton_remove_operator.setText(_translate("ProjectManager", "-"))
        self.pushButton_update_operator.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Update Operator info</span></p></body></html>"))
        self.pushButton_update_operator.setText(_translate("ProjectManager", "Update"))
        self.comboBox_operators.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">Operators</span></p></body></html>"))
        self.groupBox_description.setTitle(_translate("ProjectManager", "Description"))
        self.tableWidget_description.setToolTip(_translate("ProjectManager", "<html><head/><body><p>Description of file/project</p></body></html>"))
        self.label_search.setText(_translate("ProjectManager", "Search"))
        self.lineEdit_search.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">SQL search query</span></p></body></html>"))
        self.comments.setToolTip(_translate("ProjectManager", "<html><head/><body><p><span style=\" font-weight:600;\">comments</span></p></body></html>"))
        self.menuGeneral.setTitle(_translate("ProjectManager", "General"))
        self.actionNew_Project.setText(_translate("ProjectManager", "New Project"))
        self.actionQuit.setText(_translate("ProjectManager", "Quit"))

    def update_file_tree(self, item=None, value={}):
        if not item:
            self.treeWidget.clear()
            item = self.treeWidget.invisibleRootItem()

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
            combobox = self.comboBox_operators
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
            combobox = self.comboBox_projects
            combobox.clear()
            combobox.addItem('')
            i = 1
            for project_name in projects_names:
                text = f'{project_name}'
                combobox.addItem(text)
                i += 1
            combobox.setCurrentIndex(0)

    def update_table_description(self, info: Union[FuncGetFileDescirptionOutput, FuncGetProjectDescirptionOutput]):
        table = self.tableWidget_description
        labels = info.__annotations__.keys()
        table.setColumnCount(2)
        table.setRowCount(len(labels))
        table.setVerticalHeaderLabels(labels)
        table.setHorizontalHeaderLabels(['Actual', 'Future'])
        i = 0
        for key in labels:
            value = getattr(info, key)
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(value)))
            if key == 'author':
                author_combobox = QtWidgets.QComboBox()
                table.setCellWidget(i, 1, author_combobox)
            elif key == 'project_name':
                projects_combobox = QtWidgets.QComboBox()
                table.setCellWidget(i, 1, projects_combobox)
            i += 1
        table.resizeColumnsToContents()

from typing import List, Union
from utilities.data.datastructures.mes_independent.projects_dataclass import *
if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    form = QtWidgets.QMainWindow()
    ui = Ui_ProjectManager()
    ui.setupUi(form)
    value = {'dirs':
              {'C:\\':
                   {'dirs':
                        {'dev': {'dirs': {},
                                 'files': ['service.py']}},
                    'files': []}},
          'files': []}
    value2 = {'dirs':
              {'dev':
                   {'dirs':
                        {'DATA': {'dirs': {},
                                 'files': ['service.py']}},
                    'files': []}},
          'files': []}
    ui.update_file_tree(ui.treeWidget.invisibleRootItem(), value2)
    form.show()
    sys.exit(app.exec_())