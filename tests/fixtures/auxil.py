from pathlib import Path
from PyQt5.QtWidgets import QWidget
from utilities.data.messaging import Message
from gui.views.Test import Ui_TestObserver

app_folder = str(Path(__file__).resolve().parents[2])


class Observer(QWidget):
    #data_changed = pyqtSignal(MessageExt, name='data_observer_changed')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Message = None
        self.ui = Ui_TestObserver()
        self.ui.setupUi(self)
        self.show()

    def update_data(self, mes: Message):
        self.data = Message

a = Observer()






