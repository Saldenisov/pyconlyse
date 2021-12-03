from PyQt5 import QtWidgets, QtCore


class MyQLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, ev):
        self.clicked.emit()
