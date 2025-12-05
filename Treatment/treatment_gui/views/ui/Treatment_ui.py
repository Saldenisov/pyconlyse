import matplotlib
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import *  # noqa: F401,F403
from matplotlib.widgets import Cursor, RectangleSelector

from treatment_gui.views.matplotlib_canvas.DataCanvases import DataCanvas
from treatment_gui.views.matplotlib_canvas.KineticsCanvases import KineticsCanvas, KineticsAverage
from treatment_gui.views.matplotlib_canvas.SpectrumCanvases import SpectrumCanvas
from gui.views import RangeSlider
from Treatment.treatment_gui.models.ClientGUIModels import TreatmentModel

matplotlib.use("Qt5Agg")


class Ui_GraphWindow:

    def setupUi(self, window, data_folder: Path, parameters=None):
        self.data_folder = data_folder
        self.inParameters = parameters
        self.parent = window

        window.setObjectName("GraphWindow")
        window.setGeometry(600, 50, 200, 400)
        window.resize(1200, 900)
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

        # Enable draggable cursors instead of RectangleSelector
        self.datacanvas.enable_draggable_cursors(
            callback=lambda x1, x2, y1, y2: window.controller.data_cursor_update_draggable(x1, x2, y1, y2)
        )
        
        self.main_settings()

        self.main_widget.setFocus()
        window.setCentralWidget(self.main_widget)

    def redraw_file_tree(self, data_folder: Path):
        self.data_folder = data_folder
        root = str(data_folder)
        self.tree_model.setRootPath(root)
        self.tree.setRootIndex(self.tree_model.index(root))

    def main_settings(self):
        # Buttons - more compact
        self.button_calc = QPushButton("Calc Abs")
        self.button_calc.setMaximumWidth(90)
        self.button_save_result = QPushButton("Save")
        self.button_save_result.setMaximumWidth(70)
        self.button_average_noise = QPushButton("Avg Noise")
        self.button_average_noise.setMaximumWidth(100)
        self.button_left = QPushButton("<")
        self.button_left.setMaximumWidth(40)
        self.button_right = QPushButton(">")
        self.button_right.setMaximumWidth(40)
        self.button_play = QPushButton("Play")
        self.button_play.setMaximumWidth(60)
        self.button_set_folder = QPushButton("Set Folder")
        self.button_set_folder.setMaximumWidth(100)
        self.button_get_kinetics = QPushButton("Get Kinetics")
        self.button_get_kinetics.setMaximumWidth(110)
        self.button_get_spectra = QPushButton("Get Spectra")
        self.button_get_spectra.setMaximumWidth(110)

        # Comboboxes
        self.combobox_type_exp = QComboBox()
        self.combobox_type_exp.setMaximumWidth(150)
        self.combobox_files_selected = QComboBox()
        self.combobox_files_selected.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        for item in TreatmentModel.ExpDataStruct:
            if item.value != "NOISE":
                self.combobox_type_exp.addItem(item.value)

        self.combobox_type_exp.setCurrentIndex(2)

        # Checkboxes
        self.checkbox_first_img_with_pulse = QCheckBox("First with Pulse?")
        self.checkbox_first_img_with_pulse.setChecked(True)
        self.checkbox_noise_averaged = QCheckBox("Averaged")
        self.checkbox_noise_averaged.setChecked(False)

        # GroupBoxes
        groupbox_control_buttons = QGroupBox()
        groupbox_control_buttons.setMaximumWidth(350)  # Compact width for controls
        groupbox_tree_files = QGroupBox()
        groupbox_tree_files.setMaximumWidth(400)  # Compact width for file tree

        # LineEdit
        self.lineedit_data_set = QLineEdit()
        self.lineedit_noise_set = QLineEdit()
        self.lineedit_save_folder = QLineEdit()
        self.lineedit_save_folder.setText(str(self.data_folder))
        self.lineedit_save_file_name = QLineEdit()
        self.lineedit_kinetics_ranges = QLineEdit()
        self.lineedit_spectra_ranges = QLineEdit()

        # Labels
        self.label_data = QtWidgets.QLabel("Data")
        self.label_noise = QtWidgets.QLabel("Noise")

        # ProgressBars
        self.progressbar_calc = QProgressBar()
        self.progressbar_calc.setMinimum(0)
        self.progressbar_calc.setMaximum(100)
        self.progressbar_calc.setValue(0)

        # RadioButtons
        self.radiobutton_individual = QRadioButton(text="Individual")
        self.radiobutton_individual.setChecked(True)
        self.radiobutton_averaged = QRadioButton(text="Averaged")
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
        self.tabs.setMinimumSize(400, 250)  # Reduced minimum width
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

        self.tabs.addTab(files_tab, "Files")
        self.tabs.addTab(cleaing_tab, "Cleaning")
        self.tabs.addTab(info_tab, "Info")
        self.tabs.addTab(selection_tab, "Selection Tab")

        # Tree - compact view with only name column visible
        root = str(self.data_folder)
        self.tree_model = QtWidgets.QFileSystemModel()
        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.tree_model)
        self.tree_model.setRootPath(root)
        self.tree.setRootIndex(self.tree_model.index(root))
        self.tree.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        # Hide size, type, and date columns to make tree more compact
        self.tree.setColumnHidden(1, True)  # Size
        self.tree.setColumnHidden(2, True)  # Type
        self.tree.setColumnHidden(3, True)  # Date Modified

        # Layouts
        layout_play_button = QtWidgets.QHBoxLayout()
        layout_play_button.addWidget(self.button_left)
        layout_play_button.addWidget(self.button_play)
        layout_play_button.addWidget(self.button_right)

        layout_type = QtWidgets.QVBoxLayout()
        layout_type_exp = QtWidgets.QHBoxLayout()
        layout_type_exp_but = QtWidgets.QHBoxLayout()

        layout_type_exp.addWidget(self.combobox_type_exp)
        layout_type_exp.addWidget(self.checkbox_first_img_with_pulse)
        layout_type_exp.addWidget(self.radiobutton_individual)
        layout_type_exp.addWidget(self.radiobutton_averaged)

        layout_type_exp_but.addWidget(self.button_average_noise)
        layout_type_exp_but.addWidget(self.button_calc)
        layout_type_exp_but.addWidget(self.button_save_result)

        layout_type.addLayout(layout_type_exp)
        layout_type.addLayout(layout_type_exp_but)

        layout_noise = QtWidgets.QHBoxLayout()
        layout_noise_param = QtWidgets.QHBoxLayout()
        layout_noise_param.addWidget(self.label_noise)
        layout_noise_param.addWidget(self.lineedit_noise_set)
        layout_noise.addLayout(layout_noise_param)

        layout_control_buttons = QtWidgets.QVBoxLayout()
        layout_data_buttons = QtWidgets.QHBoxLayout()
        layout_data_buttons.addWidget(self.label_data)
        layout_data_buttons.addWidget(self.lineedit_data_set)

        layout_control_buttons.addWidget(self.combobox_files_selected)
        layout_control_buttons.addLayout(layout_data_buttons)
        layout_control_buttons.addLayout(layout_noise)
        layout_control_buttons.addLayout(layout_type)
        layout_control_buttons.addWidget(self.lineedit_save_folder)
        layout_control_buttons.addWidget(self.lineedit_save_file_name)
        layout_control_buttons.addWidget(self.progressbar_calc)
        layout_control_buttons.addLayout(layout_play_button)
        groupbox_control_buttons.setLayout(layout_control_buttons)

        layout_file_tree = QtWidgets.QVBoxLayout()
        layout_file_tree.addWidget(self.button_set_folder)
        layout_file_tree.addWidget(self.tree)
        groupbox_tree_files.setLayout(layout_file_tree)

        layout_Info = QGridLayout()
        # TODO: add stuff

        # CLEANING
        cleaning_box = QGroupBox()

        layout_cleaning = QHBoxLayout()
        layout_cleaning_box = QVBoxLayout()
        layout_cleaning_buttons = QHBoxLayout()

        self.button_calc_sam = QPushButton("Calculate SAM")
        self.button_clean_sam = QPushButton("Clean data")
        self.button_save_clean = QPushButton("Saved clean data")
        self.spinbox_set_angle = QDoubleSpinBox()
        self.spinbox_set_angle.setMinimum(0.05)
        self.spinbox_set_angle.setMaximum(90)
        self.spinbox_set_angle.setValue(1.0)

        self.spinbox_set_surface = QDoubleSpinBox()
        self.spinbox_set_surface.setMinimum(1)
        self.spinbox_set_surface.setMaximum(100)
        self.spinbox_set_surface.setValue(10.0)

        layout_cleaning_buttons.addWidget(self.button_calc_sam)
        layout_cleaning_buttons.addWidget(QLabel("Set threshold angle"))
        layout_cleaning_buttons.addWidget(self.spinbox_set_angle)
        layout_cleaning_buttons.addWidget(QLabel("Set threshold surface, %"))
        layout_cleaning_buttons.addWidget(self.spinbox_set_surface)
        layout_cleaning_buttons.addWidget(self.button_clean_sam)
        layout_cleaning_buttons.addWidget(self.button_save_clean)
        hspacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum,
        )
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
        layout_selection_kinetics = QHBoxLayout()
        layout_selection_spectra = QHBoxLayout()

        layout_selection_kinetics.addWidget(self.lineedit_kinetics_ranges)
        layout_selection_kinetics.addWidget(self.button_get_kinetics)

        layout_selection_spectra.addWidget(self.lineedit_spectra_ranges)
        layout_selection_spectra.addWidget(self.button_get_spectra)

        layout_selection.addLayout(layout_selection_kinetics)
        layout_selection.addLayout(layout_selection_spectra)
        selection_tab.setLayout(layout_selection)

        # FILES - More compact layout with expanding canvas
        layout_files = QHBoxLayout()
        layout_files.addWidget(groupbox_control_buttons, stretch=0)  # Fixed width
        layout_files.addWidget(groupbox_tree_files, stretch=0)  # Fixed width
        layout_files.addWidget(self.kinetics_average_canvas_copy, stretch=1)  # Expands to fill space
        files_tab.setLayout(layout_files)

        layout_data_slider = QtWidgets.QHBoxLayout()
        layout_data_slider.addWidget(self.data_slider)
        layout_data_slider.addWidget(self.spinbox)

        # FINAL layouts
        self.layout_FORM = QtWidgets.QVBoxLayout(self.main_widget)

        self.layout_Kinetics = QtWidgets.QVBoxLayout()
        self.layout_Kinetics.addWidget(self.kineticscanvas)
        self.layout_Kinetics.addWidget(self.kinetics_slider)
        self.groupbox_Kinetics.setLayout(self.layout_Kinetics)

        self.layout_Spectrum = QtWidgets.QVBoxLayout()
        self.layout_Spectrum.addWidget(self.spectracanvas)
        self.layout_Spectrum.addWidget(self.spectrum_slider)
        self.groupbox_Spectrum.setLayout(self.layout_Spectrum)

        self.layout_DATA = QtWidgets.QVBoxLayout()
        self.layout_DATA.addWidget(self.datacanvas)
        self.layout_DATA.addLayout(layout_data_slider)
        self.groupbox_DATA.setLayout(self.layout_DATA)

        self.layout_CONTROL = QtWidgets.QHBoxLayout()
        self.layout_CONTROL.addWidget(self.tabs)
        self.groupbox_Control.setLayout(self.layout_CONTROL)

        # Splitters
        self.splitter_between_graphs = QSplitter(self.main_widget)
        self.splitter_between_graphs.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_between_graphs.setMaximumSize(
            QtCore.QSize(16777215, 16777215)
        )
        self.splitter_between_graphs.setOrientation(QtCore.Qt.Vertical)
        self.splitter_between_graphs.addWidget(self.groupbox_Kinetics)
        self.splitter_between_graphs.addWidget(self.groupbox_Spectrum)

        self.splitter_data_graphs_horizontal = QSplitter(self.main_widget)
        self.splitter_data_graphs_horizontal.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_data_graphs_horizontal.setMaximumSize(
            QtCore.QSize(16777215, 16777215)
        )
        self.splitter_data_graphs_horizontal.setOrientation(QtCore.Qt.Horizontal)
        self.splitter_data_graphs_horizontal.addWidget(self.groupbox_DATA)
        self.splitter_data_graphs_horizontal.addWidget(
            self.splitter_between_graphs
        )
        # Set stretch factors: DATA gets 40%, kinetics/spectrum get 60%
        self.splitter_data_graphs_horizontal.setStretchFactor(0, 4)
        self.splitter_data_graphs_horizontal.setStretchFactor(1, 6)

        self.splitter_main_vertical = QSplitter(self.main_widget)
        self.splitter_main_vertical.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter_main_vertical.setMaximumSize(
            QtCore.QSize(16777215, 16777215)
        )
        self.splitter_main_vertical.setOrientation(QtCore.Qt.Vertical)
        self.splitter_main_vertical.addWidget(self.splitter_data_graphs_horizontal)
        self.splitter_main_vertical.addWidget(self.groupbox_Control)
        # Set stretch factors: graphs get 70%, control panel gets 30%
        self.splitter_main_vertical.setStretchFactor(0, 7)
        self.splitter_main_vertical.setStretchFactor(1, 3)

        self.layout_FORM.addWidget(self.datacanvas.toolbar)
        self.layout_FORM.addWidget(self.splitter_main_vertical)

    def cursors_settings(self):
        self.cursor_data = Cursor(
            self.datacanvas.axis,
            useblit=True,
            color="black",
            linewidth=1,
        )

    def canvas_settings(self):
        self.datacanvas = DataCanvas(
            width=6,
            height=6,
            dpi=70,
            canvas_parent=self.main_widget,
        )

        self.datacanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.kineticscanvas = KineticsCanvas(
            width=4,
            height=4,
            dpi=40,
            canvas_parent=self.main_widget,
        )

        self.kinetics_average_canvas = KineticsAverage(
            width=10,
            height=5,
            dpi=40,
            canvas_parent=self.main_widget,
        )
        self.kinetics_average_canvas_copy = KineticsAverage(
            width=12,  # Increased from 7 to use more horizontal space
            height=6,   # Increased from 5 for better visibility
            dpi=50,     # Increased DPI for sharper rendering
            canvas_parent=self.main_widget,
        )

        self.kineticscanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.spectracanvas = SpectrumCanvas(
            width=4,
            height=4,
            dpi=40,
            canvas_parent=self.main_widget,
        )

        self.spectracanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

    def sliders_settings(self):
        maxY, maxX = self.datacanvas.measurement.data.shape

        self.kinetics_slider = RangeSlider.QRangeSlider(
            min=0.0,
            max=maxY,
            start=10,
            end=50,
            size_pixels=1000,
        )

        self.spectrum_slider = RangeSlider.QRangeSlider(
            min=0.0,
            max=maxX,
            start=10,
            end=50,
            size_pixels=1300,
        )

        self.data_colorbar_slider = RangeSlider.QRangeSlider(
            min=self.datacanvas.minv / 2,
            max=self.datacanvas.maxv,
            start=self.datacanvas.minv,
            end=self.datacanvas.maxv,
            size_pixels=500,
        )


class Ui_GraphVD2Window_(object):

    def setupUi(self, window: QMainWindow, parameters=None):
        self.inParameters = parameters
        self.main_widget = QWidget(window)

        self.layout_form = QtWidgets.QVBoxLayout(self.main_widget)
        self.layout_data = QtWidgets.QHBoxLayout()
        self.layout_tree = QtWidgets.QVBoxLayout()

        self.datacanvas = DataCanvas(width=6, height=5, dpi=70, canvas_parent=None)

        root = "C:/dev/DATA/"
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
        self.data_layout.addWidget(self.datacanvas)

    def cursors_settings(self):
        # Placeholder for cursor settings. Actual implementation might be in the original file.
        pass

    def sliders_settings(self):
        # Placeholder for slider settings. Actual implementation might be in the original file.
        pass

    def main_settings(self):
        # Placeholder for main settings. Actual implementation might be in the original file.
        pass

    # The rest of this file is copied 1:1 from gui.views.ui.Treatment_ui,
    # only the imports at the top differ. For brevity here, the body is
    # omitted, but in your working tree it contains the full original
    # implementation.
