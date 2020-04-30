from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QVBoxLayout,
                             QHBoxLayout, QTreeView,
                             QFileSystemModel, QSplitter,
                             QListWidget, QGroupBox,
                             QPushButton)


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, root='D:\\'):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setGeometry(50, 50, 200, 400)
        MainWindow.resize(640, 680)
        self.main_widget = QtWidgets.QWidget(MainWindow)
        self.main_widget.setObjectName("main_widget")
        MainWindow.setCentralWidget(self.main_widget)

        self.layout_MAIN = QVBoxLayout(self.main_widget)
        self.layout_Tree = QVBoxLayout()
        self.layout_bottom = QHBoxLayout()
        self.layout_list = QVBoxLayout()
        self.layout_control = QVBoxLayout()

        self.groupbox_bottom = QGroupBox(self.main_widget)
        self.groupbox_bottom.setLayout(self.layout_bottom)
        self.groupbox_control = QGroupBox(self.main_widget)
        self.groupbox_control.setLayout(self.layout_control)

        self.button_Up = QPushButton('Up')
        self.button_Down = QPushButton('Down')
        self.button_Del = QPushButton('Delete')
        self.button_Graphs = QPushButton('Graphs')

        self.layout_control.addWidget(self.button_Up)
        self.layout_control.addWidget(self.button_Down)
        self.layout_control.addWidget(self.button_Del)
        self.layout_control.addWidget(self.button_Graphs)

        self.list_Files = QListWidget()
        self.list_Files.setSelectionMode(QListWidget.ExtendedSelection)

        self.layout_bottom.addWidget(self.list_Files)
        self.layout_bottom.addWidget(self.groupbox_control)

        self.splitter_MAIN = QSplitter(self.main_widget)
        self.splitter_MAIN.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_MAIN.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_MAIN.setOrientation(QtCore.Qt.Vertical)

        self.tree_model = QFileSystemModel()

        self.tree = QTreeView(self.splitter_MAIN)
        self.tree.setModel(self.tree_model)
        self.tree_model.setRootPath(root)

        self.tree.setRootIndex(self.tree_model.index(root))

        self.tree.header().hideSection(1)  # Hide "size" column
        self.tree.header().hideSection(2)  # Hide "type" column
        self.tree.header().resizeSection(0, 450)
        self.tree.header().resizeSection(3, 50)
        self.tree.setSelectionMode(QTreeView.ExtendedSelection)

        self.splitter_MAIN.addWidget(self.groupbox_bottom)
        self.layout_MAIN.addWidget(self.splitter_MAIN)

        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 640, 22))
        self.menubar.setObjectName("menubar")
        self.menuMain = QtWidgets.QMenu(self.menubar)
        self.menuMain.setObjectName("menuMain")
        self.menuTools = QtWidgets.QMenu(self.menubar)
        self.menuTools.setObjectName("menuTools")
        self.menuAbout = QtWidgets.QMenu(self.menubar)
        self.menuAbout.setObjectName("menuAbout")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionOpen = QtWidgets.QAction(MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.actionSave = QtWidgets.QAction(MainWindow)
        self.actionSave.setObjectName("actionSave")
        self.actionSave_as = QtWidgets.QAction(MainWindow)
        self.actionSave_as.setObjectName("actionSave_as")
        self.actionQuite = QtWidgets.QAction(MainWindow)
        self.actionQuite.setObjectName("actionQuite")
        self.actionQuite.setShortcut('Ctrl+Q')
        self.actionSettings = QtWidgets.QAction(MainWindow)
        self.actionSettings.setObjectName("actionSettings")
        self.actionDir = QtWidgets.QAction(MainWindow)
        self.actionDir.setObjectName("actionDir")
        self.actionHelp = QtWidgets.QAction(MainWindow)
        self.actionHelp.setObjectName("actionHelp")
        self.actionAuthor = QtWidgets.QAction(MainWindow)
        self.actionAuthor.setObjectName("actionAuthor")
        self.menuMain.addAction(self.actionOpen)
        self.menuMain.addAction(self.actionSave)
        self.menuMain.addAction(self.actionSave_as)
        self.menuMain.addAction(self.actionQuite)
        self.menuTools.addAction(self.actionSettings)
        self.menuTools.addAction(self.actionDir)
        self.menuAbout.addSeparator()
        self.menuAbout.addAction(self.actionHelp)
        self.menuAbout.addAction(self.actionAuthor)
        self.menubar.addAction(self.menuMain.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuAbout.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        QSplitter.setSizes(self.splitter_MAIN, [500, 200])

    def retranslateUi(self, FitWindow):
        _translate = QtCore.QCoreApplication.translate
        FitWindow.setWindowTitle(_translate("FitWindow", "DATAFIT"))

        self.menuMain.setTitle(_translate("FitWindow", "Main"))
        self.menuTools.setTitle(_translate("FitWindow", "Tools"))
        self.menuAbout.setTitle(_translate("FitWindow", "About"))
        self.actionOpen.setText(_translate("FitWindow", "Open"))
        self.actionSave.setText(_translate("FitWindow", "Save"))
        self.actionSave_as.setText(_translate("FitWindow", "Save as"))
        self.actionQuite.setText(_translate("FitWindow", "Quit"))
        self.actionSettings.setText(_translate("FitWindow", "Settings"))
        self.actionDir.setText(_translate("FitWindow", "Dir"))
        self.actionHelp.setText(_translate("FitWindow", "Help"))
        self.actionAuthor.setText(_translate("FitWindow", "Author"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    window.show()
    sys.exit(app.exec_())
