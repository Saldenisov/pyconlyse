# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_stpmtr_axis_simple.ui'
#
# Created by: PyQt5 UI code generator 5.13.1
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets
from utilities.data.messages import ServiceInfoMes

class Ui_StpMtrGUI(object):

    def setupUi(self, StpMtrGUI, parameters=ServiceInfoMes()):
        self.parameters = parameters
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
            self.spinBox_axis.setMinimum(self.parameters.device_decription['axes_values'][0])
            self.spinBox_axis.setMaximum(self.parameters.device_decription['axes_values'][1])
        except KeyError:
            self.spinBox_axis.setMinimum(0)
            self.spinBox_axis.setMaximum(1)
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

    def retranslateUi(self, StpMtrGUI):
        _translate = QtCore.QCoreApplication.translate
        try:
            title = self.parameters.device_decription['GUI_title']
            axis = int(self.spinBox_axis.value())
            name = self.parameters.device_decription['axes_names'][axis]
            ranges = str(self.parameters.device_decription['ranges'][axis][0:2])
            preset = self.parameters.device_decription['ranges'][axis][2]
            preset_list_str = []
            i = 0
            for item in preset:
                preset_list_str.append(f'{i}: {item}')
                i += 1
            preset = str(preset_list_str)
        except KeyError:
            title = ''
            name = 'test_name'
            ranges = str((0, 100))
            preset = str([0, 100])
        StpMtrGUI.setWindowTitle(_translate("StpMtrGUI", title))
        self.label.setText(_translate("StpMtrGUI", "axis #"))
        self.label_name.setText(_translate("StpMtrGUI", name))
        self.label_ranges.setText(_translate("StpMtrGUI", ranges))
        self.label_preset.setText(_translate("StpMtrGUI", preset))

        self.radioButton_relative.setText(_translate("StpMtrGUI", "relative"))
        self.radioButton_absolute.setText(_translate("StpMtrGUI", "absolute"))
        self.checkBox_On.setText(_translate("StpMtrGUI", "On"))
        self.pushButton_move.setText(_translate("StpMtrGUI", "MOVE"))
        self.pushButton_stop.setText(_translate("StpMtrGUI", "STOP"))
        self.menuSettings.setTitle(_translate("StpMtrGUI", "Settings"))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QMainWindow()
    ui = Ui_StpMtrGUI()
    ui.setupUi(widget)
    widget.show()
    sys.exit(app.exec_())