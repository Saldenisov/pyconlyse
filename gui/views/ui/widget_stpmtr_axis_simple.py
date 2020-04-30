# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_stpmtr_axis_simple.ui'
#
# Created by: PyQt5 UI code generator 5.13.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Dict, Union
from utilities.data.messaging import ServiceInfoMes
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import AxisStpMtr, StpMtrCtrlStatusMultiAxes
import logging


module_logger = logging.getLogger(__name__)


class Ui_StpMtrGUI(object):

    def setupUi(self, StpMtrGUI, parameters: ServiceInfoMes):
        self.parameters: ServiceInfoMes = parameters
        StpMtrGUI.setObjectName("StpMtrGUI")
        StpMtrGUI.resize(431, 119)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(StpMtrGUI.sizePolicy().hasHeightForWidth())
        StpMtrGUI.setSizePolicy(sizePolicy)
        self.centralwidget = QtWidgets.QWidget(StpMtrGUI)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.axis_movement_typeHL = QtWidgets.QHBoxLayout()
        self.axis_movement_typeHL.setObjectName("axis_movement_typeHL")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.axis_movement_typeHL.addWidget(self.label)
        self.spinBox_axis = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_axis.setObjectName("spinBox")
        try:
            ids = self.parameters.device_description.axes.keys()
            self.spinBox_axis.setMinimum(min(ids))
            self.spinBox_axis.setMaximum(max(ids))
        except KeyError:
            self.spinBox_axis.setMinimum(1)
            self.spinBox_axis.setMaximum(2)
        self.axis_movement_typeHL.addWidget(self.spinBox_axis)
        self.radioButton_relative = QtWidgets.QRadioButton(self.centralwidget)
        self.radioButton_relative.setObjectName("radioButton_relative")
        self.axis_movement_typeHL.addWidget(self.radioButton_relative)
        self.radioButton_absolute = QtWidgets.QRadioButton(self.centralwidget)
        self.radioButton_absolute.setChecked(True)
        self.radioButton_absolute.setObjectName("radioButton_absolute")
        self.axis_movement_typeHL.addWidget(self.radioButton_absolute)
        self.checkBox_On = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_On.setChecked(False)
        self.checkBox_On.setObjectName("checkBox_On")
        self.axis_movement_typeHL.addWidget(self.checkBox_On)
        self.label_name = QtWidgets.QLabel(self.centralwidget)
        self.label_name.setObjectName("label_name")
        self.axis_movement_typeHL.addWidget(self.label_name)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axis_movement_typeHL.addItem(spacerItem)
        self.verticalLayout.addLayout(self.axis_movement_typeHL)
        self.axis_moveHL = QtWidgets.QHBoxLayout()
        self.axis_moveHL.setObjectName("axis_moveHL")
        self.lcdNumber_position = QtWidgets.QLCDNumber(self.centralwidget)
        self.lcdNumber_position.setObjectName("lcdNumber_position")
        self.axis_moveHL.addWidget(self.lcdNumber_position)
        self.label_ranges = QtWidgets.QLabel(self.centralwidget)
        self.label_ranges.setObjectName("label_ranges")
        self.axis_moveHL.addWidget(self.label_ranges)
        self.lineEdit_value = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_value.setObjectName("lineEdit_value")
        self.axis_moveHL.addWidget(self.lineEdit_value)
        self.pushButton_move = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_move.setObjectName("pushButton_move")
        self.axis_moveHL.addWidget(self.pushButton_move)
        self.pushButton_stop = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_stop.setObjectName("pushButton_stop")
        self.axis_moveHL.addWidget(self.pushButton_stop)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axis_moveHL.addItem(spacerItem1)
        self.verticalLayout.addLayout(self.axis_moveHL)
        self.label_preset = QtWidgets.QLabel(self.centralwidget)
        self.label_preset.setObjectName("label_preset")
        self.verticalLayout.addWidget(self.label_preset)
        self.progressBar_movement = QtWidgets.QProgressBar(self.centralwidget)
        self.progressBar_movement.setProperty("value", 0)
        self.progressBar_movement.setObjectName("progressBar_movement")
        self.verticalLayout.addWidget(self.progressBar_movement)
        self.comments = QtWidgets.QTextEdit(self.centralwidget)
        self.verticalLayout.addWidget(self.comments)
        self.checkBox_activate = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_activate.setObjectName("checkBox_activate")
        self.verticalLayout.addWidget(self.checkBox_activate)
        self.checkBox_power = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_power.setObjectName("checkBox_power")
        self.verticalLayout.addWidget(self.checkBox_power)


        StpMtrGUI.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(StpMtrGUI)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 431, 21))
        self.menubar.setObjectName("menubar")
        self.menuSettings = QtWidgets.QMenu(self.menubar)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.menuSettings.sizePolicy().hasHeightForWidth())
        self.menuSettings.setSizePolicy(sizePolicy)
        self.menuSettings.setMaximumSize(QtCore.QSize(135, 50))
        font = QtGui.QFont()
        font.setFamily("Palatino Linotype")
        self.menuSettings.setFont(font)
        self.menuSettings.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.menuSettings.setObjectName("menuSettings")
        StpMtrGUI.setMenuBar(self.menubar)
        self.menubar.addAction(self.menuSettings.menuAction())

        self.retranslateUi(StpMtrGUI)
        QtCore.QMetaObject.connectSlotsByName(StpMtrGUI)

    def retranslateUi(self, StpMtrGUI, controller_status: StpMtrCtrlStatusMultiAxes=None):
        _translate = QtCore.QCoreApplication.translate
        try:
            self.checkBox_activate.setChecked(self.parameters.device_status.active)
            self.checkBox_power.setChecked(self.parameters.device_status.power)
            title = self.parameters.device_description.GUI_title
            axis_id = int(self.spinBox_axis.value())
            axes: Dict[int, AxisStpMtr] = self.parameters.device_description.axes
            axis: AxisStpMtr = axes[axis_id]
            self.checkBox_On.setChecked(axis.status)
            self.lcdNumber_position.display(axis.position)
            name = axis.name
            ranges = str(axis.limits)
            preset = str(axis.preset_values)
        except KeyError:
            #TODO: modify
            axis = 1
            title = ''
            name = 'test_name'
            ranges = str((0, 100))
            preset = str([0, 100])
        StpMtrGUI.setWindowTitle(_translate("StpMtrGUI", title))
        self.label.setText(_translate("StpMtrGUI", "axis ID"))
        self.label_name.setText(_translate("StpMtrGUI", name))
        self.label_ranges.setText(_translate("StpMtrGUI", ranges))
        self.label_preset.setText(_translate("StpMtrGUI", preset))

        self.radioButton_relative.setText(_translate("StpMtrGUI", "relative"))
        self.radioButton_absolute.setText(_translate("StpMtrGUI", "absolute"))
        self.checkBox_On.setText(_translate("StpMtrGUI", "On"))
        self.pushButton_move.setText(_translate("StpMtrGUI", "MOVE"))
        self.pushButton_stop.setText(_translate("StpMtrGUI", "STOP"))
        self.checkBox_activate.setText(_translate("StpMtrGUI", "Activate controller"))
        self.checkBox_power.setText(_translate("StpMtrGUI", "Power controller"))
        self.menuSettings.setTitle(_translate("StpMtrGUI", "Settings"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QMainWindow()
    ui = Ui_StpMtrGUI()
    ui.setupUi(widget)
    widget.show()
    sys.exit(app.exec_())