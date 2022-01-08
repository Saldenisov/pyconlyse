# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_daqmx.ui'
#
# Created by: PyQt5 UI code generator 5.15.0
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_DAQmxs(object):
    def setupUi(self, DAQmxs):
        DAQmxs.setObjectName("DAQmxs")
        DAQmxs.resize(396, 178)
        self.NetioPDU = QtWidgets.QWidget(DAQmxs)
        self.NetioPDU.setObjectName("NetioPDU")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.NetioPDU)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.checkBox_power = QtWidgets.QCheckBox(self.NetioPDU)
        self.checkBox_power.setObjectName("checkBox_power")
        self.horizontalLayout_2.addWidget(self.checkBox_power)
        self.checkBox_ctrl_activate = QtWidgets.QCheckBox(self.NetioPDU)
        self.checkBox_ctrl_activate.setObjectName("checkBox_ctrl_activate")
        self.horizontalLayout_2.addWidget(self.checkBox_ctrl_activate)
        self.checkBox_device_activate = QtWidgets.QCheckBox(self.NetioPDU)
        self.checkBox_device_activate.setObjectName("checkBox_device_activate")
        self.horizontalLayout_2.addWidget(self.checkBox_device_activate)
        self.label_device_id = QtWidgets.QLabel(self.NetioPDU)
        self.label_device_id.setObjectName("label_device_id")
        self.horizontalLayout_2.addWidget(self.label_device_id)
        self.spinBox_device_id = QtWidgets.QSpinBox(self.NetioPDU)
        self.spinBox_device_id.setProperty("value", 1)
        self.spinBox_device_id.setObjectName("spinBox_device_id")
        self.horizontalLayout_2.addWidget(self.spinBox_device_id)
        self.label_name = QtWidgets.QLabel(self.NetioPDU)
        self.label_name.setObjectName("label_name")
        self.horizontalLayout_2.addWidget(self.label_name)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.comments = QtWidgets.QTextEdit(self.NetioPDU)
        self.comments.setObjectName("comments")
        self.verticalLayout.addWidget(self.comments)
        self.horizontalLayout_daqmx_channels = QtWidgets.QHBoxLayout()
        self.horizontalLayout_daqmx_channels.setObjectName("horizontalLayout_daqmx_channels")
        self.verticalLayout.addLayout(self.horizontalLayout_daqmx_channels)
        DAQmxs.setCentralWidget(self.NetioPDU)
        self.menubar = QtWidgets.QMenuBar(DAQmxs)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 396, 21))
        self.menubar.setObjectName("menubar")
        DAQmxs.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(DAQmxs)
        self.statusbar.setObjectName("statusbar")
        DAQmxs.setStatusBar(self.statusbar)

        self.retranslateUi(DAQmxs)
        QtCore.QMetaObject.connectSlotsByName(DAQmxs)

    def retranslateUi(self, DAQmxs):
        _translate = QtCore.QCoreApplication.translate
        DAQmxs.setWindowTitle(_translate("DAQmxs", "PDUs controller"))
        self.checkBox_power.setText(_translate("DAQmxs", "Power"))
        self.checkBox_ctrl_activate.setText(_translate("DAQmxs", "Activate"))
        self.checkBox_device_activate.setText(_translate("DAQmxs", "On"))
        self.label_device_id.setText(_translate("DAQmxs", "DAQmx#"))
        self.label_name.setText(_translate("DAQmxs", "TextLabel"))