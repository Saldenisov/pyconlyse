# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'widget_camera.ui'
#
# Created by: PyQt5 UI code generator 5.15.0
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_CameraGUI(object):
    def setupUi(self, CameraGUI):
        CameraGUI.setObjectName("CameraGUI")
        CameraGUI.setEnabled(True)
        CameraGUI.resize(741, 835)
        self.centralwidget = QtWidgets.QWidget(CameraGUI)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setContentsMargins(-1, -1, -1, 15)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.comboBox_gain_mode = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox_gain_mode.setObjectName("comboBox_gain_mode")
        self.comboBox_gain_mode.addItem("")
        self.comboBox_gain_mode.addItem("")
        self.comboBox_gain_mode.addItem("")
        self.gridLayout.addWidget(self.comboBox_gain_mode, 5, 3, 1, 1)
        self.spinBox_trigger_delay = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_trigger_delay.setMaximum(1000000)
        self.spinBox_trigger_delay.setObjectName("spinBox_trigger_delay")
        self.gridLayout.addWidget(self.spinBox_trigger_delay, 2, 3, 1, 1)
        self.label_device_id = QtWidgets.QLabel(self.centralwidget)
        self.label_device_id.setObjectName("label_device_id")
        self.gridLayout.addWidget(self.label_device_id, 0, 0, 1, 1)
        self.spinBox_fps = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_fps.setMinimum(1)
        self.spinBox_fps.setMaximum(50)
        self.spinBox_fps.setProperty("value", 5)
        self.spinBox_fps.setObjectName("spinBox_fps")
        self.gridLayout.addWidget(self.spinBox_fps, 4, 3, 1, 1)
        self.spinBox_gainraw = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_gainraw.setMaximum(3)
        self.spinBox_gainraw.setObjectName("spinBox_gainraw")
        self.gridLayout.addWidget(self.spinBox_gainraw, 6, 1, 1, 1)
        self.spinBox_balance_ratio = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_balance_ratio.setMaximum(1023)
        self.spinBox_balance_ratio.setObjectName("spinBox_balance_ratio")
        self.gridLayout.addWidget(self.spinBox_balance_ratio, 6, 3, 1, 1)
        self.spinBox_exposure_time = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_exposure_time.setMinimum(15)
        self.spinBox_exposure_time.setMaximum(896000)
        self.spinBox_exposure_time.setProperty("value", 15)
        self.spinBox_exposure_time.setObjectName("spinBox_exposure_time")
        self.gridLayout.addWidget(self.spinBox_exposure_time, 3, 3, 1, 1)
        self.label_trig_source = QtWidgets.QLabel(self.centralwidget)
        self.label_trig_source.setObjectName("label_trig_source")
        self.gridLayout.addWidget(self.label_trig_source, 1, 2, 1, 1)
        self.label_trig_delay = QtWidgets.QLabel(self.centralwidget)
        self.label_trig_delay.setObjectName("label_trig_delay")
        self.gridLayout.addWidget(self.label_trig_delay, 2, 2, 1, 1)
        self.label_Width = QtWidgets.QLabel(self.centralwidget)
        self.label_Width.setObjectName("label_Width")
        self.gridLayout.addWidget(self.label_Width, 1, 0, 1, 1)
        self.label_Xoffset = QtWidgets.QLabel(self.centralwidget)
        self.label_Xoffset.setObjectName("label_Xoffset")
        self.gridLayout.addWidget(self.label_Xoffset, 3, 0, 1, 1)
        self.spinBox_packetsize = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_packetsize.setMaximum(16000)
        self.spinBox_packetsize.setSingleStep(4)
        self.spinBox_packetsize.setProperty("value", 1500)
        self.spinBox_packetsize.setObjectName("spinBox_packetsize")
        self.gridLayout.addWidget(self.spinBox_packetsize, 0, 5, 1, 1)
        self.spinBox_Height = QtWidgets.QSpinBox(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.spinBox_Height.sizePolicy().hasHeightForWidth())
        self.spinBox_Height.setSizePolicy(sizePolicy)
        self.spinBox_Height.setMinimum(0)
        self.spinBox_Height.setMaximum(2000)
        self.spinBox_Height.setProperty("value", 0)
        self.spinBox_Height.setObjectName("spinBox_Height")
        self.gridLayout.addWidget(self.spinBox_Height, 2, 1, 1, 1)
        self.comboBox_TrigSource = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox_TrigSource.setEnabled(False)
        self.comboBox_TrigSource.setObjectName("comboBox_TrigSource")
        self.comboBox_TrigSource.addItem("")
        self.gridLayout.addWidget(self.comboBox_TrigSource, 1, 3, 1, 1)
        self.label_Height = QtWidgets.QLabel(self.centralwidget)
        self.label_Height.setObjectName("label_Height")
        self.gridLayout.addWidget(self.label_Height, 2, 0, 1, 1)
        self.label_sync_mode = QtWidgets.QLabel(self.centralwidget)
        self.label_sync_mode.setObjectName("label_sync_mode")
        self.gridLayout.addWidget(self.label_sync_mode, 0, 2, 1, 1)
        self.spinBox_Width = QtWidgets.QSpinBox(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.spinBox_Width.sizePolicy().hasHeightForWidth())
        self.spinBox_Width.setSizePolicy(sizePolicy)
        self.spinBox_Width.setMaximum(2000)
        self.spinBox_Width.setObjectName("spinBox_Width")
        self.gridLayout.addWidget(self.spinBox_Width, 1, 1, 1, 1)
        self.spinBox_Xoffset = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_Xoffset.setMaximum(2000)
        self.spinBox_Xoffset.setSingleStep(2)
        self.spinBox_Xoffset.setObjectName("spinBox_Xoffset")
        self.gridLayout.addWidget(self.spinBox_Xoffset, 3, 1, 1, 1)
        self.label_exposure_time = QtWidgets.QLabel(self.centralwidget)
        self.label_exposure_time.setObjectName("label_exposure_time")
        self.gridLayout.addWidget(self.label_exposure_time, 3, 2, 1, 1)
        self.label_black_level = QtWidgets.QLabel(self.centralwidget)
        self.label_black_level.setObjectName("label_black_level")
        self.gridLayout.addWidget(self.label_black_level, 5, 0, 1, 1)
        self.spinBox_Yoffset = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_Yoffset.setMaximum(2000)
        self.spinBox_Yoffset.setSingleStep(2)
        self.spinBox_Yoffset.setObjectName("spinBox_Yoffset")
        self.gridLayout.addWidget(self.spinBox_Yoffset, 4, 1, 1, 1)
        self.label_gainraw = QtWidgets.QLabel(self.centralwidget)
        self.label_gainraw.setObjectName("label_gainraw")
        self.gridLayout.addWidget(self.label_gainraw, 6, 0, 1, 1)
        self.label_packet_size = QtWidgets.QLabel(self.centralwidget)
        self.label_packet_size.setObjectName("label_packet_size")
        self.gridLayout.addWidget(self.label_packet_size, 0, 4, 1, 1)
        self.label_inter_packet_delay = QtWidgets.QLabel(self.centralwidget)
        self.label_inter_packet_delay.setObjectName("label_inter_packet_delay")
        self.gridLayout.addWidget(self.label_inter_packet_delay, 1, 4, 1, 1)
        self.spinBox_interpacket_delay = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_interpacket_delay.setMaximum(2514068)
        self.spinBox_interpacket_delay.setProperty("value", 1000)
        self.spinBox_interpacket_delay.setObjectName("spinBox_interpacket_delay")
        self.gridLayout.addWidget(self.spinBox_interpacket_delay, 1, 5, 1, 1)
        self.label_balance = QtWidgets.QLabel(self.centralwidget)
        self.label_balance.setObjectName("label_balance")
        self.gridLayout.addWidget(self.label_balance, 6, 2, 1, 1)
        self.comboBox_syncmode = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox_syncmode.setObjectName("comboBox_syncmode")
        self.comboBox_syncmode.addItem("")
        self.comboBox_syncmode.addItem("")
        self.gridLayout.addWidget(self.comboBox_syncmode, 0, 3, 1, 1)
        self.spinBox_device_id = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_device_id.setProperty("value", 1)
        self.spinBox_device_id.setObjectName("spinBox_device_id")
        self.gridLayout.addWidget(self.spinBox_device_id, 0, 1, 1, 1)
        self.label_gainmode = QtWidgets.QLabel(self.centralwidget)
        self.label_gainmode.setObjectName("label_gainmode")
        self.gridLayout.addWidget(self.label_gainmode, 5, 2, 1, 1)
        self.label_Yoffset = QtWidgets.QLabel(self.centralwidget)
        self.label_Yoffset.setObjectName("label_Yoffset")
        self.gridLayout.addWidget(self.label_Yoffset, 4, 0, 1, 1)
        self.label_fps = QtWidgets.QLabel(self.centralwidget)
        self.label_fps.setObjectName("label_fps")
        self.gridLayout.addWidget(self.label_fps, 4, 2, 1, 1)
        self.spinBox_blacklevel = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_blacklevel.setMinimum(-127)
        self.spinBox_blacklevel.setMaximum(127)
        self.spinBox_blacklevel.setObjectName("spinBox_blacklevel")
        self.gridLayout.addWidget(self.spinBox_blacklevel, 5, 1, 1, 1)
        self.pushButton_set_parameters = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_set_parameters.setObjectName("pushButton_set_parameters")
        self.gridLayout.addWidget(self.pushButton_set_parameters, 6, 4, 1, 1)
        self.horizontalLayout.addLayout(self.gridLayout)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.comments = QtWidgets.QTextEdit(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.comments.sizePolicy().hasHeightForWidth())
        self.comments.setSizePolicy(sizePolicy)
        self.comments.setMaximumSize(QtCore.QSize(1000, 16777215))
        self.comments.setObjectName("comments")
        self.verticalLayout_3.addWidget(self.comments)
        self.horizontalLayout.addLayout(self.verticalLayout_3)
        self.verticalLayout_2.addLayout(self.horizontalLayout)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setContentsMargins(-1, 0, -1, -1)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.checkBox_power = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_power.setObjectName("checkBox_power")
        self.horizontalLayout_4.addWidget(self.checkBox_power)
        self.checkBox_ctrl_activate = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_ctrl_activate.setObjectName("checkBox_ctrl_activate")
        self.horizontalLayout_4.addWidget(self.checkBox_ctrl_activate)
        self.label_name = QtWidgets.QLabel(self.centralwidget)
        self.label_name.setObjectName("label_name")
        self.horizontalLayout_4.addWidget(self.label_name)
        self.checkBox_device_activate = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_device_activate.setObjectName("checkBox_device_activate")
        self.horizontalLayout_4.addWidget(self.checkBox_device_activate)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(spacerItem)
        self.verticalLayout_2.addLayout(self.horizontalLayout_4)
        self.horizontalLayout_canvas = QtWidgets.QVBoxLayout()
        self.horizontalLayout_canvas.setObjectName("horizontalLayout_canvas")
        self.verticalWidget_toolbox = QtWidgets.QWidget(self.centralwidget)
        self.verticalWidget_toolbox.setObjectName("verticalWidget_toolbox")
        self.toolbox = QtWidgets.QVBoxLayout(self.verticalWidget_toolbox)
        self.toolbox.setContentsMargins(-1, -1, -1, 16)
        self.toolbox.setObjectName("toolbox")
        self.horizontalLayout_canvas.addWidget(self.verticalWidget_toolbox)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.horizontalLayout_canvas.addItem(spacerItem1)
        self.verticalLayout_2.addLayout(self.horizontalLayout_canvas)
        self.gridLayout_2 = QtWidgets.QGridLayout()
        self.gridLayout_2.setContentsMargins(-1, 0, -1, -1)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.checkBox_show_history = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_show_history.setObjectName("checkBox_show_history")
        self.horizontalLayout_2.addWidget(self.checkBox_show_history)
        self.label_n_points_history = QtWidgets.QLabel(self.centralwidget)
        self.label_n_points_history.setObjectName("label_n_points_history")
        self.horizontalLayout_2.addWidget(self.label_n_points_history)
        self.spinBox_cg_points = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_cg_points.setMinimum(1)
        self.spinBox_cg_points.setProperty("value", 20)
        self.spinBox_cg_points.setObjectName("spinBox_cg_points")
        self.horizontalLayout_2.addWidget(self.spinBox_cg_points)
        self.label_average_coordinate = QtWidgets.QLabel(self.centralwidget)
        self.label_average_coordinate.setObjectName("label_average_coordinate")
        self.horizontalLayout_2.addWidget(self.label_average_coordinate)
        self.gridLayout_2.addLayout(self.horizontalLayout_2, 2, 2, 1, 1)
        self.pushButton_fix_track_point = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_fix_track_point.setObjectName("pushButton_fix_track_point")
        self.gridLayout_2.addWidget(self.pushButton_fix_track_point, 0, 2, 1, 1)
        self.pushButton_GetImages = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_GetImages.setObjectName("pushButton_GetImages")
        self.gridLayout_2.addWidget(self.pushButton_GetImages, 1, 1, 1, 1)
        self.pushButton_stop = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_stop.setObjectName("pushButton_stop")
        self.gridLayout_2.addWidget(self.pushButton_stop, 2, 1, 1, 1)
        self.pushButton_GetImage = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_GetImage.setObjectName("pushButton_GetImage")
        self.gridLayout_2.addWidget(self.pushButton_GetImage, 0, 1, 1, 1)
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.label_x_stepmotor = QtWidgets.QLabel(self.centralwidget)
        self.label_x_stepmotor.setObjectName("label_x_stepmotor")
        self.horizontalLayout_5.addWidget(self.label_x_stepmotor)
        self.comboBox_x_stepmotor = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox_x_stepmotor.setMinimumSize(QtCore.QSize(150, 0))
        self.comboBox_x_stepmotor.setObjectName("comboBox_x_stepmotor")
        self.horizontalLayout_5.addWidget(self.comboBox_x_stepmotor)
        self.pushButton_decrease_X = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_decrease_X.setObjectName("pushButton_decrease_X")
        self.horizontalLayout_5.addWidget(self.pushButton_decrease_X)
        self.pushButton_increase_X = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_increase_X.setObjectName("pushButton_increase_X")
        self.horizontalLayout_5.addWidget(self.pushButton_increase_X)
        self.gridLayout_2.addLayout(self.horizontalLayout_5, 0, 3, 1, 1)
        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.label_y_stepmotor = QtWidgets.QLabel(self.centralwidget)
        self.label_y_stepmotor.setObjectName("label_y_stepmotor")
        self.horizontalLayout_6.addWidget(self.label_y_stepmotor)
        self.comboBox_y_stepmotor = QtWidgets.QComboBox(self.centralwidget)
        self.comboBox_y_stepmotor.setMinimumSize(QtCore.QSize(150, 0))
        self.comboBox_y_stepmotor.setObjectName("comboBox_y_stepmotor")
        self.horizontalLayout_6.addWidget(self.comboBox_y_stepmotor)
        self.pushButton_decrease_Y = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_decrease_Y.setObjectName("pushButton_decrease_Y")
        self.horizontalLayout_6.addWidget(self.pushButton_decrease_Y)
        self.pushButton_increase_Y = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_increase_Y.setObjectName("pushButton_increase_Y")
        self.horizontalLayout_6.addWidget(self.pushButton_increase_Y)
        self.gridLayout_2.addLayout(self.horizontalLayout_6, 1, 3, 1, 1)
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.checkBox_auto_pos_controlled = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_auto_pos_controlled.setObjectName("checkBox_auto_pos_controlled")
        self.horizontalLayout_7.addWidget(self.checkBox_auto_pos_controlled)
        self.label_accuracy = QtWidgets.QLabel(self.centralwidget)
        self.label_accuracy.setObjectName("label_accuracy")
        self.horizontalLayout_7.addWidget(self.label_accuracy)
        self.spinBox_accuracy_control = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_accuracy_control.setMinimum(1)
        self.spinBox_accuracy_control.setMaximum(20)
        self.spinBox_accuracy_control.setProperty("value", 4)
        self.spinBox_accuracy_control.setObjectName("spinBox_accuracy_control")
        self.horizontalLayout_7.addWidget(self.spinBox_accuracy_control)
        self.label_update_time = QtWidgets.QLabel(self.centralwidget)
        self.label_update_time.setObjectName("label_update_time")
        self.horizontalLayout_7.addWidget(self.label_update_time)
        self.spinBox_update_time = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_update_time.setMinimum(1)
        self.spinBox_update_time.setProperty("value", 5)
        self.spinBox_update_time.setObjectName("spinBox_update_time")
        self.horizontalLayout_7.addWidget(self.spinBox_update_time)
        self.gridLayout_2.addLayout(self.horizontalLayout_7, 2, 3, 1, 1)
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.checkBox_images = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_images.setObjectName("checkBox_images")
        self.horizontalLayout_8.addWidget(self.checkBox_images)
        self.checkBox_cg = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBox_cg.setObjectName("checkBox_cg")
        self.horizontalLayout_8.addWidget(self.checkBox_cg)
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.horizontalLayout_8.addWidget(self.label)
        self.spinBox_threshold = QtWidgets.QSpinBox(self.centralwidget)
        self.spinBox_threshold.setMinimum(0)
        self.spinBox_threshold.setMaximum(255)
        self.spinBox_threshold.setProperty("value", 80)
        self.spinBox_threshold.setObjectName("spinBox_threshold")
        self.horizontalLayout_8.addWidget(self.spinBox_threshold)
        self.gridLayout_2.addLayout(self.horizontalLayout_8, 1, 2, 1, 1)
        self.verticalLayout_2.addLayout(self.gridLayout_2)
        self.line = QtWidgets.QFrame(self.centralwidget)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout_2.addWidget(self.line)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setContentsMargins(-1, 10, -1, -1)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.radioButton_RT = QtWidgets.QRadioButton(self.centralwidget)
        self.radioButton_RT.setChecked(False)
        self.radioButton_RT.setObjectName("radioButton_RT")
        self.horizontalLayout_3.addWidget(self.radioButton_RT)
        self.radioButton_every_n_sec = QtWidgets.QRadioButton(self.centralwidget)
        self.radioButton_every_n_sec.setChecked(True)
        self.radioButton_every_n_sec.setObjectName("radioButton_every_n_sec")
        self.horizontalLayout_3.addWidget(self.radioButton_every_n_sec)
        self.spinBox_seconds = QtWidgets.QDoubleSpinBox(self.centralwidget)
        self.spinBox_seconds.setSingleStep(0.5)
        self.spinBox_seconds.setProperty("value", 1.0)
        self.spinBox_seconds.setObjectName("spinBox_seconds")
        self.horizontalLayout_3.addWidget(self.spinBox_seconds)
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem2)
        self.verticalLayout_2.addLayout(self.horizontalLayout_3)
        self.verticalLayout.addLayout(self.verticalLayout_2)
        CameraGUI.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(CameraGUI)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 741, 21))
        self.menubar.setObjectName("menubar")
        CameraGUI.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(CameraGUI)
        self.statusbar.setObjectName("statusbar")
        CameraGUI.setStatusBar(self.statusbar)

        self.retranslateUi(CameraGUI)
        QtCore.QMetaObject.connectSlotsByName(CameraGUI)

    def retranslateUi(self, CameraGUI):
        _translate = QtCore.QCoreApplication.translate
        CameraGUI.setWindowTitle(_translate("CameraGUI", "MainWindow"))
        self.comboBox_gain_mode.setItemText(0, _translate("CameraGUI", "Off"))
        self.comboBox_gain_mode.setItemText(1, _translate("CameraGUI", "Once"))
        self.comboBox_gain_mode.setItemText(2, _translate("CameraGUI", "Continuous"))
        self.label_device_id.setText(_translate("CameraGUI", "#ID"))
        self.label_trig_source.setText(_translate("CameraGUI", "TrigSource"))
        self.label_trig_delay.setText(_translate("CameraGUI", "Trigger Delay"))
        self.label_Width.setText(_translate("CameraGUI", "Width"))
        self.label_Xoffset.setText(_translate("CameraGUI", "Xoffset"))
        self.comboBox_TrigSource.setItemText(0, _translate("CameraGUI", "Line1"))
        self.label_Height.setText(_translate("CameraGUI", "Height"))
        self.label_sync_mode.setText(_translate("CameraGUI", "SyncMode"))
        self.label_exposure_time.setText(_translate("CameraGUI", "ExposureTime"))
        self.label_black_level.setText(_translate("CameraGUI", "BlackLevel"))
        self.label_gainraw.setText(_translate("CameraGUI", "GainRaw"))
        self.label_packet_size.setText(_translate("CameraGUI", "PacketSize"))
        self.label_inter_packet_delay.setText(_translate("CameraGUI", "InterPacketDelay"))
        self.label_balance.setText(_translate("CameraGUI", "BalanceRatio"))
        self.comboBox_syncmode.setItemText(0, _translate("CameraGUI", "On"))
        self.comboBox_syncmode.setItemText(1, _translate("CameraGUI", "Off"))
        self.label_gainmode.setText(_translate("CameraGUI", "GainMode"))
        self.label_Yoffset.setText(_translate("CameraGUI", "Yoffset"))
        self.label_fps.setText(_translate("CameraGUI", "FPS"))
        self.pushButton_set_parameters.setText(_translate("CameraGUI", "Set"))
        self.checkBox_power.setText(_translate("CameraGUI", "Power"))
        self.checkBox_ctrl_activate.setText(_translate("CameraGUI", "Activate"))
        self.label_name.setText(_translate("CameraGUI", "Name"))
        self.checkBox_device_activate.setText(_translate("CameraGUI", "On"))
        self.checkBox_show_history.setText(_translate("CameraGUI", "Show History"))
        self.label_n_points_history.setText(_translate("CameraGUI", "# points"))
        self.label_average_coordinate.setText(_translate("CameraGUI", "(0, 0)"))
        self.pushButton_fix_track_point.setText(_translate("CameraGUI", "Fix Point"))
        self.pushButton_GetImages.setText(_translate("CameraGUI", "Start Grabbing"))
        self.pushButton_stop.setText(_translate("CameraGUI", "Stop"))
        self.pushButton_GetImage.setText(_translate("CameraGUI", "Grab Once"))
        self.label_x_stepmotor.setText(_translate("CameraGUI", "X stepmotor"))
        self.pushButton_decrease_X.setText(_translate("CameraGUI", "<"))
        self.pushButton_increase_X.setText(_translate("CameraGUI", ">"))
        self.label_y_stepmotor.setText(_translate("CameraGUI", "Y stepmotor"))
        self.pushButton_decrease_Y.setText(_translate("CameraGUI", "<"))
        self.pushButton_increase_Y.setText(_translate("CameraGUI", ">"))
        self.checkBox_auto_pos_controlled.setText(_translate("CameraGUI", "Auto"))
        self.label_accuracy.setText(_translate("CameraGUI", "Accuracy"))
        self.label_update_time.setText(_translate("CameraGUI", "UpdateTime"))
        self.checkBox_images.setText(_translate("CameraGUI", "Images?"))
        self.checkBox_cg.setText(_translate("CameraGUI", "CG tracking"))
        self.label.setText(_translate("CameraGUI", "Threshold"))
        self.radioButton_RT.setText(_translate("CameraGUI", "Real Time"))
        self.radioButton_every_n_sec.setText(_translate("CameraGUI", "Every n sec"))