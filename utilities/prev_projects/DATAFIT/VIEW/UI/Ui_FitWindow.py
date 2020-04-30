from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QSplitter,
                             QGroupBox, QPushButton, QDoubleSpinBox,
                             QComboBox, QLineEdit,
                             QTableWidget, QHeaderView,
                             QRadioButton, QVBoxLayout)

from prev_projects.DATAFIT.VIEW.CANVAS import FitCanvas
import matplotlib
matplotlib.use("Qt5Agg")


class Ui_FitWindow(object):
    def setupUi(self, fitview):
        self.fitmodel = fitview.model
        self.variables = fitview.model.parameters['variables']
        self.model = fitview.model.parameters['fitmodel']
        self.file_path = fitview.model.parameters['filepath']
        self.method = fitview.model.parameters['method']

        fitview.setObjectName("fitview")
        fitview.resize(1240, 800)
        self.main_widget = QtWidgets.QWidget(fitview)
        self.main_widget.setObjectName("main_widget")

        self.main_widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.main_widget.setWindowTitle("3DGraph")

        self.canvas_settings()
        self.main_settings()

        self.retranslateUi(fitview)

        self.main_widget.setFocus()
        fitview.setCentralWidget(self.main_widget)

    def main_settings(self):
        self.layout_FORM = QtWidgets.QHBoxLayout(self.main_widget)
        self.splitter_MAIN = QSplitter()

        self.splitter_MAIN.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_MAIN.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_MAIN.setOrientation(QtCore.Qt.Horizontal)
        self.layout_FIT = QtWidgets.QVBoxLayout()
        self.layout_CONTROL = QtWidgets.QVBoxLayout()
        self.layout_PARAMETERS = QtWidgets.QVBoxLayout()

        self.layout_lin_log_X = QtWidgets.QVBoxLayout()
        self.layout_lin_log_Y = QtWidgets.QVBoxLayout()
        self.layout_normalisation = QtWidgets.QVBoxLayout()

        self.layout_FIT.addWidget(self.fitcanvas.toolbar)
        self.layout_FIT.addWidget(self.fitcanvas)

        self.groupbox_FIT = QGroupBox(self.main_widget)
        self.groupbox_FIT.setLayout(self.layout_FIT)

        self.groupbox_CONTROLS = QGroupBox(self.main_widget)

        self.groupbox_CONTROLS.setLayout(self.layout_CONTROL)
        self.groupbox_lin_log_X = QGroupBox(self.main_widget)
        self.groupbox_lin_log_X.setTitle('lin/log X')
        self.groupbox_lin_log_X.setLayout(self.layout_lin_log_X)

        self.groupbox_lin_log_Y = QGroupBox(self.main_widget)
        self.groupbox_lin_log_Y.setTitle('lin/log Y')
        self.groupbox_lin_log_Y.setLayout(self.layout_lin_log_Y)

        self.groupbox_Norm_Real = QGroupBox(self.main_widget)
        self.groupbox_Norm_Real.setTitle('Norm.')
        self.groupbox_Norm_Real.setLayout(self.layout_normalisation)

        self.groupbox_PARAMETERS = QGroupBox(self.main_widget)
        self.groupbox_PARAMETERS.setLayout(self.layout_PARAMETERS)

        self.button_FIT = QPushButton('Fit')
        self.button_SAVE = QPushButton('Save')

        self.layout_CONTROL.addWidget(self.groupbox_lin_log_X)
        self.layout_CONTROL.addWidget(self.groupbox_lin_log_Y)
        self.layout_CONTROL.addWidget(self.groupbox_Norm_Real)
        self.layout_CONTROL.addWidget(self.button_FIT)
        self.layout_CONTROL.addWidget(self.button_SAVE)

        self.radiobutton_X_log = QRadioButton()
        self.radiobutton_X_log.setText('logX')
        self.radiobutton_X_lin = QRadioButton()
        self.radiobutton_X_lin.setText('X')
        self.radiobutton_X_lin.setChecked(True)

        self.radiobutton_Y_log = QRadioButton()
        self.radiobutton_Y_log.setText('logY')
        self.radiobutton_Y_lin = QRadioButton()
        self.radiobutton_Y_lin.setText('Y')
        self.radiobutton_Y_lin.setChecked(True)

        self.radiobutton_Norm = QRadioButton()
        self.radiobutton_Norm.setText('Norm.')
        self.radiobutton_Real = QRadioButton()
        self.radiobutton_Real.setText('Real')
        self.radiobutton_Norm.setChecked(True)

        self.layout_lin_log_X.addWidget(self.radiobutton_X_lin)
        self.layout_lin_log_X.addWidget(self.radiobutton_X_log)

        self.layout_lin_log_Y.addWidget(self.radiobutton_Y_lin)
        self.layout_lin_log_Y.addWidget(self.radiobutton_Y_log)

        self.layout_normalisation.addWidget(self.radiobutton_Norm)
        self.layout_normalisation.addWidget(self.radiobutton_Real)

        self.table_paramerters = QTableWidget()
        self.table_paramerters.setGeometry(QtCore.QRect(500, 500, 431, 161))
        self.table_paramerters.resize(500, 250)

        Header = ['Variables', 'Guess', 'Range', 'Fit']
        self.table_paramerters.setColumnCount(len(Header))
        self.table_paramerters.setRowCount(len(self.variables))
        self.table_paramerters.setHorizontalHeaderLabels(Header)
        self.table_paramerters.setObjectName("table_param")

        self.table_var_map = {}
        j = 0
        for i in self.variables:

            # model column
            line = QLineEdit(str(j + 1) + '-' + i)
            line.setDisabled(True)
            line.setFixedWidth(60)
            line.setAlignment(QtCore.Qt.AlignCenter)
            self.table_paramerters.setCellWidget(j, 0, line)

            # Guess Column
            guess = QDoubleSpinBox()
            self.table_var_map[i + 'guess'] = guess
            guess.setRange(-999999, 999999)
            guess.setFixedWidth(80)
            self.table_paramerters.setCellWidget(j, 1, guess)
            guess.setAlignment(QtCore.Qt.AlignCenter)

            # Range column
            layout_cell = QVBoxLayout()
            groupbox_cell = QGroupBox()
            groupbox_cell.setLayout(layout_cell)
            _min = QDoubleSpinBox()
            _min.setFixedWidth(80)
            self.table_var_map[i + 'min'] = _min
            _min.setRange(-999999, 999999)

            _max = QDoubleSpinBox()
            self.table_var_map[i + 'max'] = _max
            _max.setRange(-999999, 999999)
            _max.setFixedWidth(80)
            layout_cell.addWidget(_min)
            layout_cell.addWidget(_max)
            self.table_paramerters.setCellWidget(j, 2, groupbox_cell)
            # self.table_paramerters.item(j,2).setTextAlignment(QtCore.Qt.AlignCenter)

            # Fit column
            line = QLineEdit('')
            line.setFixedWidth(80)
            line.setAlignment(QtCore.Qt.AlignCenter)
            self.table_var_map[i + 'fit'] = line

            line.setDisabled(True)
            self.table_paramerters.setCellWidget(j, 3, line)
            # self.table_paramerters.item(j,3).setTextAlignment(QtCore.Qt.AlignCenter)

            j += 1
        # print(self.table_var_map)
        self.table_paramerters.resizeColumnsToContents()
        self.table_paramerters.resizeRowsToContents()
        header = self.table_paramerters.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self.combobox_Method = QComboBox()
        self.combobox_Method.setMaximumWidth(150)
        self.combobox_Method.addItem('dogbox')
        self.combobox_Method.addItem('trf')
        self.combobox_Method.addItem('lm')

        index = 0

        for i in range(self.combobox_Method.count()):
            if self.combobox_Method.itemText(i) == self.method:
                index = i

        self.combobox_Method.setCurrentIndex(index)

        self.layout_PARAMETERS.addWidget(self.table_paramerters)
        self.layout_PARAMETERS.addWidget(self.combobox_Method)

        self.splitter_MAIN.addWidget(self.groupbox_FIT)
        self.splitter_MAIN.addWidget(self.groupbox_CONTROLS)
        self.splitter_MAIN.addWidget(self.groupbox_PARAMETERS)

        self.splitter_MAIN.setStretchFactor(0, 1)
        self.splitter_MAIN.setStretchFactor(1, 0)
        self.splitter_MAIN.setStretchFactor(2, 1)

        self.splitter_MAIN.setSizes([150, 100, 100])
        self.layout_FORM.addWidget(self.splitter_MAIN)

    def canvas_settings(self):
        self.fitcanvas = FitCanvas(self.main_widget,
                                   width=8,
                                   height=8,
                                   dpi=110,
                                   LP=self.main_widget,
                                   fitmodel=self.fitmodel)
        self.fitcanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

    def retranslateUi(self, FitWindow):
        _translate = QtCore.QCoreApplication.translate
        fitmodel = ''
        for key, value in self.model.items():
            fitmodel += key + ': ' + str(value) + '; '
        fitmodel = fitmodel[:-1]
        FitWindow.setWindowTitle(_translate("FitWindow", "Fit Window: " + fitmodel + self.file_path))
