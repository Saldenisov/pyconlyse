import matplotlib
matplotlib.use("Qt5Agg")

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QSizePolicy,
                             QTabWidget,
                             QWidget,
                             QGridLayout,
                             QSplitter,
                             QGroupBox,
                             QPushButton,
                             QComboBox,
                             QListWidget,
                             QCheckBox)
from matplotlib.widgets import Cursor, RectangleSelector
from prev_projects.DATAFIT.VIEW.CANVAS import DataCanvas, KineticsCanvas, SpectrumCanvas
from prev_projects.DATAFIT.VIEW import RangeSlider


class Ui_GraphWindow(object):

    def setupUi(self, fitview, parameters=None):
        self.inParameters = parameters
        self.parent = fitview
        try:
            self.model = fitview.model
            self.file_path = self.model.filepath
        except:
            self.model = None
            self.file_path = ''
        fitview.setObjectName("GraphWindow")
        fitview.setGeometry(600, 50, 200, 400)
        fitview.resize(1240, 900)
        self.main_widget = QtWidgets.QWidget(fitview)
        self.main_widget.setObjectName("main_widget")

        self.main_widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.main_widget.setWindowTitle("3DGraph")

        self.groupbox_Control = QGroupBox(self.main_widget)
        self.groupbox_DATA = QGroupBox(self.main_widget)
        self.groupbox_Kinetics = QGroupBox(self.main_widget)
        self.groupbox_Spectrum = QGroupBox(self.main_widget)

        self.canvas_settings()
        self.cursors_settings()
        # self.table_settings()
        self.sliders_settings()

        self.RS = RectangleSelector(self.datacanvas.dataplot,
                                    fitview.controller.onselectrect,
                                    drawtype='box',
                                    useblit=True,
                                    button=[1, 3],
                                    minspanx=5,
                                    minspany=5,
                                    spancoords='pixels')
        self.main_settings()

        self.main_widget.setFocus()
        fitview.setCentralWidget(self.main_widget)
        self.retranslateUi(fitview)

    def main_settings(self):
        self.splitter_MAIN = QSplitter(self.main_widget)
        self.splitter_MAIN.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_MAIN.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_MAIN.setOrientation(QtCore.Qt.Vertical)

        self.splitter_main = QSplitter(self.main_widget)
        self.splitter_main.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_main.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_main.setOrientation(QtCore.Qt.Horizontal)

        self.splitter_additional = QSplitter(self.main_widget)
        self.splitter_additional.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_additional.setMaximumSize(
            QtCore.QSize(16777215, 16777215))
        self.splitter_additional.setOrientation(QtCore.Qt.Vertical)

        groupbox_Fit_buttons = QGroupBox()
        groupbox_Fit_list = QGroupBox()
        groupbox_Method = QGroupBox()

        self.tabs = QTabWidget()
        self.tabs.setMinimumSize(500, 200)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        save_tab = QWidget()
        save_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        save_tab.setMaximumSize(100, 100)
        fit_tab = QWidget()
        fit_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        info_tab = QWidget()
        info_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        info_tab.setMaximumSize(100, 100)

        self.button_Fit = QPushButton('Fit')
        self.button_Fit.setMaximumWidth(100)
        self.button_Delete = QPushButton('Delete')
        self.button_Delete.setMaximumWidth(100)
        self.button_Save = QPushButton('Save')
        self.button_Save.setMaximumWidth(100)

        self.combobox_Fit = QComboBox()
        self.combobox_Fit.setMaximumWidth(150)
        self.combobox_Method = QComboBox()
        self.combobox_Method.setMaximumWidth(150)
        self.combobox_Method.addItem('dogbox')
        self.combobox_Method.addItem('trf')
        self.combobox_Method.addItem('lm')
        self.checkbox_pulse = QCheckBox('Pulse')
        self.checkbox_constrained = QCheckBox('Constrained')
        self.checkbox_conv = QCheckBox('Convolution')

        if self.inParameters:
            for model in self.inParameters['Models']:
                self.combobox_Fit.addItem(model)
            self.combobox_Fit.setCurrentIndex(int(
                self.inParameters['ModelPreselected']))
            self.checkbox_pulse.setChecked(bool(self.inParameters['pulse']))
            self.checkbox_constrained.setChecked(bool(
                self.inParameters['Constrained']))
            self.checkbox_conv.setChecked(bool(self.inParameters['Convolution']))

        else:
            self.combobox_Fit.addItem('1exp')
            self.combobox_Fit.addItem('2exp')
            self.combobox_Fit.addItem('Stretched exp')
            self.combobox_Fit.addItem('DistFRET_Gaussian')
            self.combobox_Fit.setCurrentIndex(0)
            self.checkbox_pulse.setChecked(True)
            self.checkbox_constrained.setChecked(False)
            self.checkbox_conv.setChecked(True)

        self.tabs.addTab(fit_tab, 'Fit')
        self.tabs.addTab(save_tab, 'Save')
        self.tabs.addTab(info_tab, 'Info')

        layout_Save = QGridLayout()
        layout_FIT = QtWidgets.QHBoxLayout()
        layout_Fit_buttons = QtWidgets.QVBoxLayout()
        layout_Fit_list = QtWidgets.QVBoxLayout()
        layout_Method = QtWidgets.QVBoxLayout()
        layout_Info = QGridLayout()

        layout_Fit_buttons.addWidget(self.button_Fit)
        layout_Fit_buttons.addWidget(self.button_Delete)
        layout_Fit_buttons.addWidget(self.combobox_Fit)
        layout_Fit_buttons.addWidget(self.checkbox_pulse)
        layout_Fit_buttons.addWidget(self.checkbox_constrained)
        layout_Fit_buttons.addWidget(self.checkbox_conv)

        groupbox_Fit_buttons.setLayout(layout_Fit_buttons)

        self.list_fits = QListWidget()
        self.list_fits.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_fits.setMinimumSize(250, 150)

        layout_Fit_list.addWidget(self.list_fits)
        groupbox_Fit_list.setLayout(layout_Fit_list)

        layout_Method.addWidget(self.combobox_Method)

        groupbox_Method.setLayout(layout_Method)

        layout_Save.addWidget(self.button_Save, 0, 0)
        # layout_Info.addWidget(self.table,0,0)

        save_tab.setLayout(layout_Save)

        layout_FIT.addWidget(groupbox_Fit_buttons)
        layout_FIT.addWidget(groupbox_Fit_list)
        layout_FIT.addWidget(groupbox_Method)
        fit_tab.setLayout(layout_FIT)

        self.layout_FORM = QtWidgets.QVBoxLayout(self.main_widget)

        self.layout_Kinetics = QtWidgets.QVBoxLayout()
        self.layout_Spectrum = QtWidgets.QVBoxLayout()

        self.layout_DATA = QtWidgets.QVBoxLayout()
        self.layout_CONTROL = QtWidgets.QHBoxLayout()

        self.layout_Kinetics.addWidget(self.kineticscanvas)
        self.layout_Kinetics.addWidget(self.kinetics_slider)
        self.layout_Spectrum.addWidget(self.spectracanvas)
        self.layout_Spectrum.addWidget(self.spectrum_slider)

        self.groupbox_Kinetics.setLayout(self.layout_Kinetics)
        self.groupbox_Spectrum.setLayout(self.layout_Spectrum)

        self.splitter_additional.addWidget(self.groupbox_Kinetics)
        self.splitter_additional.addWidget(self.groupbox_Spectrum)

        self.layout_DATA.addWidget(self.datacanvas)
        self.layout_DATA.addWidget(self.data_colorbar_slider)
        self.groupbox_DATA.setLayout(self.layout_DATA)

        self.splitter_main.addWidget(self.groupbox_DATA)
        self.splitter_main.addWidget(self.splitter_additional)

        self.layout_CONTROL.addWidget(self.tabs)
        self.groupbox_Control.setLayout(self.layout_CONTROL)

        self.splitter_MAIN.addWidget(self.splitter_main)
        self.splitter_MAIN.addWidget(self.groupbox_Control)

        self.layout_FORM.addWidget(self.datacanvas.toolbar)
        self.layout_FORM.addWidget(self.splitter_MAIN)

    def cursors_settings(self):
        self.cursor_data = Cursor(
            self.datacanvas.dataplot, useblit=True, color='black', linewidth=1)

    def table_settings(self):
        self.table = QtWidgets.QTableWidget(self.main_widget)
        self.table.setGeometry(QtCore.QRect(50, 70, 431, 161))
        self.table.setRowCount(4)
        self.table.setColumnCount(5)
        self.table.setObjectName("table")
        self.table.setHorizontalHeaderLabels(['N', 'button', 'X', 'Y'])
        self.table.horizontalHeader().setCascadingSectionResizes(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def canvas_settings(self):
        self.datacanvas = DataCanvas(self.main_widget,
                                     width=12,
                                     height=6,
                                     dpi=70,
                                     LP=self.main_widget, 
                                     data_model=self.model,
                                     figure_name=None)

        self.datacanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.kineticscanvas = KineticsCanvas(self.main_widget,
                                             width=6,
                                             height=6,
                                             dpi=40,
                                             LP=None,
                                             data_model=self.model)

        self.kineticscanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.spectracanvas = SpectrumCanvas(self.main_widget,
                                            width=6,
                                            height=6,
                                            dpi=40,
                                            LP=None,
                                            data_model=self.model)

        self.spectracanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

    def sliders_settings(self):
        cursors = self.model.cursors
        maxY, maxX = self.model.data.shape

        self.kinetics_slider = RangeSlider.QRangeSlider(min=0.0,
                                                        max=maxY,
                                                        start=cursors['y1'],
                                                        end=cursors['y2'],
                                                        size_pixels=300)
        self.kinetics_slider.setBackgroundStyle(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #222, stop:1 #333);')
        self.kinetics_slider.handle.setStyleSheet(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #282, stop:1 #393);')

        self.spectrum_slider = RangeSlider.QRangeSlider(min=0.0,
                                                        max=maxX,
                                                        start=cursors['x1'],
                                                        end=cursors['x2'],
                                                        size_pixels=300)
        self.spectrum_slider.setBackgroundStyle(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #222, stop:1 #333);')
        self.spectrum_slider.handle.setStyleSheet(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #282, stop:1 #393);')

        self.data_colorbar_slider = RangeSlider.QRangeSlider(min=self.datacanvas.minv,
                                                             max=self.datacanvas.maxv,
                                                             start=self.datacanvas.minv,
                                                             end=self.datacanvas.maxv,
                                                             size_pixels=500)
        self.data_colorbar_slider.setBackgroundStyle(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #222, stop:1 #333);')
        self.data_colorbar_slider.handle.setStyleSheet(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #282, stop:1 #393);')

    def retranslateUi(self, view):
        _translate = QtCore.QCoreApplication.translate
        view.setWindowTitle(_translate(
            "GraphWindow", "Graph Window " + self.file_path))



if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    ui = Ui_GraphWindow()
    ui.setupUi(window)
    window.show()
    sys.exit(app.exec_())