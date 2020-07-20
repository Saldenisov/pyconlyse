# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_stpmtr_axis.ui'
#
# Created by: PyQt5 UI code generator 5.13.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Widget_Stpmtr(object):
    Form = None

    def setupUi(self, Form, axis_number=1):
        Ui_Widget_Stpmtr.Form = Form
        Form.setObjectName("StpMtrWidget")
        Form.resize(410, 125)
        font = QtGui.QFont()
        font.setFamily("Palatino Linotype")
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        Form.setFont(font)
        self.centralwidget = QtWidgets.QWidget(Form)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.axisVL0 = QtWidgets.QVBoxLayout()
        self.axisVL0.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.axisVL0.setContentsMargins(0, 0, 0, 0)
        self.axisVL0.setSpacing(6)
        self.axisVL0.setObjectName("axisVL0")


        for axis in range(axis_number):
            self.setupAxis(axis)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def setupAxis(self, axis_n=1):
        self.axisHL0 = QtWidgets.QHBoxLayout()
        self.axisHL0.setContentsMargins(0, 0, 0, 0)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axisHL0.addItem(spacerItem1)
        self.radioButton_axis = QtWidgets.QRadioButton(Ui_Widget_Stpmtr.Form)
        self.radioButton_axis.setObjectName("radioButton_axis")
        self.axisHL0.addWidget(self.radioButton_axis)
        self.line_v1 = QtWidgets.QFrame(Ui_Widget_Stpmtr.Form)
        self.line_v1.setFrameShape(QtWidgets.QFrame.VLine)
        self.line_v1.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_v1.setObjectName("line_v1")
        self.axisHL0.addWidget(self.line_v1)


        _translate = QtCore.QCoreApplication.translate


    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("StpMtrWidget", "Form"))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QMainWindow()
    ui = Ui_Widget_Stpmtr()
    ui.setupUi(widget)
    widget.show()
    sys.exit(app.exec_())