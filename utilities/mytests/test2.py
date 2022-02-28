from PyQt5 import QtWidgets
import pyqtgraph as pg
import numpy as np
import sys

class MyWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MyWidget, self).__init__(parent)
        self.win = pg.GraphicsWindow()
        self.p = []
        self.c = []
        for i in range(3):
            self.p.append(self.win.addPlot(row=i, col=0))
            for j in range(2):
                self.c.append(self.p[-1].plot(np.random.rand(100), pen=3*i+j))
        # self.update()
        # self.del_curve()
        # self.add_curve()

    def update(self): # update a curve
        self.c[3].setData(np.random.rand(100)*10)

    def del_curve(self): # remove a curve
        self.c[5].clear()

    def add_curve(self): # add a curve
        self.c.append(self.p[2].plot(np.random.rand(100)))

def startWindow():
    app = QtWidgets.QApplication(sys.argv)
    mw = MyWidget()
    app.exec_()

if __name__ == '__main__':
    startWindow()