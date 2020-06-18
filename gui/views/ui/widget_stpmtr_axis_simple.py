# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_stpmtr_axis_simple.ui'
#
# Created by: PyQt5 UI code generator 5.13.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Dict
from utilities.datastructures.mes_independent.devices_dataclass import DeviceInfoExt
from utilities.datastructures.mes_independent.stpmtr_dataclass import AxisStpMtr, StpMtrCtrlStatusMultiAxes
import logging


module_logger = logging.getLogger(__name__)


class Ui_StpMtrGUI(object):

    def setupUi(self, StpMtrGUI, parameters: DeviceInfoExt = {}):
        self.parameters: DeviceInfoExt = parameters
        StpMtrGUI.setObjectName("StpMtrGUI")
        StpMtrGUI.resize(631, 339)
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
        self.spinBox_axis.setObjectName("spinBox_axis")
        try:
            ids = self.parameters.device_description.axes.keys()
            self.spinBox_axis.setMinimum(min(ids))
            self.spinBox_axis.setMaximum(max(ids))
        except (KeyError, AttributeError):
            self.spinBox_axis.setMinimum(1)
            self.spinBox_axis.setMaximum(2)

        self.axis_movement_typeHL.addWidget(self.spinBox_axis)
        self.checkBox_On = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_On.setChecked(False)
        self.checkBox_On.setObjectName("checkBox_On")
        self.axis_movement_typeHL.addWidget(self.checkBox_On)
        self.label_name = QtWidgets.QLabel(self.centralwidget)
        self.label_name.setObjectName("label_name")
        self.axis_movement_typeHL.addWidget(self.label_name)
        self.progressBar_movement = QtWidgets.QProgressBar(self.centralwidget)
        self.progressBar_movement.setMinimumSize(QtCore.QSize(350, 0))
        self.progressBar_movement.setProperty("value", 0)
        self.progressBar_movement.setObjectName("progressBar_movement")
        self.axis_movement_typeHL.addWidget(self.progressBar_movement)
        self.verticalLayout.addLayout(self.axis_movement_typeHL)
        self.axis_moveHL = QtWidgets.QHBoxLayout()
        self.axis_moveHL.setObjectName("axis_moveHL")
        self.lcdNumber_position = QtWidgets.QLCDNumber(self.centralwidget)
        self.lcdNumber_position.setSmallDecimalPoint(True)
        self.lcdNumber_position.setProperty("value", 0.0)
        self.lcdNumber_position.setObjectName("lcdNumber_position")
        self.axis_moveHL.addWidget(self.lcdNumber_position)
        self.groupBox_stp_or_mm = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox_stp_or_mm.setTitle("")
        self.groupBox_stp_or_mm.setObjectName("groupBox_stp_or_mm")
        self.verticalLayout_stp_or_mm = QtWidgets.QVBoxLayout(self.groupBox_stp_or_mm)
        self.verticalLayout_stp_or_mm.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_stp_or_mm.setSpacing(0)
        self.verticalLayout_stp_or_mm.setObjectName("verticalLayout_stp_or_mm")
        self.radioButton_stp = QtWidgets.QRadioButton(self.groupBox_stp_or_mm)
        self.radioButton_stp.setObjectName("radioButton_stp")
        self.verticalLayout_stp_or_mm.addWidget(self.radioButton_stp)
        self.radioButton_mm = QtWidgets.QRadioButton(self.groupBox_stp_or_mm)
        self.radioButton_mm.setEnabled(True)
        self.radioButton_mm.setChecked(True)
        self.radioButton_mm.setObjectName("radioButton_mm")
        self.verticalLayout_stp_or_mm.addWidget(self.radioButton_mm)
        self.radioButton_angle = QtWidgets.QRadioButton(self.groupBox_stp_or_mm)
        self.radioButton_angle.setEnabled(True)
        self.radioButton_angle.setChecked(False)
        self.radioButton_angle.setObjectName("radioButton_angle")
        self.verticalLayout_stp_or_mm.addWidget(self.radioButton_angle)
        self.axis_moveHL.addWidget(self.groupBox_stp_or_mm)
        self.groupBox_how_to_move = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox_how_to_move.setTitle("")
        self.groupBox_how_to_move.setObjectName("groupBox_how_to_move")
        self.verticalLayout_how_to_move = QtWidgets.QVBoxLayout(self.groupBox_how_to_move)
        self.verticalLayout_how_to_move.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_how_to_move.setSpacing(0)
        self.verticalLayout_how_to_move.setObjectName("verticalLayout_how_to_move")
        self.radioButton_relative = QtWidgets.QRadioButton(self.groupBox_how_to_move)
        self.radioButton_relative.setObjectName("radioButton_relative")
        self.verticalLayout_how_to_move.addWidget(self.radioButton_relative)
        self.radioButton_absolute = QtWidgets.QRadioButton(self.groupBox_how_to_move)
        self.radioButton_absolute.setChecked(True)
        self.radioButton_absolute.setObjectName("radioButton_absolute")
        self.verticalLayout_how_to_move.addWidget(self.radioButton_absolute)
        self.axis_moveHL.addWidget(self.groupBox_how_to_move)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setContentsMargins(-1, -1, 0, -1)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.axis_moveHL.addLayout(self.verticalLayout_3)
        self.lineEdit_value = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_value.setObjectName("lineEdit_value")
        self.axis_moveHL.addWidget(self.lineEdit_value)
        self.pushButton_move = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_move.setObjectName("pushButton_move")
        self.axis_moveHL.addWidget(self.pushButton_move)
        self.pushButton_stop = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_stop.setObjectName("pushButton_stop")
        self.axis_moveHL.addWidget(self.pushButton_stop)
        self.pushButton_set = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_set.setObjectName("pushButton_set")
        self.axis_moveHL.addWidget(self.pushButton_set)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.axis_moveHL.addItem(spacerItem)
        self.verticalLayout.addLayout(self.axis_moveHL)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(-1, 0, -1, -1)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_ranges = QtWidgets.QLabel(self.centralwidget)
        self.label_ranges.setObjectName("label_ranges")
        self.horizontalLayout.addWidget(self.label_ranges)
        self.label_preset = QtWidgets.QLabel(self.centralwidget)
        self.label_preset.setObjectName("label_preset")
        self.horizontalLayout.addWidget(self.label_preset)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.plainTextEdit = QtWidgets.QPlainTextEdit(self.centralwidget)
        self.plainTextEdit.setObjectName("plainTextEdit")
        self.verticalLayout.addWidget(self.plainTextEdit)
        self.checkBox_activate = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_activate.setObjectName("checkBox_activate")
        self.verticalLayout.addWidget(self.checkBox_activate)
        self.checkBox_power = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_power.setObjectName("checkBox_power")
        self.verticalLayout.addWidget(self.checkBox_power)
        StpMtrGUI.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(StpMtrGUI)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 631, 21))
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
        except (KeyError, AttributeError):
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

        _translate = QtCore.QCoreApplication.translate

        StpMtrGUI.setWindowTitle(_translate("StpMtrGUI", "StpMtrGUI"))
        self.checkBox_On.setText(_translate("StpMtrGUI", "On"))
        self.radioButton_stp.setText(_translate("StpMtrGUI", "steps/microstep"))
        self.radioButton_mm.setText(_translate("StpMtrGUI", "mm"))
        self.radioButton_angle.setText(_translate("StpMtrGUI", "angle"))
        self.radioButton_relative.setText(_translate("StpMtrGUI", "relative"))
        self.radioButton_absolute.setText(_translate("StpMtrGUI", "absolute"))
        self.pushButton_move.setText(_translate("StpMtrGUI", "MOVE"))
        self.pushButton_stop.setText(_translate("StpMtrGUI", "STOP"))
        self.pushButton_set.setText(_translate("StpMtrGUI", "SET"))
        self.checkBox_activate.setText(_translate("StpMtrGUI", "Activate Controller"))
        self.checkBox_power.setText(_translate("StpMtrGUI", "Power Controller"))
        self.menuSettings.setTitle(_translate("StpMtrGUI", "Settings"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QMainWindow()
    ui = Ui_StpMtrGUI()
    ui.setupUi(widget)
    widget.show()
    sys.exit(app.exec_())