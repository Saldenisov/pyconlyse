# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'settings_general.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtWidgets

class Ui_settings_general_widget(object):
    def setupUi(self, FormSettings):
        FormSettings.setObjectName("FormSettings")
        FormSettings.setWindowModality(QtCore.Qt.WindowModal)
        FormSettings.resize(446, 628)
        FormSettings.setAcceptDrops(True)
        self.verticalLayout_M = QtWidgets.QVBoxLayout(FormSettings)
        self.verticalLayout_M.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.verticalLayout_M.setObjectName("verticalLayout_M")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.settings_status_label = QtWidgets.QLabel(FormSettings)
        self.settings_status_label.setObjectName("settings_status_label")
        self.verticalLayout.addWidget(self.settings_status_label)
        self.settings_textEdit = QtWidgets.QTextEdit(FormSettings)
        self.settings_textEdit.setAutoFillBackground(False)
        self.settings_textEdit.setInputMethodHints(QtCore.Qt.ImhMultiLine)
        self.settings_textEdit.setFrameShape(QtWidgets.QFrame.WinPanel)
        self.settings_textEdit.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.settings_textEdit.setLineWidth(3)
        self.settings_textEdit.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.settings_textEdit.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.settings_textEdit.setObjectName("settings_textEdit")
        self.verticalLayout.addWidget(self.settings_textEdit)
        self.horizontal_buttons_Layout = QtWidgets.QHBoxLayout()
        self.horizontal_buttons_Layout.setObjectName("horizontal_buttons_Layout")
        self.save_settingsButton = QtWidgets.QPushButton(FormSettings)
        self.save_settingsButton.setObjectName("save_settingsButton")
        self.horizontal_buttons_Layout.addWidget(self.save_settingsButton)
        self.update_settingsButton = QtWidgets.QPushButton(FormSettings)
        self.update_settingsButton.setObjectName("update_settingsButton")
        self.horizontal_buttons_Layout.addWidget(self.update_settingsButton)
        self.verify_settingsButton = QtWidgets.QPushButton(FormSettings)
        self.verify_settingsButton.setObjectName("verify_settingsButton")
        self.horizontal_buttons_Layout.addWidget(self.verify_settingsButton)
        self.verticalLayout.addLayout(self.horizontal_buttons_Layout)
        self.verticalLayout_M.addLayout(self.verticalLayout)

        self.retranslateUi(FormSettings)
        QtCore.QMetaObject.connectSlotsByName(FormSettings)

    def retranslateUi(self, FormSettings):
        _translate = QtCore.QCoreApplication.translate
        FormSettings.setWindowTitle(_translate("FormSettings", "Settings"))
        self.settings_status_label.setText(_translate("FormSettings", "Settings_: status unknown"))
        self.save_settingsButton.setText(_translate("FormSettings", "Save"))
        self.update_settingsButton.setText(_translate("FormSettings", "Update"))
        self.verify_settingsButton.setText(_translate("FormSettings", "Verify"))

