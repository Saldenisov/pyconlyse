from _functools import partial

from PyQt5.Qt import QMainWindow
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QListWidgetItem
from UTILITY.META import Meta
from UTILITY.OBSERVER import MObserver
from VIEW.UI import Ui_MainWindow


class MView(QMainWindow, MObserver, metaclass=Meta):
    """
    Represents experimental datastructures file selection.
    """

    def __init__(self, inController, in_model, root, parent=None):
        """
        """
        super(QMainWindow, self).__init__(parent)
        self.controller = inController
        self.model = in_model

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self, root)

        self.model.addObserver(self)

        self.ui.tree.doubleClicked.connect(self.controller.tree_doubleclicked)
        self.ui.button_Del.clicked.connect(self.controller.delete_clicked)
        self.ui.button_Up.clicked.connect(self.controller.up_clicked)
        self.ui.button_Down.clicked.connect(self.controller.down_clicked)
        self.ui.list_Files.itemDoubleClicked.connect(self.controller.lfiles_doubleclicked)
        self.ui.actionQuite.triggered.connect(self.controller.quit)
        self.ui.button_Graphs.clicked.connect(self.controller.graphs_clicked)

        self.ui.actionQuite.triggered.connect(partial(self.controller.quit, QCloseEvent()))
        self.ui.actionAuthor.triggered.connect(self.controller.author_clicked)
        self.ui.actionHelp.triggered.connect(self.controller.help_clicked)
        self.ui.actionSettings.triggered.connect(self.controller.settings_clicked)
        self.ui.actionDir.triggered.connect(self.controller.dir_clicked)

    def modelIsChanged(self, file):
        """
        """
        if file:
            self.ui.list_Files.addItem(QListWidgetItem(file))

    def closeEvent(self, event):
        self.controller.quit()
