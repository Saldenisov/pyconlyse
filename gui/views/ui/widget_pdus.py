# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_pdus.ui'
#
# Created by: PyQt5 UI code generator 5.14.2
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_PDUs(object):
    def setupUi(self, PDUs):
        PDUs.setObjectName("PDUs")
        PDUs.resize(396, 178)
        self.NetioPDU = QtWidgets.QWidget(PDUs)
        self.NetioPDU.setObjectName("NetioPDU")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.NetioPDU)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.checkBox_power = QtWidgets.QCheckBox(self.NetioPDU)
        self.checkBox_power.setObjectName("checkBox_power")
        self.horizontalLayout_2.addWidget(self.checkBox_power)
        self.checkBox_activate = QtWidgets.QCheckBox(self.NetioPDU)
        self.checkBox_activate.setObjectName("checkBox_activate")
        self.horizontalLayout_2.addWidget(self.checkBox_activate)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout_pdu_outputs = QtWidgets.QHBoxLayout()
        self.horizontalLayout_pdu_outputs.setObjectName("horizontalLayout_pdu_outputs")
        self.verticalLayout.addLayout(self.horizontalLayout_pdu_outputs)
        PDUs.setCentralWidget(self.NetioPDU)
        self.menubar = QtWidgets.QMenuBar(PDUs)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 396, 21))
        self.menubar.setObjectName("menubar")
        PDUs.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(PDUs)
        self.statusbar.setObjectName("statusbar")
        PDUs.setStatusBar(self.statusbar)

        self.retranslateUi(PDUs)
        QtCore.QMetaObject.connectSlotsByName(PDUs)

    def retranslateUi(self, PDUs):
        _translate = QtCore.QCoreApplication.translate
        PDUs.setWindowTitle(_translate("PDUs", "PDUs controller"))
        self.checkBox_power.setText(_translate("PDUs", "Power"))
        self.checkBox_activate.setText(_translate("PDUs", "Activate"))
