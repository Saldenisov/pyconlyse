# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'C:\dev\pyconlyse\views\ui\TestObserver.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtWidgets

class Ui_TestObserver(object):
    def setupUi(self, TestObserver):
        TestObserver.setObjectName("TestObserver")
        TestObserver.resize(641, 445)
        self.centralwidget = QtWidgets.QWidget(TestObserver)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_superuser = QtWidgets.QLabel(self.centralwidget)
        self.label_superuser.setObjectName("label_superuser")
        self.verticalLayout.addWidget(self.label_superuser)
        self.plainTextEdit_superuser_recieved = QtWidgets.QPlainTextEdit(self.centralwidget)
        self.plainTextEdit_superuser_recieved.setObjectName("plainTextEdit_superuser_recieved")
        self.verticalLayout.addWidget(self.plainTextEdit_superuser_recieved)
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.plainTextEdit_superuser_sent = QtWidgets.QTextEdit(self.centralwidget)
        self.plainTextEdit_superuser_sent.setObjectName("plainTextEdit_superuser_sent")
        self.verticalLayout.addWidget(self.plainTextEdit_superuser_sent)
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setObjectName("label_4")
        self.verticalLayout.addWidget(self.label_4)
        self.lineEdit_hb_superuser = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_hb_superuser.setObjectName("lineEdit_hb_superuser")
        self.verticalLayout.addWidget(self.lineEdit_hb_superuser)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_server = QtWidgets.QLabel(self.centralwidget)
        self.label_server.setObjectName("label_server")
        self.verticalLayout_2.addWidget(self.label_server)
        self.plainTextEdit_server_recieved = QtWidgets.QPlainTextEdit(self.centralwidget)
        self.plainTextEdit_server_recieved.setObjectName("plainTextEdit_server_recieved")
        self.verticalLayout_2.addWidget(self.plainTextEdit_server_recieved)
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_2.addWidget(self.label_2)
        self.plainTextEdit_server_sent = QtWidgets.QTextEdit(self.centralwidget)
        self.plainTextEdit_server_sent.setObjectName("plainTextEdit_server_sent")
        self.verticalLayout_2.addWidget(self.plainTextEdit_server_sent)
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setObjectName("label_5")
        self.verticalLayout_2.addWidget(self.label_5)
        self.lineEdit_hb_server = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_hb_server.setObjectName("lineEdit_hb_server")
        self.verticalLayout_2.addWidget(self.lineEdit_hb_server)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label_service = QtWidgets.QLabel(self.centralwidget)
        self.label_service.setObjectName("label_service")
        self.verticalLayout_3.addWidget(self.label_service)
        self.plainTextEdit_service_recieved = QtWidgets.QPlainTextEdit(self.centralwidget)
        self.plainTextEdit_service_recieved.setObjectName("plainTextEdit_service_recieved")
        self.verticalLayout_3.addWidget(self.plainTextEdit_service_recieved)
        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_3.addWidget(self.label_3)
        self.plainTextEdit_service_sent = QtWidgets.QTextEdit(self.centralwidget)
        self.plainTextEdit_service_sent.setObjectName("plainTextEdit_service_sent")
        self.verticalLayout_3.addWidget(self.plainTextEdit_service_sent)
        self.label_6 = QtWidgets.QLabel(self.centralwidget)
        self.label_6.setObjectName("label_6")
        self.verticalLayout_3.addWidget(self.label_6)
        self.lineEdit_hb_service = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_hb_service.setObjectName("lineEdit_hb_service")
        self.verticalLayout_3.addWidget(self.lineEdit_hb_service)
        self.horizontalLayout.addLayout(self.verticalLayout_3)
        self.horizontalLayout_2.addLayout(self.horizontalLayout)
        TestObserver.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(TestObserver)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 641, 21))
        self.menubar.setObjectName("menubar")
        TestObserver.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(TestObserver)
        self.statusbar.setObjectName("statusbar")
        TestObserver.setStatusBar(self.statusbar)

        self.retranslateUi(TestObserver)
        QtCore.QMetaObject.connectSlotsByName(TestObserver)

    def retranslateUi(self, TestObserver):
        _translate = QtCore.QCoreApplication.translate
        TestObserver.setWindowTitle(_translate("TestObserver", "TestObserver"))
        self.label_superuser.setText(_translate("TestObserver", "SuperUser_recieved"))
        self.label.setText(_translate("TestObserver", "Sent"))
        self.label_4.setText(_translate("TestObserver", "Heartbeat"))
        self.label_server.setText(_translate("TestObserver", "Server_recieved"))
        self.label_2.setText(_translate("TestObserver", "Sent"))
        self.label_5.setText(_translate("TestObserver", "Heartbeat"))
        self.label_service.setText(_translate("TestObserver", "Service_recieved"))
        self.label_3.setText(_translate("TestObserver", "Sent"))
        self.label_6.setText(_translate("TestObserver", "Heartbeat"))

