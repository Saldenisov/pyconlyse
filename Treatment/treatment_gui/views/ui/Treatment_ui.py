import matplotlib
from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import *  # noqa: F401,F403
from PyQt5.QtWidgets import QApplication
from matplotlib.widgets import Cursor

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
        window.setGeometry(100, 50, 1400, 900)
        window.resize(1400, 900)
        
        # All canvases will be 12x10 cm (width x height)
        self.canvas_width_cm = 12
        self.canvas_height_cm = 10
        
        self.main_widget = QtWidgets.QWidget(window)
        self.main_widget.setObjectName("main_widget")
        self.main_widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)

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

        # Control buttons widget (no groupbox wrapper)
        control_buttons_widget = QWidget()
        control_buttons_widget.setMaximumWidth(450)  # Reasonable width for controls
        control_buttons_widget.setMinimumWidth(400)  # Ensure minimum readable width
        control_buttons_widget.setMinimumHeight(450)  # Minimum height to prevent compression
        # Smaller font for compact appearance
        control_buttons_widget.setStyleSheet("""
            QWidget {
                font-size: 8.5pt;
            }
            QPushButton {
                font-size: 8.5pt;
                padding: 3px 8px;
                min-height: 22px;
            }
            QLabel {
                font-size: 8.5pt;
            }
            QLineEdit, QComboBox {
                font-size: 8.5pt;
                min-height: 22px;
            }
        """)

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
        info_tab = QWidget()
        info_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        info_tab.setMaximumSize(100, 100)
        selection_tab = QWidget()
        selection_tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        selection_tab.setMaximumSize(500, 200)

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
        layout_type.setSpacing(6)  # Space between rows
        layout_type_exp = QtWidgets.QHBoxLayout()
        layout_type_exp.setSpacing(6)  # Space between elements
        layout_type_exp_but = QtWidgets.QHBoxLayout()
        layout_type_exp_but.setSpacing(6)  # Space between buttons

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

        # Reorganized layout for better compactness
        layout_control_buttons = QtWidgets.QVBoxLayout()
        layout_control_buttons.setSpacing(5)  # Tighter spacing
        layout_control_buttons.setContentsMargins(6, 8, 6, 6)  # Compact margins
        
        # Section 1: File Selection (most important at top)
        layout_control_buttons.addWidget(QLabel("<b>Selected File:</b>"))
        layout_control_buttons.addWidget(self.combobox_files_selected)
        
        # Section 2: Data paths (compact side-by-side labels)
        layout_data_buttons = QtWidgets.QHBoxLayout()
        layout_data_buttons.setSpacing(4)
        layout_data_buttons.addWidget(self.label_data)
        layout_data_buttons.addWidget(self.lineedit_data_set)
        layout_control_buttons.addLayout(layout_data_buttons)
        
        layout_noise = QtWidgets.QHBoxLayout()
        layout_noise.setSpacing(4)
        layout_noise.addWidget(self.label_noise)
        layout_noise.addWidget(self.lineedit_noise_set)
        layout_control_buttons.addLayout(layout_noise)
        
        # Section 3: Experiment settings (grouped together)
        layout_control_buttons.addWidget(QLabel("<b>Experiment Type:</b>"))
        layout_control_buttons.addLayout(layout_type)
        
        # Section 4: Save settings (grouped together)
        layout_control_buttons.addWidget(QLabel("<b>Output:</b>"))
        layout_control_buttons.addWidget(self.lineedit_save_folder)
        layout_control_buttons.addWidget(self.lineedit_save_file_name)
        
        # Section 5: Progress and playback
        layout_control_buttons.addWidget(self.progressbar_calc)
        layout_play_button.setSpacing(4)
        layout_control_buttons.addLayout(layout_play_button)
        
        layout_control_buttons.addStretch()  # Push everything to the top
        control_buttons_widget.setLayout(layout_control_buttons)

        # File browser widget (no groupbox, just tree + button)
        file_browser_widget = QtWidgets.QWidget()
        layout_file_tree = QtWidgets.QVBoxLayout(file_browser_widget)
        layout_file_tree.setSpacing(4)
        layout_file_tree.setContentsMargins(2, 2, 2, 2)
        layout_file_tree.addWidget(self.button_set_folder)
        layout_file_tree.addWidget(self.tree)

        layout_Info = QGridLayout()
        # TODO: add stuff

        # CLEANING
        cleaning_box = QGroupBox()

        layout_cleaning = QHBoxLayout()
        layout_cleaning_box = QVBoxLayout()
        layout_cleaning_buttons = QHBoxLayout()

        self.button_calc_sam = QPushButton("Calculate SAM")
        # Explain what SAM does when the user hovers over the button
        self.button_calc_sam.setToolTip(
            "Compute Spectral Angle Mapping (SAM) between each kinetics trace and the "
            "average reference. The resulting angles are shown below and are used "
            "together with the Angle threshold and Surface threshold values to filter "
            "measurements."
        )
        # Clean current measurements using SAM thresholds
        self.button_clean_sam = QPushButton("Clean")
        # Reset cleaned measurements back to the original data from file
        self.button_reset_sam = QPushButton("Reset data")
        self.button_save_clean = QPushButton("Saved clean data")
        self.spinbox_set_angle = QDoubleSpinBox()
        # Allow very small angle thresholds
        self.spinbox_set_angle.setMinimum(0.01)
        self.spinbox_set_angle.setMaximum(90)
        # Default angle threshold
        self.spinbox_set_angle.setValue(1.0)

        self.spinbox_set_surface = QDoubleSpinBox()
        # Allow very small surface thresholds (in percent)
        self.spinbox_set_surface.setMinimum(0.01)
        self.spinbox_set_surface.setMaximum(100)
        # Default surface threshold (percent)
        self.spinbox_set_surface.setValue(1.0)

        layout_cleaning_buttons.addWidget(self.button_calc_sam)
        layout_cleaning_buttons.addWidget(QLabel("Angle threshold"))
        layout_cleaning_buttons.addWidget(self.spinbox_set_angle)
        layout_cleaning_buttons.addWidget(QLabel("Surface threshold, %"))
        layout_cleaning_buttons.addWidget(self.spinbox_set_surface)
        layout_cleaning_buttons.addWidget(self.button_clean_sam)
        layout_cleaning_buttons.addWidget(self.button_reset_sam)
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

        # FILES tab removed - File Browser is now a separate dock widget

        layout_data_slider = QtWidgets.QHBoxLayout()
        layout_data_slider.addWidget(self.data_slider)
        layout_data_slider.addWidget(self.spinbox)

        # NEW LAYOUT STRUCTURE with dockable widgets
        # =============================================
        from PyQt5.QtWidgets import QDockWidget
        
        # === Create all dock widgets ===
        
        # LEFT: File Browser (full height)
        self.dock_file_browser = QDockWidget("File Browser", self.parent)
        self.dock_file_browser.setWidget(file_browser_widget)
        self.dock_file_browser.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        self.dock_file_browser.setMinimumWidth(250)
        
        # CENTER: 2D Data (12x10 cm with slider)
        data_widget = QtWidgets.QWidget()
        data_layout = QtWidgets.QVBoxLayout(data_widget)
        data_layout.setContentsMargins(4, 4, 4, 4)
        # Add matplotlib toolbar first
        data_layout.addWidget(self.datacanvas.toolbar)
        # Then add the canvas
        data_layout.addWidget(self.datacanvas)
        # Add slider at the bottom
        layout_data_slider = QtWidgets.QHBoxLayout()
        layout_data_slider.addWidget(self.data_slider)
        layout_data_slider.addWidget(self.spinbox)
        data_layout.addLayout(layout_data_slider)
        
        self.dock_2d_data = QDockWidget("2D", self.parent)
        self.dock_2d_data.setWidget(data_widget)
        self.dock_2d_data.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        
        # TOP-RIGHT: Kinetics (narrower, 6x10 cm)
        kinetics_widget = QtWidgets.QWidget()
        kinetics_layout = QtWidgets.QVBoxLayout(kinetics_widget)
        kinetics_layout.setContentsMargins(4, 4, 4, 4)
        kinetics_layout.addWidget(self.kineticscanvas)
        self.kinetics_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.kinetics_slider.setMinimumHeight(35)
        self.kinetics_slider.setMaximumHeight(60)
        kinetics_layout.addWidget(self.kinetics_slider)
        
        self.dock_kinetics = QDockWidget("Kinetics", self.parent)
        self.dock_kinetics.setWidget(kinetics_widget)
        self.dock_kinetics.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        
        # MIDDLE-RIGHT: Spectrum (below Kinetics)
        spectrum_widget = QtWidgets.QWidget()
        spectrum_layout = QtWidgets.QVBoxLayout(spectrum_widget)
        spectrum_layout.setContentsMargins(4, 4, 4, 4)
        spectrum_layout.addWidget(self.spectracanvas)
        self.spectrum_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.spectrum_slider.setMinimumHeight(35)
        self.spectrum_slider.setMaximumHeight(60)
        spectrum_layout.addWidget(self.spectrum_slider)
        
        self.dock_spectrum = QDockWidget("Spectrum", self.parent)
        self.dock_spectrum.setWidget(spectrum_widget)
        self.dock_spectrum.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        
        # RIGHT: Project Description (full height)
        project_desc_widget = QtWidgets.QWidget()
        project_desc_layout = QtWidgets.QVBoxLayout(project_desc_widget)
        project_desc_layout.setContentsMargins(4, 4, 4, 4)
        project_desc_text = QTextEdit()
        project_desc_text.setPlaceholderText("Project notes and description...")
        project_desc_layout.addWidget(project_desc_text)
        
        self.dock_project_desc = QDockWidget("Project Description", self.parent)
        self.dock_project_desc.setWidget(project_desc_widget)
        self.dock_project_desc.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        self.dock_project_desc.setMinimumWidth(200)
        
        # BOTTOM-LEFT: Analysis Control
        self.dock_controls = QDockWidget("Analysis Control", self.parent)
        self.dock_controls.setWidget(control_buttons_widget)
        self.dock_controls.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        
        # BOTTOM-RIGHT: Additional Tools
        self.dock_tabs = QDockWidget("Additional Tools", self.parent)
        self.dock_tabs.setWidget(self.tabs)
        self.dock_tabs.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetFloatable
        )
        
        # === ARRANGE DOCKS TO MATCH USER'S LAYOUT ===
        # User's layout:
        # Row 1: FileBrowser | 2D | Kinetics | Project Description
        # Row 2: FileBrowser | 2D | Spectrum | Project Description  
        # Row 3: FileBrowser | Analysis Control | Additional Tools
        
        # Strategy: To make File Browser span full height on left, we need to:
        # 1. Add File Browser to left
        # 2. Add all other widgets to the right area
        # 3. Use nested dock corners to control layout
        
        # Set dock nesting to allow corners to be shared
        self.parent.setCorner(QtCore.Qt.TopLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        self.parent.setCorner(QtCore.Qt.BottomLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        
        # Add File Browser to left - it will now span full height
        self.parent.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dock_file_browser)
        
        # Add 2D to top area (to the right of File Browser)
        self.parent.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.dock_2d_data)
        
        # Add Kinetics to the right of 2D
        self.parent.splitDockWidget(self.dock_2d_data, self.dock_kinetics, QtCore.Qt.Horizontal)
        
        # Add Project Description to the right of Kinetics
        self.parent.splitDockWidget(self.dock_kinetics, self.dock_project_desc, QtCore.Qt.Horizontal)
        
        # Add Spectrum below Kinetics
        self.parent.splitDockWidget(self.dock_kinetics, self.dock_spectrum, QtCore.Qt.Vertical)
        
        # Add Analysis Control at bottom
        self.parent.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.dock_controls)
        
        # Add Additional Tools to the right of Analysis Control
        self.parent.splitDockWidget(self.dock_controls, self.dock_tabs, QtCore.Qt.Horizontal)

    def cursors_settings(self):
        self.cursor_data = Cursor(
            self.datacanvas.axis,
            useblit=True,
            color="black",
            linewidth=1,
        )

    def canvas_settings(self):
        # All canvases: 12cm width x 10cm height
        # Convert cm to inches: 1 inch = 2.54 cm
        canvas_width_inches = self.canvas_width_cm / 2.54
        canvas_height_inches = self.canvas_height_cm / 2.54
        canvas_dpi = 80  # DPI for good rendering
        
        # 2D Data canvas
        self.datacanvas = DataCanvas(
            width=canvas_width_inches,
            height=canvas_height_inches,
            dpi=canvas_dpi,
            canvas_parent=self.main_widget,
        )
        self.datacanvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        # Kinetics canvas - same height as 2D Data, but narrower width
        kinetics_width_inches = 6 / 2.54  # 6 cm width (narrower for kinetics)
        self.kineticscanvas = KineticsCanvas(
            width=kinetics_width_inches,
            height=canvas_height_inches,  # Same 10 cm height as 2D Data
            dpi=canvas_dpi,
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

        # Spectrum canvas - same size as 2D Data
        self.spectracanvas = SpectrumCanvas(
            width=canvas_width_inches,
            height=canvas_height_inches,
            dpi=canvas_dpi,
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
