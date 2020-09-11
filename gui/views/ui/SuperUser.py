# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'SuperUser.ui'
#
# Created by: PyQt5 UI code generator 5.15.0
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_SuperUser(object):
    def setupUi(self, SuperUser):
        SuperUser.setObjectName("SuperUser")
        SuperUser.resize(828, 630)
        font = QtGui.QFont()
        font.setFamily("Palatino Linotype")
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        SuperUser.setFont(font)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("../../icons/client_cut.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        SuperUser.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(SuperUser)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.DevicesLayout = QtWidgets.QHBoxLayout()
        self.DevicesLayout.setContentsMargins(10, 10, 10, 10)
        self.DevicesLayout.setObjectName("DevicesLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)
        self.verticalLayout.setObjectName("verticalLayout")
        self.lW_devices = QtWidgets.QListWidget(self.centralwidget)
        self.lW_devices.setObjectName("lW_devices")
        self.verticalLayout.addWidget(self.lW_devices)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(-1, 10, -1, 10)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.pB_checkServices = QtWidgets.QPushButton(self.centralwidget)
        self.pB_checkServices.setObjectName("pB_checkServices")
        self.horizontalLayout.addWidget(self.pB_checkServices)
        self.radioButton_hB = QtWidgets.QRadioButton(self.centralwidget)
        self.radioButton_hB.setText("")
        self.radioButton_hB.setObjectName("radioButton_hB")
        self.horizontalLayout.addWidget(self.radioButton_hB)
        self.radioButton_hB2 = QtWidgets.QRadioButton(self.centralwidget)
        self.radioButton_hB2.setText("")
        self.radioButton_hB2.setObjectName("radioButton_hB2")
        self.horizontalLayout.addWidget(self.radioButton_hB2)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.DevicesLayout.addLayout(self.verticalLayout)
        self.InfoLayout = QtWidgets.QVBoxLayout()
        self.InfoLayout.setContentsMargins(-1, 10, -1, 10)
        self.InfoLayout.setObjectName("InfoLayout")
        self.pB_connection = QtWidgets.QPushButton(self.centralwidget)
        self.pB_connection.setObjectName("pB_connection")
        self.InfoLayout.addWidget(self.pB_connection)
        self.chooseLayout = QtWidgets.QHBoxLayout()
        self.chooseLayout.setSizeConstraint(QtWidgets.QLayout.SetMaximumSize)
        self.chooseLayout.setContentsMargins(-1, -1, -1, 0)
        self.chooseLayout.setObjectName("chooseLayout")
        self.rB_window = QtWidgets.QRadioButton(self.centralwidget)
        self.rB_window.setObjectName("rB_window")
        self.chooseLayout.addWidget(self.rB_window)
        self.rB_local = QtWidgets.QRadioButton(self.centralwidget)
        self.rB_local.setObjectName("rB_local")
        self.chooseLayout.addWidget(self.rB_local)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.chooseLayout.addItem(spacerItem1)
        self.InfoLayout.addLayout(self.chooseLayout)
        self.tE_info = QtWidgets.QTextEdit(self.centralwidget)
        self.tE_info.setObjectName("tE_info")
        self.InfoLayout.addWidget(self.tE_info)
        self.DevicesLayout.addLayout(self.InfoLayout)
        self.verticalLayout_2.addLayout(self.DevicesLayout)
        self.executionLayout = QtWidgets.QHBoxLayout()
        self.executionLayout.setContentsMargins(-1, 2, -1, 2)
        self.executionLayout.setObjectName("executionLayout")
        self.lineEdit_msg = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_msg.setObjectName("lineEdit_msg")
        self.executionLayout.addWidget(self.lineEdit_msg)
        self.verticalLayout_2.addLayout(self.executionLayout)
        SuperUser.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(SuperUser)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 828, 21))
        self.menubar.setObjectName("menubar")
        self.menuMain = QtWidgets.QMenu(self.menubar)
        self.menuMain.setObjectName("menuMain")
        SuperUser.setMenuBar(self.menubar)
        self.actionSettings = QtWidgets.QAction(SuperUser)
        self.actionSettings.setObjectName("actionSettings")
        self.actionQuit = QtWidgets.QAction(SuperUser)
        self.actionQuit.setObjectName("actionQuit")
        self.menuMain.addAction(self.actionSettings)
        self.menuMain.addAction(self.actionQuit)
        self.menubar.addAction(self.menuMain.menuAction())

        self.retranslateUi(SuperUser)
        QtCore.QMetaObject.connectSlotsByName(SuperUser)

    def retranslateUi(self, SuperUser):
        _translate = QtCore.QCoreApplication.translate
        SuperUser.setWindowTitle(_translate("SuperUser", "SuperUser"))
        self.pB_checkServices.setText(_translate("SuperUser", "Check Services"))
        self.pB_connection.setText(_translate("SuperUser", "Create Connection"))
        self.rB_window.setText(_translate("SuperUser", "Window"))
        self.rB_local.setText(_translate("SuperUser", "Terminal"))
        self.menuMain.setTitle(_translate("SuperUser", "Main"))
        self.actionSettings.setText(_translate("SuperUser", "Settings"))
        self.actionQuit.setText(_translate("SuperUser", "Quit"))
