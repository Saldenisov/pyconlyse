import matplotlib
matplotlib.use("Qt5Agg")
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QSplitter,
                             QGroupBox, QPushButton)


class Ui_GraphsWindow(object):

    def setupUi(self, GraphsWindow):

        self.parent = GraphsWindow

        GraphsWindow.setObjectName("GraphsWindow")
        GraphsWindow.setGeometry(600, 50, 200, 400)
        GraphsWindow.resize(1240, 900)
        self.main_widget = QtWidgets.QWidget(GraphsWindow)
        self.main_widget.setObjectName("main_widget")

        self.main_widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.main_widget.setWindowTitle("3DGraph")


        self.canvas_settings()

        self.main_settings()

        self.main_widget.setFocus()
        GraphsWindow.setCentralWidget(self.main_widget)
        self.retranslateUi(GraphsWindow)

    def main_settings(self):
        self.splitter_MAIN = QSplitter(self.main_widget)
        self.splitter_MAIN.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_MAIN.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_MAIN.setOrientation(QtCore.Qt.Vertical)

        self.layout_FORM = QtWidgets.QVBoxLayout(self.main_widget)
        self.layout_Kinetics = QtWidgets.QVBoxLayout()
        self.layout_Spectrum = QtWidgets.QVBoxLayout()
        self.layout_Buttons = QtWidgets.QVBoxLayout()


        #self.layout_Kinetics.addWidget(self.kineticscanvas)
        #self.layout_Spectrum.addWidget(self.spectracanvas)

        self.groupbox_Buttons = QGroupBox()
        self.groupbox_Kinetics = QGroupBox()
        self.groupbox_Spectrum = QGroupBox()

        self.groupbox_Buttons.setLayout(self.layout_Buttons)
        self.groupbox_Kinetics.setLayout(self.layout_Kinetics)
        self.groupbox_Spectrum.setLayout(self.layout_Spectrum)

        self.button_Del = QPushButton('Delete')
        self.layout_Buttons.addWidget(self.button_Del)

        self.splitter_MAIN.addWidget(self.groupbox_Kinetics)
        self.splitter_MAIN.addWidget(self.groupbox_Spectrum)
        self.layout_FORM.addWidget(self.splitter_MAIN)
        self.layout_FORM.addWidget(self.groupbox_Buttons)

    def canvas_settings(self):
        pass
        #self.kineticscanvas = KineticsCanvas(self.main_widget, width=6, height=6, dpi=50, LP=None, datastructures=self.All_Data[0], timedelay=self.All_Data[1], cursors=self.All_Data[5])
        #self.spectracanvas = SpectrumCanvas(self.main_widget, width=6, height=6, dpi=50, LP=None, datastructures=self.All_Data[0], wavelength=self.All_Data[2], cursors=self.All_Data[5])

    def retranslateUi(self, view):
        _translate = QtCore.QCoreApplication.translate
        view.setWindowTitle(_translate(
            "GraphsWindow", "Graphs Window "))
