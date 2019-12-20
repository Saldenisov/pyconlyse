# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_stpmtr_axis.ui'
#
# Created by: PyQt5 UI code generator 5.13.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_widget_stpmtr(object):

    Form = None

    def setupUi(self, Form, axis_number=1):
        Ui_widget_stpmtr.Form = Form
        Form.setObjectName("Form")
        Form.resize(725, 463)
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.mainVL = QtWidgets.QVBoxLayout()
        self.mainVL.setObjectName("mainVL")

        for axis in range(axis_number):
            self.setupAxis(axis)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def setupAxis(self, axis_n=1):
        self.axisVL0 = QtWidgets.QVBoxLayout()
        self.axisVL0.setContentsMargins(5, 5, 5, 5)
        self.axisVL0.setObjectName("axisVL0")
        self.axisHL0 = QtWidgets.QHBoxLayout()
        self.axisHL0.setObjectName("axisHL0")
        self.radioButton_axis = QtWidgets.QRadioButton(Ui_widget_stpmtr.Form)
        self.radioButton_axis.setObjectName("radioButton_axis")
        self.axisHL0.addWidget(self.radioButton_axis)
        self.line_v1 = QtWidgets.QFrame(Ui_widget_stpmtr.Form)
        self.line_v1.setFrameShape(QtWidgets.QFrame.VLine)
        self.line_v1.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_v1.setObjectName("line_v1")
        self.axisHL0.addWidget(self.line_v1)
        self.axis_valueVL1 = QtWidgets.QVBoxLayout()
        self.axis_valueVL1.setObjectName("axis_valueVL1")
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.axis_valueVL1.addItem(spacerItem)
        self.label_dimension = QtWidgets.QLabel(Ui_widget_stpmtr.Form)
        self.label_dimension.setAlignment(QtCore.Qt.AlignCenter)
        self.label_dimension.setObjectName("label_dimension")
        self.axis_valueVL1.addWidget(self.label_dimension)
        self.lineEdit_value = QtWidgets.QLineEdit(Ui_widget_stpmtr.Form)
        self.lineEdit_value.setObjectName("lineEdit_value")
        self.axis_valueVL1.addWidget(self.lineEdit_value)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.axis_valueVL1.addItem(spacerItem1)
        self.axisHL0.addLayout(self.axis_valueVL1)
        self.line_v2 = QtWidgets.QFrame(Ui_widget_stpmtr.Form)
        self.line_v2.setFrameShape(QtWidgets.QFrame.VLine)
        self.line_v2.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_v2.setObjectName("line_v2")
        self.axisHL0.addWidget(self.line_v2)
        self.axis_controlsVL2 = QtWidgets.QVBoxLayout()
        self.axis_controlsVL2.setObjectName("axis_controlsVL2")
        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.axis_controlsVL2.addItem(spacerItem2)
        self.axis_movement_typeHL3 = QtWidgets.QHBoxLayout()
        self.axis_movement_typeHL3.setObjectName("axis_movement_typeHL3")
        self.radioButton_relative = QtWidgets.QRadioButton(Ui_widget_stpmtr.Form)
        self.radioButton_relative.setObjectName("radioButton_relative")
        self.axis_movement_typeHL3.addWidget(self.radioButton_relative)
        self.radioButton_absolute = QtWidgets.QRadioButton(Ui_widget_stpmtr.Form)
        self.radioButton_absolute.setChecked(True)
        self.radioButton_absolute.setObjectName("radioButton_absolute")
        self.axis_movement_typeHL3.addWidget(self.radioButton_absolute)
        self.checkBox_On = QtWidgets.QCheckBox(Ui_widget_stpmtr.Form)
        self.checkBox_On.setChecked(False)
        self.checkBox_On.setObjectName("checkBox_On")
        self.axis_movement_typeHL3.addWidget(self.checkBox_On)
        spacerItem3 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axis_movement_typeHL3.addItem(spacerItem3)
        self.axis_controlsVL2.addLayout(self.axis_movement_typeHL3)
        self.axis_moveHL3 = QtWidgets.QHBoxLayout()
        self.axis_moveHL3.setObjectName("axis_moveHL3")
        self.lcdNumber_position = QtWidgets.QLCDNumber(Ui_widget_stpmtr.Form)
        self.lcdNumber_position.setObjectName("lcdNumber_position")
        self.axis_moveHL3.addWidget(self.lcdNumber_position)
        self.label_ranges = QtWidgets.QLabel(Ui_widget_stpmtr.Form)
        self.label_ranges.setObjectName("label_ranges")
        self.axis_moveHL3.addWidget(self.label_ranges)
        self.pushButton_move = QtWidgets.QPushButton(Ui_widget_stpmtr.Form)
        self.pushButton_move.setObjectName("pushButton_move")
        self.axis_moveHL3.addWidget(self.pushButton_move)
        self.pushButton_stop = QtWidgets.QPushButton(Ui_widget_stpmtr.Form)
        self.pushButton_stop.setObjectName("pushButton_stop")
        self.axis_moveHL3.addWidget(self.pushButton_stop)
        spacerItem4 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axis_moveHL3.addItem(spacerItem4)
        self.axis_controlsVL2.addLayout(self.axis_moveHL3)
        self.progressBar_movement = QtWidgets.QProgressBar(Ui_widget_stpmtr.Form)
        self.progressBar_movement.setProperty("value", 0)
        self.progressBar_movement.setObjectName("progressBar_movement")
        self.axis_controlsVL2.addWidget(self.progressBar_movement)
        spacerItem5 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.axis_controlsVL2.addItem(spacerItem5)
        self.axisHL0.addLayout(self.axis_controlsVL2)
        spacerItem6 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axisHL0.addItem(spacerItem6)
        self.axisVL0.addLayout(self.axisHL0)
        self.line_bottom = QtWidgets.QFrame(Ui_widget_stpmtr.Form)
        self.line_bottom.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_bottom.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_bottom.setObjectName("line_bottom")
        self.axisVL0.addWidget(self.line_bottom)
        self.mainVL.addLayout(self.axisVL0)
        spacerItem7 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.mainVL.addItem(spacerItem7)
        self.verticalLayout_4.addLayout(self.mainVL)

        _translate = QtCore.QCoreApplication.translate
        self.radioButton_axis.setText(_translate("Form", "I"))
        self.label_dimension.setText(_translate("Form", "mm"))
        self.radioButton_relative.setText(_translate("Form", "relative"))
        self.radioButton_absolute.setText(_translate("Form", "absolute"))
        self.checkBox_On.setText(_translate("Form", "On"))
        self.label_ranges.setText(_translate("Form", "ranges"))
        self.pushButton_move.setText(_translate("Form", "MOVE"))
        self.pushButton_stop.setText(_translate("Form", "STOP"))



    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "Form"))

