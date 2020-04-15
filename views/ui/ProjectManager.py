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
        ProjectManager.resize(787, 644)
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
        self.treeWidget.setObjectName("treeWidget")
        self.treeWidget.headerItem().setText(0, "1")
        self.horizontalLayout.addWidget(self.treeWidget)
        self.verticalLayout_files_action = QtWidgets.QVBoxLayout()
        self.verticalLayout_files_action.setContentsMargins(10, 20, 10, -1)
        self.verticalLayout_files_action.setObjectName("verticalLayout_files_action")
        self.groupBox_actions = QtWidgets.QGroupBox(self.groupBox_files)
        self.groupBox_actions.setObjectName("groupBox_actions")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.groupBox_actions)
        self.verticalLayout.setObjectName("verticalLayout")
        self.pushButton_open = QtWidgets.QPushButton(self.groupBox_actions)
        self.pushButton_open.setObjectName("pushButton_open")
        self.verticalLayout.addWidget(self.pushButton_open)
        self.pushButton_create_project = QtWidgets.QPushButton(self.groupBox_actions)
        self.pushButton_create_project.setObjectName("pushButton_create_project")
        self.verticalLayout.addWidget(self.pushButton_create_project)
        self.pushButton_rename = QtWidgets.QPushButton(self.groupBox_actions)
        self.pushButton_rename.setObjectName("pushButton_rename")
        self.verticalLayout.addWidget(self.pushButton_rename)
        self.pushButton = QtWidgets.QPushButton(self.groupBox_actions)
        self.pushButton.setObjectName("pushButton")
        self.verticalLayout.addWidget(self.pushButton)
        self.pushButton_delete = QtWidgets.QPushButton(self.groupBox_actions)
        self.pushButton_delete.setObjectName("pushButton_delete")
        self.verticalLayout.addWidget(self.pushButton_delete)
        self.verticalLayout_files_action.addWidget(self.groupBox_actions)
        self.groupBox_retreive = QtWidgets.QGroupBox(self.groupBox_files)
        self.groupBox_retreive.setObjectName("groupBox_retreive")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.groupBox_retreive)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.pushButton_get_projects = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_get_projects.setObjectName("pushButton_get_projects")
        self.verticalLayout_3.addWidget(self.pushButton_get_projects)
        self.comboBox_projects = QtWidgets.QComboBox(self.groupBox_retreive)
        self.comboBox_projects.setObjectName("comboBox_projects")
        self.verticalLayout_3.addWidget(self.comboBox_projects)
        self.pushButton_get_files = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_get_files.setObjectName("pushButton_get_files")
        self.verticalLayout_3.addWidget(self.pushButton_get_files)
        self.label_files_number = QtWidgets.QLabel(self.groupBox_retreive)
        self.label_files_number.setObjectName("label_files_number")
        self.verticalLayout_3.addWidget(self.label_files_number)
        self.pushButton_get_users = QtWidgets.QPushButton(self.groupBox_retreive)
        self.pushButton_get_users.setObjectName("pushButton_get_users")
        self.verticalLayout_3.addWidget(self.pushButton_get_users)
        self.comboBox_users = QtWidgets.QComboBox(self.groupBox_retreive)
        self.comboBox_users.setMinimumSize(QtCore.QSize(200, 0))
        self.comboBox_users.setObjectName("comboBox_users")
        self.comboBox_users.addItem("")
        self.comboBox_users.setItemText(0, "")
        self.verticalLayout_3.addWidget(self.comboBox_users)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_3.addItem(spacerItem)
        self.verticalLayout_files_action.addWidget(self.groupBox_retreive)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_files_action.addItem(spacerItem1)
        self.horizontalLayout.addLayout(self.verticalLayout_files_action)
        self.groupBox_description = QtWidgets.QGroupBox(self.groupBox_files)
        self.groupBox_description.setObjectName("groupBox_description")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox_description)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.tableWidget_description = QtWidgets.QTableWidget(self.groupBox_description)
        self.tableWidget_description.setObjectName("tableWidget_description")
        self.tableWidget_description.setColumnCount(0)
        self.tableWidget_description.setRowCount(0)
        self.verticalLayout_2.addWidget(self.tableWidget_description)
        self.label_search = QtWidgets.QLabel(self.groupBox_description)
        self.label_search.setObjectName("label_search")
        self.verticalLayout_2.addWidget(self.label_search)
        self.lineEdit_search = QtWidgets.QLineEdit(self.groupBox_description)
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
        self.menubar.setGeometry(QtCore.QRect(0, 0, 787, 21))
        self.menubar.setObjectName("menubar")
        ProjectManager.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(ProjectManager)
        self.statusbar.setObjectName("statusbar")
        ProjectManager.setStatusBar(self.statusbar)

        self.retranslateUi(ProjectManager)
        QtCore.QMetaObject.connectSlotsByName(ProjectManager)

    def retranslateUi(self, ProjectManager):
        _translate = QtCore.QCoreApplication.translate
        ProjectManager.setWindowTitle(_translate("ProjectManager", "Project Manager"))
        self.groupBox_files.setTitle(_translate("ProjectManager", "File tree"))
        self.groupBox_actions.setTitle(_translate("ProjectManager", "Actions"))
        self.pushButton_open.setText(_translate("ProjectManager", "Open"))
        self.pushButton_create_project.setText(_translate("ProjectManager", "Create New"))
        self.pushButton_rename.setText(_translate("ProjectManager", "Rename"))
        self.pushButton.setText(_translate("ProjectManager", "Update"))
        self.pushButton_delete.setText(_translate("ProjectManager", "Delete"))
        self.groupBox_retreive.setTitle(_translate("ProjectManager", "Retrieve"))
        self.pushButton_get_projects.setText(_translate("ProjectManager", "Get Projects"))
        self.pushButton_get_files.setText(_translate("ProjectManager", "Get Files"))
        self.label_files_number.setText(_translate("ProjectManager", "Files: "))
        self.pushButton_get_users.setText(_translate("ProjectManager", "Get Users"))
        self.groupBox_description.setTitle(_translate("ProjectManager", "Description"))
        self.label_search.setText(_translate("ProjectManager", "Search"))

    def fill_file_tree(self, item=None, value={}):


        if not item:
            self.treeWidget.clear()
            item = self.treeWidget.invisibleRootItem()

        def new_item(parent, key, val=None):
            child = QtWidgets.QTreeWidgetItem([key])
            if not isinstance(val, str):
                self.fill_file_tree(child, val)
            parent.addChild(child)
            child.setExpanded(True)
        if not value:
            return
        elif isinstance(value, dict):
            for key, val in sorted(value.items()):
                if key not in ['dirs', 'files']:
                    new_item(item, str(key), val)
                else:
                    self.fill_file_tree(item, val)
        elif isinstance(value, (list, tuple)):
            for val in value:
                text = (str(val) if not isinstance(val, (dict, list, tuple)) else '[%s]' % type(val).__name__)
                new_item(item, text, val)
        else:
            new_item(item, str(value))

    def update_operators(self, operators: List[Operator]):
        if len(operators) != 0:
            self.comboBox_users.clear()
            self.comboBox_users.addItem('')
            i = 1
            for operator in operators:
                text = f'{operator.email}'
                self.comboBox_users.addItem(text)
                i += 1
            self.comboBox_users.setCurrentIndex(0)

    def update_table_description(self, info: Union[FuncGetFileDescirptionOutput, FuncGetProjectDescirptionOutput]):
        table = self.tableWidget_description
        labels = info.__annotations__.keys()
        table.setColumnCount(2)
        table.setRowCount(len(labels))
        table.setVerticalHeaderLabels(labels)
        table.setHorizontalHeaderLabels(['Actual', 'Future'])
        i=0
        for key in labels:
            value = getattr(info, key)
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(value)))
            i += 1
        table.resizeColumnsToContents()


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
    ui.fill_file_tree(ui.treeWidget.invisibleRootItem(), value)
    form.show()
    sys.exit(app.exec_())