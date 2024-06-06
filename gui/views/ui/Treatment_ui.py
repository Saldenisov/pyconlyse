import matplotlib
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import *
from matplotlib.widgets import Cursor, RectangleSelector
from gui.views.matplotlib_canvas.DataCanvases import DataCanvas
from gui.views.matplotlib_canvas.KineticsCanvases import KineticsCanvas, KineticsAverage
from gui.views.matplotlib_canvas.SpectrumCanvases import SpectrumCanvas
from gui.views import RangeSlider
from gui.models.ClientGUIModels import TreatmentModel
matplotlib.use("Qt5Agg")

class Ui_GraphWindow:

    def setupUi(self, window, data_folder: Path, parameters=None):
        self.data_folder = data_folder
        self.inParameters = parameters
        self.parent = window

        window.setObjectName("GraphWindow")
        window.setGeometry(600, 50, 200, 400)
        window.resize(1240, 950)
        self.main_widget = QtWidgets.QWidget(window)
        self.main_widget.setObjectName("main_widget")

        self.main_widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.groupbox_Control = QGroupBox(self.main_widget)
        self.groupbox_DATA = QGroupBox(self.main_widget)
        self.groupbox_Kinetics = QGroupBox(self.main_widget)
        self.groupbox_Spectrum = QGroupBox(self.main_widget)

        self.canvas_settings()
        self.cursors_settings()
        self.sliders_settings()

        self.RS = RectangleSelector(self.datacanvas.axis,
                                    window.controller.data_cursor_update,
                                    #drawtype='box',
                                    useblit=True,
                                    button=[1, 3],
                                    minspanx=5,
                                    minspany=5,
                                    spancoords='pixels')
        self.main_settings()

        self.main_widget.setFocus()
        window.setCentralWidget(self.main_widget)

    def redraw_file_tree(self, data_folder: Path):
        self.data_folder = data_folder
        root = str(data_folder)
        self.tree_model.setRootPath(root)
        self.tree.setRootIndex(self.tree_model.index(root))

    def main_settings(self):
        # Buttons
        self.button_calc = QPushButton('Calculate Abs')
        self.button_calc.setMaximumWidth(100)
        self.button_save_result = QPushButton('Save')
        self.button_save_result.setMaximumWidth(100)
        self.button_average_noise = QPushButton('Average Noise')
        self.button_left = QPushButton('<')
        self.button_right = QPushButton('>')
        self.button_play = QPushButton('Play')
        self.button_set_folder = QPushButton('Set Main Folder')
        self.button_get_kinetics = QPushButton('Get Kinetics')
        self.button_get_spectra = QPushButton('Get Spectra')

        # Comboboxes
        self.combobox_type_exp = QComboBox()
        self.combobox_type_exp.setMaximumWidth(150)
        self.combobox_files_selected = QComboBox()
        self.combobox_files_selected.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        for item in TreatmentModel.ExpDataStruct:
            if item.value != 'NOISE':
                self.combobox_type_exp.addItem(item.value)

        self.combobox_type_exp.setCurrentIndex(2)

        # Checkboxes
        self.checkbox_first_img_with_pulse = QCheckBox('First with Pulse?')
        self.checkbox_first_img_with_pulse.setChecked(True)
        self.checkbox_noise_averaged = QCheckBox('Averaged')
        self.checkbox_noise_averaged.setChecked(False)

        # GroupBoxes
        groupbox_control_buttons = QGroupBox()
        groupbox_tree_files = QGroupBox()

        # LineEdit
        self.lineedit_data_set = QLineEdit()
        self.lineedit_noise_set = QLineEdit()
        self.lineedit_save_folder = QLineEdit()
        self.lineedit_save_folder.setText(str(self.data_folder))
        self.lineedit_save_file_name = QLineEdit()
        self.lineedit_kinetics_ranges = QLineEdit()
        self.lineedit_spectra_ranges = QLineEdit()

        # Labels
        self.label_data = QtWidgets.QLabel('Data')
        self.label_noise = QtWidgets.QLabel('Noise')

        # ProgressBars
        self.progressbar_calc = QProgressBar()
        self.progressbar_calc.setMinimum(0)
        self.progressbar_calc.setMaximum(100)
        self.progressbar_calc.setValue(0)

        # RadioButtons
        self.radiobutton_individual = QRadioButton(text='Individual')
        self.radiobutton_individual.setChecked(True)
        self.radiobutton_averaged = QRadioButton(text='Averaged')
        self.radiobutton_averaged.setChecked(False)

        # Slider
        self.data_slider = QSlider(QtCore.Qt.Horizontal, self.main_widget)
        self.data_slider.setMinimum(0)
        self.data_slider.setMaximum(10)
        self.data_slider.setValue(0)

        # SpinBoxes
        self.spinbox = QSpinBox()
        self.spinbox.setMaximumSize(150, 50)
        self.spinbox.setValue(0)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setMinimumSize(500, 200)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cleaing_tab = QWidget()
        cleaing_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        files_tab = QWidget()
        files_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        info_tab = QWidget()
        info_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        info_tab.setMaximumSize(100, 100)
        selection_tab = QWidget()
        selection_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        selection_tab.setMaximumSize(500, 200)

        self.tabs.addTab(files_tab, 'Files')
        self.tabs.addTab(cleaing_tab, 'Cleaning')
        self.tabs.addTab(info_tab, 'Info')
        self.tabs.addTab(selection_tab, 'Selection Tab')

        # Tree
        root = str(self.data_folder)
        #root = 'D:\\DATA_VD2\\2020\\20200617-RK-940'
        self.tree_model = QtWidgets.QFileSystemModel()
        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.tree_model)
        self.tree_model.setRootPath(root)
        self.tree.setRootIndex(self.tree_model.index(root))
        self.tree.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        # Layouts
        layout_play_button = QtWidgets.QHBoxLayout()
        #
        layout_play_button.addWidget(self.button_left)
        layout_play_button.addWidget(self.button_play)
        layout_play_button.addWidget(self.button_right)
        #

        layout_type_exp = QtWidgets.QHBoxLayout()
        #
        layout_type_exp.addWidget(self.combobox_type_exp)
        layout_type_exp.addWidget(self.checkbox_first_img_with_pulse)
        layout_type_exp.addWidget(self.radiobutton_individual)
        layout_type_exp.addWidget(self.radiobutton_averaged)
        layout_type_exp.addWidget(self.button_average_noise)
        layout_type_exp.addWidget(self.button_calc)

        layout_type_exp.addWidget(self.button_save_result)
        #

        layout_noise = QtWidgets.QHBoxLayout()
        #
        layout_noise_param = QtWidgets.QHBoxLayout()
        layout_noise_param.addWidget(self.label_noise)
        layout_noise_param.addWidget(self.lineedit_noise_set)
        layout_noise.addLayout(layout_noise_param)
        #

        layout_control_buttons = QtWidgets.QVBoxLayout()
        #
        layout_data_buttons = QtWidgets.QHBoxLayout()
        layout_data_buttons.addWidget(self.label_data)
        layout_data_buttons.addWidget(self.lineedit_data_set)

        layout_control_buttons.addWidget(self.combobox_files_selected)
        layout_control_buttons.addLayout(layout_data_buttons)
        layout_control_buttons.addLayout(layout_noise)
        layout_control_buttons.addLayout(layout_type_exp)
        layout_control_buttons.addWidget(self.lineedit_save_folder)
        layout_control_buttons.addWidget(self.lineedit_save_file_name)
        layout_control_buttons.addWidget(self.progressbar_calc)
        layout_control_buttons.addLayout(layout_play_button)
        groupbox_control_buttons.setLayout(layout_control_buttons)  # GroupBox layout
        #

        layout_file_tree = QtWidgets.QVBoxLayout()
        #
        layout_file_tree.addWidget(self.button_set_folder)
        layout_file_tree.addWidget(self.tree)
        groupbox_tree_files.setLayout(layout_file_tree)  # GroupBox tree layout
        #

        layout_Info = QGridLayout()
        #
        #TODO: add stuff
        #

        # CLEANING
        cleaning_box = QGroupBox()

        layout_cleaning = QHBoxLayout()

        layout_cleaning_box = QVBoxLayout()

        layout_cleaning_buttons = QHBoxLayout()
        self.button_calc_sam = QPushButton('Calculate SAM')
        self.button_clean_sam = QPushButton('Clean data')
        self.button_save_clean = QPushButton('Saved clean data')
        self.spinbox_set_angle = QDoubleSpinBox()
        self.spinbox_set_angle.setMinimum(0.05)
        self.spinbox_set_angle.setMaximum(90)
        self.spinbox_set_angle.setValue(1.0)

        self.spinbox_set_surface = QDoubleSpinBox()
        self.spinbox_set_surface.setMinimum(1)
        self.spinbox_set_surface.setMaximum(100)
        self.spinbox_set_surface.setValue(10.0)

        layout_cleaning_buttons.addWidget(self.button_calc_sam)
        layout_cleaning_buttons.addWidget((QLabel('Set threshold angle')))
        layout_cleaning_buttons.addWidget(self.spinbox_set_angle)
        layout_cleaning_buttons.addWidget((QLabel('Set threshold surface, %')))
        layout_cleaning_buttons.addWidget(self.spinbox_set_surface)
        layout_cleaning_buttons.addWidget(self.button_clean_sam)
        layout_cleaning_buttons.addWidget(self.button_save_clean)
        hspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        layout_cleaning_buttons.addItem(hspacer)

        layout_cleaning_box.addLayout(layout_cleaning_buttons)
        self.sam_values = QTextEdit()
        layout_cleaning_box.addWidget(self.sam_values)

        cleaning_box.setLayout(layout_cleaning_box)

        layout_cleaning.addWidget(cleaning_box)
        layout_cleaning.addWidget(self.kinetics_average_canvas)
        cleaing_tab.setLayout(layout_cleaning)

        # SELECTION
        layout_selection = QVBoxLayout()
        #
        layout_selection_kinetics = QHBoxLayout()
        layout_selection_spectra = QHBoxLayout()

        layout_selection_kinetics.addWidget(self.lineedit_kinetics_ranges)
        layout_selection_kinetics.addWidget(self.button_get_kinetics)

        layout_selection_spectra.addWidget(self.lineedit_spectra_ranges)
        layout_selection_spectra.addWidget(self.button_get_spectra)

        layout_selection.addLayout(layout_selection_kinetics)
        layout_selection.addLayout(layout_selection_spectra)
        selection_tab.setLayout(layout_selection)
        #

        # FILES
        layout_files = QHBoxLayout()
        #
        layout_files.addWidget(groupbox_control_buttons)
        layout_files.addWidget(groupbox_tree_files)
        files_tab.setLayout(layout_files)  # Tab files layout
        #

        layout_data_slider = QtWidgets.QHBoxLayout()
        #
        layout_data_slider.addWidget(self.data_slider)
        layout_data_slider.addWidget(self.spinbox)
        #

        # FINALY layouts
        self.layout_FORM = QtWidgets.QVBoxLayout(self.main_widget)

        self.layout_Kinetics = QtWidgets.QVBoxLayout()
        #
        self.layout_Kinetics.addWidget(self.kineticscanvas)
        self.layout_Kinetics.addWidget(self.kinetics_slider)
        self.groupbox_Kinetics.setLayout(self.layout_Kinetics)  # GroupBox kinetics layout
        #

        self.layout_Spectrum = QtWidgets.QVBoxLayout()
        #
        self.layout_Spectrum.addWidget(self.spectracanvas)
        self.layout_Spectrum.addWidget(self.spectrum_slider)
        self.groupbox_Spectrum.setLayout(self.layout_Spectrum)  # GroupBox spectrum layout
        #

        self.layout_DATA = QtWidgets.QVBoxLayout()
        #
        self.layout_DATA.addWidget(self.datacanvas)
        #self.layout_DATA.addWidget(self.data_colorbar_slider)
        self.layout_DATA.addLayout(layout_data_slider)
        self.groupbox_DATA.setLayout(self.layout_DATA)  # Groupbox datastructures layout
        #
        self.layout_CONTROL = QtWidgets.QHBoxLayout()
        #
        self.layout_CONTROL.addWidget(self.tabs)
        self.groupbox_Control.setLayout(self.layout_CONTROL)  # Groupbox control layout
        #

        # Splitters
        self.splitter_between_graphs = QSplitter(self.main_widget)
        self.splitter_between_graphs.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_between_graphs.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_between_graphs.setOrientation(QtCore.Qt.Vertical)
        #
        self.splitter_between_graphs.addWidget(self.groupbox_Kinetics)
        self.splitter_between_graphs.addWidget(self.groupbox_Spectrum)
        #

        self.splitter_data_graphs_horizontal = QSplitter(self.main_widget)
        self.splitter_data_graphs_horizontal.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_data_graphs_horizontal.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_data_graphs_horizontal.setOrientation(QtCore.Qt.Horizontal)
        #
        self.splitter_data_graphs_horizontal.addWidget(self.groupbox_DATA)
        self.splitter_data_graphs_horizontal.addWidget(self.splitter_between_graphs)
        #

        self.splitter_main_vertical = QSplitter(self.main_widget)
        self.splitter_main_vertical.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_main_vertical.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter_main_vertical.setOrientation(QtCore.Qt.Vertical)
        #
        self.splitter_main_vertical.addWidget(self.splitter_data_graphs_horizontal)
        self.splitter_main_vertical.addWidget(self.groupbox_Control)
        #

        self.layout_FORM.addWidget(self.datacanvas.toolbar)
        self.layout_FORM.addWidget(self.splitter_main_vertical)

    def cursors_settings(self):
        self.cursor_data = Cursor(self.datacanvas.axis, useblit=True, color='black', linewidth=1)

    def canvas_settings(self):
        self.datacanvas = DataCanvas(width=9, height=10, dpi=70, canvas_parent=self.main_widget)

        self.datacanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.kineticscanvas = KineticsCanvas(width=6, height=6, dpi=40, canvas_parent=self.main_widget)

        self.kinetics_average_canvas = KineticsAverage(width=6, height=6, dpi=40, canvas_parent=self.main_widget)

        self.kineticscanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.spectracanvas = SpectrumCanvas(width=6, height=6, dpi=40, canvas_parent=self.main_widget)

        self.spectracanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

    def sliders_settings(self):
        maxY, maxX = self.datacanvas.measurement.data.shape

        self.kinetics_slider = RangeSlider.QRangeSlider(min=0.0, max=maxY, start=10, end=50, size_pixels=1000)
        self.kinetics_slider.setBackgroundStyle('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                                                'stop:0 #222, stop:1 #333);')
        self.kinetics_slider.handle.setStyleSheet('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                                                  'stop:0 #282, stop:1 #393);')

        self.spectrum_slider = RangeSlider.QRangeSlider(min=0.0, max=maxX, start=10, end=50, size_pixels=1300)
        self.spectrum_slider.setBackgroundStyle('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                                                'stop:0 #222, stop:1 #333);')
        self.spectrum_slider.handle.setStyleSheet('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                                                  'stop:0 #282, stop:1 #393);')

        self.data_colorbar_slider = RangeSlider.QRangeSlider(min=self.datacanvas.minv / 2,
                                                             max=self.datacanvas.maxv,
                                                             start=self.datacanvas.minv,
                                                             end=self.datacanvas.maxv,
                                                             size_pixels=500)
        self.data_colorbar_slider.setBackgroundStyle('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                                                     'stop:0 #222, stop:1 #333);')
        self.data_colorbar_slider.handle.setStyleSheet('background: qlineargradient(x1:0, y1:0, x2:0, y2:1, '
                                                       'stop:0 #282, stop:1 #393);')


class Ui_GraphVD2Window_(object):

    def setupUi(self, window: QMainWindow, parameters=None):
        self.inParameters = parameters
        self.main_widget = QWidget(window)

        self.layout_form = QtWidgets.QVBoxLayout(self.main_widget)
        self.layout_data = QtWidgets.QHBoxLayout()
        self.layout_tree = QtWidgets.QVBoxLayout()

        self.datacanvas = DataCanvas(width=6, height=5, dpi=70, canvas_parent=None)

        root = 'C:\\dev\\DATA\\'
        self.tree_model = QtWidgets.QFileSystemModel()
        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.tree_model)
        self.tree_model.setRootPath(root)
        self.tree.setRootIndex(self.tree_model.index(root))
        self.tree.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)

        self.layout_data.addWidget(self.datacanvas)
        self.layout_tree.addWidget(self.tree)
        self.layout_form.addLayout(self.layout_data)
        self.layout_form.addLayout(self.layout_tree)

        self.main_widget.setFocus()
        window.setCentralWidget(self.main_widget)
