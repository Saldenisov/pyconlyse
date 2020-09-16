# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_stpmtr_axis_simple.ui'
#
# Created by: PyQt5 UI code generator 5.13.1
#
# WARNING! All changes made in this file will be lost!


import logging
from typing import Dict

from PyQt5 import QtCore, QtGui, QtWidgets

from utilities.datastructures.mes_independent.devices_dataclass import ControllerInfoExt
from utilities.datastructures.mes_independent.stpmtr_dataclass import AxisStpMtr, MoveType, StepMotorsControllerState

module_logger = logging.getLogger(__name__)

class Ui_StpMtrGUI(object):

    def setupUi(self, StpMtrGUI, parameters: ControllerInfoExt = {}):
        self.parameters = parameters
        StpMtrGUI.setObjectName("StpMtrGUI")
        StpMtrGUI.resize(529, 282)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(StpMtrGUI.sizePolicy().hasHeightForWidth())
        StpMtrGUI.setSizePolicy(sizePolicy)
        self.centralwidget = QtWidgets.QWidget(StpMtrGUI)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.line_3 = QtWidgets.QFrame(self.centralwidget)
        self.line_3.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_3.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_3.setObjectName("line_3")
        self.verticalLayout.addWidget(self.line_3)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(-1, 0, 0, -1)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.checkBox_power = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_power.setObjectName("checkBox_power")
        self.horizontalLayout.addWidget(self.checkBox_power)
        self.checkBox_activate = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_activate.setObjectName("checkBox_activate")
        self.horizontalLayout.addWidget(self.checkBox_activate)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.axis_movement_typeHL = QtWidgets.QHBoxLayout()
        self.axis_movement_typeHL.setObjectName("axis_movement_typeHL")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.axis_movement_typeHL.addWidget(self.label)
        self.spinBox_axis = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_axis.setObjectName("spinBox_axis")
        self.axis_movement_typeHL.addWidget(self.spinBox_axis)
        try:
            ids = self.parameters.device_description.axes.keys()
            self.spinBox_axis.setMinimum(min(ids))
            self.spinBox_axis.setMaximum(max(ids))
        except (KeyError, AttributeError):
            self.spinBox_axis.setMinimum(1)
            self.spinBox_axis.setMaximum(2)

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
        self.line = QtWidgets.QFrame(self.centralwidget)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout.addWidget(self.line)
        self.axis_moveHL = QtWidgets.QHBoxLayout()
        self.axis_moveHL.setObjectName("axis_moveHL")
        self.lcdNumber_position = QtWidgets.QLCDNumber(self.centralwidget)
        self.lcdNumber_position.setMinimumSize(QtCore.QSize(0, 38))
        self.lcdNumber_position.setSmallDecimalPoint(True)
        self.lcdNumber_position.setProperty("value", 0.0)
        self.lcdNumber_position.setObjectName("lcdNumber_position")
        self.axis_moveHL.addWidget(self.lcdNumber_position)
        self.verticalLayout_radiobuttons = QtWidgets.QVBoxLayout()
        self.verticalLayout_radiobuttons.setContentsMargins(-1, 0, 0, -1)
        self.verticalLayout_radiobuttons.setSpacing(0)
        self.verticalLayout_radiobuttons.setObjectName("verticalLayout_radiobuttons")
        self.groupBox_stp_or_mm = QtWidgets.QGroupBox(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_stp_or_mm.sizePolicy().hasHeightForWidth())
        self.groupBox_stp_or_mm.setSizePolicy(sizePolicy)
        self.groupBox_stp_or_mm.setMaximumSize(QtCore.QSize(16777215, 20))
        self.groupBox_stp_or_mm.setTitle("")
        self.groupBox_stp_or_mm.setObjectName("groupBox_stp_or_mm")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.groupBox_stp_or_mm)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.radioButton_angle = QtWidgets.QRadioButton(self.groupBox_stp_or_mm)
        self.radioButton_angle.setObjectName("radioButton_angle")
        self.horizontalLayout_2.addWidget(self.radioButton_angle)
        self.radioButton_mm = QtWidgets.QRadioButton(self.groupBox_stp_or_mm)
        self.radioButton_mm.setEnabled(True)
        self.radioButton_mm.setChecked(True)
        self.radioButton_mm.setObjectName("radioButton_mm")
        self.horizontalLayout_2.addWidget(self.radioButton_mm)
        self.radioButton_stp = QtWidgets.QRadioButton(self.groupBox_stp_or_mm)
        self.radioButton_stp.setIconSize(QtCore.QSize(16, 10))
        self.radioButton_stp.setObjectName("radioButton_stp")
        self.horizontalLayout_2.addWidget(self.radioButton_stp)
        self.verticalLayout_radiobuttons.addWidget(self.groupBox_stp_or_mm)
        self.groupBox_how_to_move = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox_how_to_move.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_how_to_move.sizePolicy().hasHeightForWidth())
        self.groupBox_how_to_move.setSizePolicy(sizePolicy)
        self.groupBox_how_to_move.setTitle("")
        self.groupBox_how_to_move.setObjectName("groupBox_how_to_move")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(self.groupBox_how_to_move)
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.radioButton_absolute = QtWidgets.QRadioButton(self.groupBox_how_to_move)
        self.radioButton_absolute.setChecked(True)
        self.radioButton_absolute.setObjectName("radioButton_absolute")
        self.horizontalLayout_3.addWidget(self.radioButton_absolute)
        self.radioButton_relative = QtWidgets.QRadioButton(self.groupBox_how_to_move)
        self.radioButton_relative.setObjectName("radioButton_relative")
        self.horizontalLayout_3.addWidget(self.radioButton_relative)
        self.verticalLayout_radiobuttons.addWidget(self.groupBox_how_to_move)
        self.axis_moveHL.addLayout(self.verticalLayout_radiobuttons)
        self.verticalLayout_4 = QtWidgets.QVBoxLayout()
        self.verticalLayout_4.setContentsMargins(5, -1, 0, -1)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.label_ranges = QtWidgets.QLabel(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_ranges.sizePolicy().hasHeightForWidth())
        self.label_ranges.setSizePolicy(sizePolicy)
        self.label_ranges.setObjectName("label_ranges")
        self.verticalLayout_4.addWidget(self.label_ranges)
        self.line_4 = QtWidgets.QFrame(self.centralwidget)
        self.line_4.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_4.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_4.setObjectName("line_4")
        self.verticalLayout_4.addWidget(self.line_4)
        self.label_preset = QtWidgets.QLabel(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_preset.sizePolicy().hasHeightForWidth())
        self.label_preset.setSizePolicy(sizePolicy)
        self.label_preset.setObjectName("label_preset")
        self.verticalLayout_4.addWidget(self.label_preset)
        self.lineEdit_value = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_value.setObjectName("lineEdit_value")
        self.verticalLayout_4.addWidget(self.lineEdit_value)
        self.axis_moveHL.addLayout(self.verticalLayout_4)
        self.verticalLayout.addLayout(self.axis_moveHL)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setContentsMargins(-1, 0, 0, -1)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.pushButton_move = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_move.setObjectName("pushButton_move")
        self.horizontalLayout_4.addWidget(self.pushButton_move)
        self.pushButton_stop = QtWidgets.QPushButton(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_stop.sizePolicy().hasHeightForWidth())
        self.pushButton_stop.setSizePolicy(sizePolicy)
        self.pushButton_stop.setMinimumSize(QtCore.QSize(0, 0))
        self.pushButton_stop.setObjectName("pushButton_stop")
        self.horizontalLayout_4.addWidget(self.pushButton_stop)
        self.pushButton_set = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_set.setObjectName("pushButton_set")
        self.horizontalLayout_4.addWidget(self.pushButton_set)
        self.verticalLayout.addLayout(self.horizontalLayout_4)
        self.line_2 = QtWidgets.QFrame(self.centralwidget)
        self.line_2.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_2.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_2.setObjectName("line_2")
        self.verticalLayout.addWidget(self.line_2)
        self.comments = QtWidgets.QTextEdit(self.centralwidget)
        self.comments.setMaximumSize(QtCore.QSize(16777215, 80))
        self.comments.setObjectName("comments")
        self.verticalLayout.addWidget(self.comments)
        StpMtrGUI.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(StpMtrGUI)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 529, 21))
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

    def retranslateUi(self, StpMtrGUI, controller_status: StepMotorsControllerState=None):
        _translate = QtCore.QCoreApplication.translate
        try:
            self.checkBox_activate.setChecked(self.parameters.controller_status.active)
            self.checkBox_power.setChecked(self.parameters.controller_status.power)
            title = self.parameters.device_description.GUI_title
            axis_id = int(self.spinBox_axis.value())
            axes: Dict[int, AxisStpMtr] = self.parameters.device_description.axes
            axis: AxisStpMtr = axes[axis_id]
            self.checkBox_On.setChecked(axis.status)

            name = axis.name

            def form_ranges(ranges) -> str:
                out_l = []
                for val in ranges:
                    try:
                        val = val.name
                    except AttributeError:
                        val = str(val)
                    finally:
                        out_l.append(val)
                return '_'.join(out_l)

            ranges = f'Ranges: {form_ranges(axis.limits)}'
            preset = f'Preset Positions: {form_ranges(axis.preset_values)}'

            if MoveType.step in axis.type_move or MoveType.microstep in axis.type_move:
                self.radioButton_stp.setEnabled(True)
            else:
                self.radioButton_stp.setEnabled(False)

            if MoveType.angle in axis.type_move:
                self.radioButton_angle.setEnabled(True)
            else:
                self.radioButton_angle.setEnabled(False)

            if MoveType.mm in axis.type_move:
                self.radioButton_mm.setEnabled(True)
            else:
                self.radioButton_mm.setEnabled(False)

        except (KeyError, AttributeError):
            #TODO: modify
            axis = 1
            title = ''
            name = 'test_name'
            ranges = f'Ranges: {str((0, 100))}'
            preset = f'Preset Positions: {str([0, 100])}'
            self.spinBox_axis.setMaximum(len(ranges))


        StpMtrGUI.setWindowTitle(_translate("StpMtrGUI", title))
        self.label.setText(_translate("StpMtrGUI", "axis ID"))
        self.label_name.setText(_translate("StpMtrGUI", name))
        self.label_ranges.setText(_translate("StpMtrGUI", ranges))
        self.label_preset.setText(_translate("StpMtrGUI", preset))

        _translate = QtCore.QCoreApplication.translate
        self.checkBox_power.setText(_translate("StpMtrGUI", "Power Controller"))
        self.checkBox_activate.setText(_translate("StpMtrGUI", "Activate Controller"))
        self.checkBox_On.setText(_translate("StpMtrGUI", "On"))
        self.radioButton_angle.setText(_translate("StpMtrGUI", "angle"))
        self.radioButton_mm.setText(_translate("StpMtrGUI", "mm"))
        self.radioButton_stp.setText(_translate("StpMtrGUI", "stp"))
        self.radioButton_absolute.setText(_translate("StpMtrGUI", "absolute"))
        self.radioButton_relative.setText(_translate("StpMtrGUI", "relative"))
        self.pushButton_move.setText(_translate("StpMtrGUI", "MOVE"))
        self.pushButton_stop.setText(_translate("StpMtrGUI", "STOP"))
        self.pushButton_set.setText(_translate("StpMtrGUI", "SET"))
        self.menuSettings.setTitle(_translate("StpMtrGUI", "Settings"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QMainWindow()
    ui = Ui_StpMtrGUI()
    ui.setupUi(widget)
    widget.show()
    sys.exit(app.exec_())