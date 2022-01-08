# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Motors_widget.ui'
#
# Created by: PyQt5 UI code generator 5.13.0
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_StepMotorsWidgetWindow(object):
    def setupUi(self, stepmotorswidget):
        stepmotorswidget.setObjectName("MotorswidgetWindow")
        stepmotorswidget.resize(732, 560)
        font = QtGui.QFont()
        font.setFamily("MV Boli")
        font.setPointSize(14)
        font.setBold(False)
        font.setItalic(False)
        font.setUnderline(False)
        font.setWeight(50)
        font.setStrikeOut(False)
        font.setStyleStrategy(QtGui.QFont.PreferDefault)
        stepmotorswidget.setFont(font)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("../../icons/motors.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        stepmotorswidget.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(stepmotorswidget)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.listWidget = QtWidgets.QListWidget(self.centralwidget)
        self.listWidget.setObjectName("listWidget")
        self.verticalLayout.addWidget(self.listWidget)
        self.horizontalLayout_buttons = QtWidgets.QHBoxLayout()
        self.horizontalLayout_buttons.setObjectName("horizontalLayout_buttons")
        self.verticalLayout.addLayout(self.horizontalLayout_buttons)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.gridLayout_2.addLayout(self.horizontalLayout, 0, 0, 1, 1)
        stepmotorswidget.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar(stepmotorswidget)
        self.statusbar.setObjectName("statusbar")
        stepmotorswidget.setStatusBar(self.statusbar)
        self.menubar = QtWidgets.QMenuBar(stepmotorswidget)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 732, 21))
        self.menubar.setObjectName("menubar")
        self.menu_sdf = QtWidgets.QMenu(self.menubar)
        self.menu_sdf.setObjectName("menu_sdf")
        self.menu_sd = QtWidgets.QMenu(self.menubar)
        self.menu_sd.setObjectName("menu_sd")
        self.menuMain = QtWidgets.QMenu(self.menubar)
        self.menuMain.setObjectName("menuMain")
        stepmotorswidget.setMenuBar(self.menubar)
        self.actionSettings = QtWidgets.QAction(stepmotorswidget)
        self.actionSettings.setObjectName("actionSettings")
        self.actionHelp = QtWidgets.QAction(stepmotorswidget)
        self.actionHelp.setObjectName("actionHelp")
        self.actionAuthor = QtWidgets.QAction(stepmotorswidget)
        self.actionAuthor.setObjectName("actionAuthor")
        self.actionQuit = QtWidgets.QAction(stepmotorswidget)
        self.actionQuit.setObjectName("actionQuit")
        self.actionLoad = QtWidgets.QAction(stepmotorswidget)
        self.actionLoad.setObjectName("actionLoad")
        self.actionSave_config = QtWidgets.QAction(stepmotorswidget)
        self.actionSave_config.setObjectName("actionSave_config")
        self.actionTest_connections = QtWidgets.QAction(stepmotorswidget)
        self.actionTest_connections.setObjectName("actionTest_connections")
        self.actionStart_connection = QtWidgets.QAction(stepmotorswidget)
        self.actionStart_connection.setObjectName("actionStart_connection")
        self.actionStop_connection = QtWidgets.QAction(stepmotorswidget)
        self.actionStop_connection.setObjectName("actionStop_connection")
        self.menu_sdf.addAction(self.actionSettings)
        self.menu_sdf.addSeparator()
        self.menu_sdf.addAction(self.actionLoad)
        self.menu_sdf.addAction(self.actionSave_config)
        self.menu_sdf.addSeparator()
        self.menu_sdf.addAction(self.actionTest_connections)
        self.menu_sdf.addAction(self.actionStart_connection)
        self.menu_sdf.addAction(self.actionStop_connection)
        self.menu_sd.addAction(self.actionHelp)
        self.menu_sd.addAction(self.actionAuthor)
        self.menuMain.addAction(self.actionQuit)
        self.menubar.addAction(self.menuMain.menuAction())
        self.menubar.addAction(self.menu_sdf.menuAction())
        self.menubar.addAction(self.menu_sd.menuAction())

        self.retranslateUi(stepmotorswidget)
        QtCore.QMetaObject.connectSlotsByName(stepmotorswidget)

    def retranslateUi(self, MotorswidgetWindow):
        _translate = QtCore.QCoreApplication.translate
        MotorswidgetWindow.setWindowTitle(_translate("MotorswidgetWindow", "pytlyse Motors"))
        self.menu_sdf.setTitle(_translate("MotorswidgetWindow", "Tools"))
        self.menu_sd.setTitle(_translate("MotorswidgetWindow", "About"))
        self.menuMain.setTitle(_translate("MotorswidgetWindow", "Main"))
        self.actionSettings.setText(_translate("MotorswidgetWindow", "Settings"))
        self.actionHelp.setText(_translate("MotorswidgetWindow", "Help"))
        self.actionAuthor.setText(_translate("MotorswidgetWindow", "Author"))
        self.actionAuthor.setIconText(_translate("MotorswidgetWindow", "Author"))
        self.actionQuit.setText(_translate("MotorswidgetWindow", "Quit"))
        self.actionQuit.setShortcut(_translate("MotorswidgetWindow", "Ctrl+Q"))
        self.actionLoad.setText(_translate("MotorswidgetWindow", "Load config"))
        self.actionLoad.setShortcut(_translate("MotorswidgetWindow", "Ctrl+L"))
        self.actionSave_config.setText(_translate("MotorswidgetWindow", "Save config"))
        self.actionSave_config.setShortcut(_translate("MotorswidgetWindow", "Ctrl+S"))
        self.actionTest_connections.setText(_translate("MotorswidgetWindow", "Test connections"))
        self.actionStart_connection.setText(_translate("MotorswidgetWindow", "Start connection"))
        self.actionStart_connection.setShortcut(_translate("MotorswidgetWindow", "Shift+S"))
        self.actionStop_connection.setText(_translate("MotorswidgetWindow", "Stop connection"))
        self.actionStop_connection.setShortcut(_translate("MotorswidgetWindow", "Shift+T"))