# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'main_widget.ui'
#
# Created by: PyQt5 UI code generator 5.8.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(408, 400)
        font = QtGui.QFont()
        font.setFamily("MS PGothic")
        font.setPointSize(12)
        font.setBold(True)
        font.setItalic(False)
        font.setUnderline(False)
        font.setWeight(75)
        font.setStrikeOut(False)
        font.setStyleStrategy(QtGui.QFont.PreferDefault)
        MainWindow.setFont(font)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("main_icon.jpg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName("tabWidget")
        self.tabDL = QtWidgets.QWidget()
        self.tabDL.setObjectName("tabDL")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.tabDL)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.textEdit = QtWidgets.QTextEdit(self.tabDL)
        self.textEdit.setObjectName("textEdit")
        self.gridLayout_3.addWidget(self.textEdit, 2, 0, 1, 1)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.groupBox_DL_sliders = QtWidgets.QGroupBox(self.tabDL)
        self.groupBox_DL_sliders.setTitle("")
        self.groupBox_DL_sliders.setObjectName("groupBox_DL_sliders")
        self.gridLayout_5 = QtWidgets.QGridLayout(self.groupBox_DL_sliders)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.horizontalSlider_DL_Y_axis = QtWidgets.QSlider(self.groupBox_DL_sliders)
        self.horizontalSlider_DL_Y_axis.setEnabled(False)
        self.horizontalSlider_DL_Y_axis.setCursor(QtGui.QCursor(QtCore.Qt.UpArrowCursor))
        self.horizontalSlider_DL_Y_axis.setOrientation(QtCore.Qt.Horizontal)
        self.horizontalSlider_DL_Y_axis.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.horizontalSlider_DL_Y_axis.setObjectName("horizontalSlider_DL_Y_axis")
        self.gridLayout_5.addWidget(self.horizontalSlider_DL_Y_axis, 1, 1, 1, 1)
        self.lcdNumber_Xaxis = QtWidgets.QLCDNumber(self.groupBox_DL_sliders)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lcdNumber_Xaxis.sizePolicy().hasHeightForWidth())
        self.lcdNumber_Xaxis.setSizePolicy(sizePolicy)
        self.lcdNumber_Xaxis.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.lcdNumber_Xaxis.setObjectName("lcdNumber_Xaxis")
        self.gridLayout_5.addWidget(self.lcdNumber_Xaxis, 0, 2, 1, 1)
        self.label_mm_lcd_Yaxis = QtWidgets.QLabel(self.groupBox_DL_sliders)
        self.label_mm_lcd_Yaxis.setObjectName("label_mm_lcd_Yaxis")
        self.gridLayout_5.addWidget(self.label_mm_lcd_Yaxis, 1, 3, 1, 1)
        self.horizontalSlider_DL_X_axis = QtWidgets.QSlider(self.groupBox_DL_sliders)
        self.horizontalSlider_DL_X_axis.setEnabled(False)
        self.horizontalSlider_DL_X_axis.setCursor(QtGui.QCursor(QtCore.Qt.UpArrowCursor))
        self.horizontalSlider_DL_X_axis.setMouseTracking(False)
        self.horizontalSlider_DL_X_axis.setOrientation(QtCore.Qt.Horizontal)
        self.horizontalSlider_DL_X_axis.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.horizontalSlider_DL_X_axis.setObjectName("horizontalSlider_DL_X_axis")
        self.gridLayout_5.addWidget(self.horizontalSlider_DL_X_axis, 0, 1, 1, 1)
        self.label_DL_X_axis = QtWidgets.QLabel(self.groupBox_DL_sliders)
        self.label_DL_X_axis.setObjectName("label_DL_X_axis")
        self.gridLayout_5.addWidget(self.label_DL_X_axis, 0, 0, 1, 1)
        self.label_mm_lcd_Xaxis = QtWidgets.QLabel(self.groupBox_DL_sliders)
        self.label_mm_lcd_Xaxis.setObjectName("label_mm_lcd_Xaxis")
        self.gridLayout_5.addWidget(self.label_mm_lcd_Xaxis, 0, 3, 1, 1)
        self.lcdNumber_Yaxis = QtWidgets.QLCDNumber(self.groupBox_DL_sliders)
        self.lcdNumber_Yaxis.setObjectName("lcdNumber_Yaxis")
        self.gridLayout_5.addWidget(self.lcdNumber_Yaxis, 1, 2, 1, 1)
        self.label_DL_Y_axis = QtWidgets.QLabel(self.groupBox_DL_sliders)
        self.label_DL_Y_axis.setObjectName("label_DL_Y_axis")
        self.gridLayout_5.addWidget(self.label_DL_Y_axis, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.groupBox_DL_sliders, 0, 0, 1, 1)
        self.verticalLayout_3.addLayout(self.gridLayout)
        self.progressBar_DL_movement = QtWidgets.QProgressBar(self.tabDL)
        self.progressBar_DL_movement.setProperty("value", 0)
        self.progressBar_DL_movement.setObjectName("progressBar_DL_movement")
        self.verticalLayout_3.addWidget(self.progressBar_DL_movement)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.pushButton_DL_connect = QtWidgets.QPushButton(self.tabDL)
        self.pushButton_DL_connect.setObjectName("pushButton_DL_connect")
        self.horizontalLayout.addWidget(self.pushButton_DL_connect)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout_3.addLayout(self.horizontalLayout)
        self.gridLayout_3.addLayout(self.verticalLayout_3, 0, 0, 1, 1)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap("stepmotors.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.tabWidget.addTab(self.tabDL, icon1, "")
        self.tabSP = QtWidgets.QWidget()
        self.tabSP.setObjectName("tabSP")
        self.gridLayout_4 = QtWidgets.QGridLayout(self.tabSP)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.groupBox_detection_type = QtWidgets.QGroupBox(self.tabSP)
        self.groupBox_detection_type.setObjectName("groupBox_detection_type")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox_detection_type)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.radioButton_UVVIS = QtWidgets.QRadioButton(self.groupBox_detection_type)
        self.radioButton_UVVIS.setObjectName("radioButton_UVVIS")
        self.verticalLayout.addWidget(self.radioButton_UVVIS)
        self.radioButton_IR = QtWidgets.QRadioButton(self.groupBox_detection_type)
        self.radioButton_IR.setObjectName("radioButton_IR")
        self.verticalLayout.addWidget(self.radioButton_IR)
        self.verticalLayout_2.addLayout(self.verticalLayout)
        self.gridLayout_4.addWidget(self.groupBox_detection_type, 0, 0, 1, 1)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout_4.addItem(spacerItem1, 0, 1, 1, 1)
        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout_4.addItem(spacerItem2, 1, 0, 1, 1)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap("spectrometer.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.tabWidget.addTab(self.tabSP, icon2, "")
        self.gridLayout_2.addWidget(self.tabWidget, 0, 0, 1, 1)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 408, 21))
        self.menubar.setObjectName("menubar")
        self.menu_sdf = QtWidgets.QMenu(self.menubar)
        self.menu_sdf.setObjectName("menu_sdf")
        self.menu_sd = QtWidgets.QMenu(self.menubar)
        self.menu_sd.setObjectName("menu_sd")
        self.menuMain = QtWidgets.QMenu(self.menubar)
        self.menuMain.setObjectName("menuMain")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionSettings = QtWidgets.QAction(MainWindow)
        self.actionSettings.setObjectName("actionSettings")
        self.actionHelp = QtWidgets.QAction(MainWindow)
        self.actionHelp.setObjectName("actionHelp")
        self.actionAuthor = QtWidgets.QAction(MainWindow)
        self.actionAuthor.setObjectName("actionAuthor")
        self.actionQuit = QtWidgets.QAction(MainWindow)
        self.actionQuit.setObjectName("actionQuit")
        self.menu_sdf.addAction(self.actionSettings)
        self.menu_sd.addAction(self.actionHelp)
        self.menu_sd.addAction(self.actionAuthor)
        self.menuMain.addAction(self.actionQuit)
        self.menubar.addAction(self.menuMain.menuAction())
        self.menubar.addAction(self.menu_sdf.menuAction())
        self.menubar.addAction(self.menu_sd.menuAction())
        self.label_DL_X_axis.setBuddy(self.horizontalSlider_DL_X_axis)
        self.label_DL_Y_axis.setBuddy(self.horizontalSlider_DL_Y_axis)

        self.retranslateUi(MainWindow)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "TranPyt-Elyse"))
        self.label_mm_lcd_Yaxis.setText(_translate("MainWindow", "mm"))
        self.label_DL_X_axis.setText(_translate("MainWindow", "X - line"))
        self.label_mm_lcd_Xaxis.setText(_translate("MainWindow", "mm"))
        self.label_DL_Y_axis.setText(_translate("MainWindow", "Y - line"))
        self.pushButton_DL_connect.setText(_translate("MainWindow", "Connect to stepmotors"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabDL), _translate("MainWindow", "Delay lines"))
        self.groupBox_detection_type.setTitle(_translate("MainWindow", "Detection"))
        self.radioButton_UVVIS.setText(_translate("MainWindow", "UV-vis"))
        self.radioButton_IR.setText(_translate("MainWindow", "IR"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabSP), _translate("MainWindow", "Spectrometers and Cameras"))
        self.menu_sdf.setTitle(_translate("MainWindow", "Tools"))
        self.menu_sd.setTitle(_translate("MainWindow", "About"))
        self.menuMain.setTitle(_translate("MainWindow", "Main"))
        self.actionSettings.setText(_translate("MainWindow", "Settings"))
        self.actionHelp.setText(_translate("MainWindow", "Help"))
        self.actionAuthor.setText(_translate("MainWindow", "Author"))
        self.actionAuthor.setIconText(_translate("MainWindow", "Author"))
        self.actionQuit.setText(_translate("MainWindow", "Quit"))
        self.actionQuit.setShortcut(_translate("MainWindow", "Ctrl+Q"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

