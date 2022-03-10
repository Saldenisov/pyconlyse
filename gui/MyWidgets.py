from PyQt5 import QtWidgets, QtCore


class MyQLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal(str)

    def __init__(self, *args):
        super(MyQLabel, self).__init__(*args)
        self.border = False
        self.style = ''
        self.update_style()

    def mousePressEvent(self, ev):
        if not self.border:
            self.border = True
        else:
            self.border = False

        self.update_style(self.style)
        self.clicked.emit(self.text())

    def update_style(self, style=''):
        self.style = style
        if self.border:
            color = 'green'
        else:
            color = 'black'
        extra = f"border: 1px solid {color};"

        self.setStyleSheet(f'{self.style}; {extra}')


