'''
Created on 11 mai 2017

@author: saldenisov
'''
from _functools import partial

from PyQt5.Qt import QMainWindow
from PyQt5.QtGui import QCloseEvent

from utilities.meta.meta import Meta
from utilities.observers.observers import MObserver
from views.ui.main_widget_2_0 import Ui_MainWindow


class Mview(QMainWindow, MObserver, metaclass=Meta):
    """
    """

    def __init__(self, in_controller, in_model, parent=None):
        """

        """
        super(QMainWindow, self).__init__(parent)
        self.controller = in_controller
        self.model = in_model

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.model.add_observer(self)

        self.ui.actionHelp.triggered.connect(self.controller.help_clicked)
        self.ui.actionAuthor.triggered.connect(self.controller.author_clicked)
        self.ui.actionQuit.triggered.connect(partial(self.controller.quit_clicked, event=QCloseEvent()))
        self.ui.actionSettings.triggered.connect(self.controller.settings_clicked)

        self.ui.DLButton.clicked.connect(self.controller.connect_stpmtrctrl)

    def test(self):
        print(1)

    def model_is_changed(self):
        self.ui.setvalues(self.model.get)

    def closeEvent(self, event):
        self.controller.quit_clicked(event)