# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'main_widget_2_0.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!
from os import path

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def __init__(self):
        self.path = path.dirname(path.realpath(__file__))


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
        icon.addPixmap(QtGui.QPixmap(str(self.path)+str("\\")+str("main_icon.jpg")),
                       QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.DLButton = QtWidgets.QPushButton(self.centralwidget)
        self.DLButton.setObjectName("DLButton")
        self.gridLayout_2.addWidget(self.DLButton, 0, 0, 1, 1)
        self.DETButton = QtWidgets.QPushButton(self.centralwidget)
        self.DETButton.setObjectName("DETButton")
        self.gridLayout_2.addWidget(self.DETButton, 1, 0, 1, 1)
        self.CameraButton = QtWidgets.QPushButton(self.centralwidget)
        self.CameraButton.setObjectName("CameraButton")
        self.gridLayout_2.addWidget(self.CameraButton, 3, 0, 1, 1)
        self.DAQmxButton = QtWidgets.QPushButton(self.centralwidget)
        self.DAQmxButton.setObjectName("DAQmxButton")
        self.gridLayout_2.addWidget(self.DAQmxButton, 2, 0, 1, 1)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout_2.addItem(spacerItem, 4, 0, 1, 1)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 408, 26))
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

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "TranPyt-Elyse"))
        self.DLButton.setText(_translate("MainWindow", "Delay Line"))
        self.DETButton.setText(_translate("MainWindow", "Detector"))
        self.CameraButton.setText(_translate("MainWindow", "Camera"))
        self.DAQmxButton.setText(_translate("MainWindow", "DAQmx"))
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

