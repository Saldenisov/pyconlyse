from taurus.external.qt import QtGui  # Replace with the appropriate GUI toolkit import
from taurus.qt.qtgui.base import TaurusBaseWidget
class MyCustomWidget(TaurusBaseWidget):
    def __init__(self, parent=None):
        super(MyCustomWidget, self).__init__(parent)
        # Your widget initialization code here
        self.initUI()

    def initUI(self):
        # Add and configure your GUI elements here
        layout = QtGui.QVBoxLayout()
        label = QtGui.QLabel("Custom Widget")
        button = QtGui.QPushButton("Click Me")
        layout.addWidget(label)
        layout.addWidget(button)
        self.setLayout(layout)

from taurus.qt.qtgui.application import TaurusApplication

import sys

from PyQt5 import QtWidgets
if __name__ == '__main__':
    app = TaurusApplication(sys.argv)

    panel = QtWidgets.QWidget()
    panel.setWindowTitle('PYCONLYSE')

    my_widget = MyCustomWidget()
    my_widget.show()
    sys.exit(app.exec_())
