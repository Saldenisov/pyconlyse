from PyQt5.Qt import QMainWindow
from UTILITY.META import Meta
from UTILITY.OBSERVER import GraphsObserver
from VIEW.UI import Ui_GraphsWindow


class GraphsView(QMainWindow, GraphsObserver, metaclass=Meta):
    """
    """

    def __init__(self, inController, in_model, parent=None):
        """
        """
        super(QMainWindow, self).__init__(parent)
        self.graphsController = inController
        self.graphsModel = in_model

        self.ui = Ui_GraphsWindow()
        self.ui.setupUi(self)

        #self.graphsModel.addObserver(self)


    def cursorsChanged(self, file):
        """
        """
        pass

    def closeEvent(self, event):
        pass