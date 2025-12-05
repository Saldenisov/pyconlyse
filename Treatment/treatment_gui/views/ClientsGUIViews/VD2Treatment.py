"""Forked Treatment view for the Treatment GUI.

Copied from ``gui.views.ClientsGUIViews.VD2Treatment`` and adjusted to
use the forked Treatment GUI models and UI.
"""

from __future__ import annotations

import logging
from _functools import partial

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QCheckBox, QLineEdit, QProgressBar, QMenu

from gui.controllers.openers import CriticalInfoHamamatsu
from Treatment.treatment_gui.models.ClientGUIModels import TreatmentModel
from Treatment.treatment_gui.views.ui import Ui_GraphWindow
from utilities.datastructures.mes_independent.measurments_dataclass import (
    Measurement,
    Cursors2D,
)
from utilities.myfunc import info_msg

module_logger = logging.getLogger(__name__)


ExpDataStruct: TreatmentModel.ExpDataStruct = TreatmentModel.ExpDataStruct
DataTypes: TreatmentModel.DataTypes = TreatmentModel.DataTypes


class TreatmentView(QMainWindow):

    def __init__(self, in_controller, parent=None):
        super().__init__(parent)
        self.controller = in_controller
        self.name = "VD2Treatment:view"
        self.logger = logging.getLogger("VD2Treatment")

        # Window branding / style
        self.setWindowTitle("Streak-camera data treatment")

        # Window icon: use the existing streak_camera.jpg located at
        #   Treatment/treatment_gui/resources/streak_camera.jpg
        try:
            from pathlib import Path

            # This file lives in Treatment/treatment_gui/views/ClientsGUIViews,
            # so parents[3] is Treatment/ and resources/ is directly below that.
            icon_path = (
                Path(__file__).resolve().parents[3]
                / "resources"
                / "sumo.svg"
            )
            module_logger.info(f"Window icon path resolved to: {icon_path}")
            if icon_path.is_file():
                module_logger.info("Window icon file found; setting window icon.")
                self.setWindowIcon(QIcon(str(icon_path)))
            else:
                module_logger.warning("Window icon file not found; using default icon.")
        except Exception:  # noqa: BLE001
            # Icon is purely cosmetic; ignore any errors.
            pass

        # High-tech Protoss-inspired theme with lighter background and
        # easy-to-read fonts while keeping blue control outlines.
        self.setStyleSheet(
            """
            * {
                font-family: "Segoe UI", Arial, Helvetica, sans-serif;
                font-size: 10pt;
            }

            QMainWindow {
                background-color: #e9edf5;  /* light, slightly blue-neutral */
                color: #0f172a;
            }

            QWidget {
                background-color: #edf1fa;
                color: #0f172a;
                selection-background-color: #1b6fff;
            }

            QGroupBox {
                border: 1px solid #2b8bff;  /* keep blue outline */
                border-radius: 4px;
                margin-top: 6px;
                background-color: #f5f7ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                color: #1f2937;
                font-weight: 600;
            }

            QPushButton {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #2b8bff;
                border-radius: 3px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #dbeafe;
            }
            QPushButton:pressed {
                background-color: #bfdbfe;
            }

            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #2b8bff;  /* blue outline preserved */
                color: #0f172a;
                selection-background-color: #1b6fff;
            }

            QTabBar::tab {
                background: #e5e7eb;
                color: #111827;
                padding: 4px 12px;
            }
            QTabBar::tab:selected {
                background: #bfdbfe;
                border-bottom: 2px solid #1d4ed8;
            }

            QTreeView, QTableView {
                background-color: #ffffff;
                alternate-background-color: #f3f4f6;
                gridline-color: #93c5fd;
            }

            QMenuBar {
                background-color: #e5e7eb;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 8px;
                color: #111827;
            }
            QMenuBar::item:selected {
                background: #dbeafe;
            }

            QMenu {
                background-color: #ffffff;
                border: 1px solid #2b8bff;
            }
            QMenu::item:selected {
                background-color: #dbeafe;
            }

            QSlider::groove:horizontal {
                border: 1px solid #2b8bff;
                height: 6px;
                background: #e5e7eb;
            }
            QSlider::handle:horizontal {
                background: #1d4ed8;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }

            QProgressBar {
                border: 1px solid #2b8bff;
                border-radius: 3px;
                text-align: center;
                background: #e5e7eb;
                color: #111827;
            }
            QProgressBar::chunk {
                background-color: #1d4ed8;
            }
            """
        )

        info_msg(self, "INITIALIZING")

        self.ui = Ui_GraphWindow()
        self.ui.setupUi(self, data_folder=in_controller.model.data_folder)

        # Top menu: add a simple Settings menu with an entry to edit
        # Treatment/config.json (data folder and other options).
        settings_menu = self.menuBar().addMenu("Settings")
        action_edit_config = settings_menu.addAction("Edit config.json…")
        action_edit_config.triggered.connect(self.controller.open_config_file)

        self.controller.model.add_measurement_observer(self)
        self.controller.model.add_ui_observer(self)
        self.controller.model.progressbar = self.ui.progressbar_calc

        self.ui.data_slider.valueChanged.connect(self.controller.slider_map_selector_change)
        self.ui.button_average_noise.clicked.connect(self.controller.average_noise)
        self.ui.button_calc.clicked.connect(self.controller.calc_abs)
        self.ui.button_left.clicked.connect(partial(self.map_step, -1))
        self.ui.button_play.clicked.connect(self.button_play_maps)
        self.ui.button_right.clicked.connect(partial(self.map_step, 1))
        self.ui.button_save_result.clicked.connect(self.controller.save)
        self.ui.button_get_kinetics.clicked.connect(partial(self.controller.get_average, "kinetics"))
        self.ui.button_get_spectra.clicked.connect(partial(self.controller.get_average, "spectra"))
        self.ui.kinetics_slider.ValueChanged.connect(self.controller.slider_kinetics)
        self.ui.spectrum_slider.ValueChanged.connect(self.controller.slider_spectra)
        self.ui.button_set_folder.clicked.connect(self.controller.data_folder_changed)
        self.ui.lineedit_save_file_name.returnPressed.connect(self.controller.save_file_path_changed)
        self.ui.lineedit_save_folder.returnPressed.connect(self.controller.save_file_folder_changed)
        self.ui.spinbox.valueChanged.connect(self.controller.spinbox_map_selector_change)
        self.ui.combobox_type_exp.currentIndexChanged.connect(self._combobox_index_change)
        self.ui.tree.customContextMenuRequested.connect(self.menuContextTree)
        self.ui.combobox_files_selected.customContextMenuRequested.connect(self.menuContextComboBoxFiles)
        self.ui.combobox_files_selected.currentIndexChanged.connect(self.controller.combobox_files_changed)
        self.ui.button_calc_sam.clicked.connect(self.controller.calc_sam)
        self.ui.button_clean_sam.clicked.connect(self.controller.clean_his_sam)
        self.ui.button_save_clean.clicked.connect(self.controller.save_clean_h5)
        info_msg(self, "INITIALIZED")

    def menuContextComboBoxFiles(self, point) -> None:
        menu = QMenu()
        action_remove_this = menu.addAction("Remove This")
        action_remove_all = menu.addAction("Remove All")

        action = menu.exec_(self.ui.combobox_files_selected.mapToGlobal(point))

        if action:
            if action == action_remove_all:
                self.ui.combobox_files_selected.clear()
            elif action == action_remove_this:
                idx = self.ui.combobox_files_selected.currentIndex()
                self.ui.combobox_files_selected.removeItem(idx)

    def menuContextTree(self, point) -> None:
        index = self.ui.tree.indexAt(point)
        if not index.isValid():
            return
        
        # Get file path and extension
        file_path = Path(self.ui.tree.model().filePath(index))
        is_cleanable = file_path.suffix.lower() in ['.h5', '.his', '.img']

        menu = QMenu()
        action_set_ABS = action_set_BASE = action_set_NOISE = action_set_DATA_HIS = action_set_DATA_NOISE_HIS = None
        action_clean_sam = None
        action_plus = menu.addAction("Add file")
        
        # Add SAM cleaning option for .h5 and .his/.img files
        if is_cleanable:
            action_clean_sam = menu.addAction("Clean with SAM (Spectral Angle Mapping)")
            menu.addSeparator()
        if ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.ABS_BASE_NOISE:
            action_set_ABS = menu.addAction("set ABS HIS or IMG")
            action_set_BASE = menu.addAction("set BASE HIS or IMG")
            action_set_NOISE = menu.addAction("set NOISE HIS or IMG")
        elif ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.HIS_NOISE:
            action_set_DATA_HIS = menu.addAction("set ABS+BASE HIS")
            action_set_NOISE = menu.addAction("set NOISE HIS or IMG")
        elif ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.HIS:
            action_set_DATA_NOISE_HIS = menu.addAction("set ABS+BASE+NOISE HIS")

        action = menu.exec_(self.ui.tree.mapToGlobal(point))

        if action:
            if action == action_clean_sam:
                self.controller.clean_file_with_sam(index)
            elif action == action_set_NOISE:
                self.controller.set_path(index, DataTypes.NOISE)
            elif action == action_set_ABS:
                self.controller.set_path(index, DataTypes.ABS)
            elif action == action_set_BASE:
                self.controller.set_path(index, DataTypes.BASE)
            elif action == action_set_DATA_HIS:
                self.controller.set_path(index, DataTypes.ABS_BASE)
            elif action == action_set_DATA_NOISE_HIS:
                self.controller.set_path(index, DataTypes.ABS_BASE_NOISE)
            elif action == action_plus:
                idx = self.ui.tree.selectedIndexes()[0]
                file_path = self.ui.tree.model().filePath(idx)
                chk = []
                combox_l = self.ui.combobox_files_selected.count()
                for i in range(combox_l):
                    if file_path != self.ui.combobox_files_selected.itemText(i):
                        chk.append(True)
                    else:
                        chk.append(False)
                        break
                if all(chk):
                    self.ui.combobox_files_selected.addItem(file_path)
                    self.ui.combobox_files_selected.setCurrentIndex(combox_l)

    def _combobox_index_change(self) -> None:
        if ExpDataStruct(self.ui.combobox_type_exp.currentText()) is ExpDataStruct.ABS_BASE_NOISE:
            self.ui.radiobutton_individual.setDisabled(True)
            self.ui.radiobutton_averaged.setChecked(True)
            self.ui.checkbox_first_img_with_pulse.setDisabled(True)
        else:
            self.ui.radiobutton_individual.setDisabled(False)
            self.ui.checkbox_first_img_with_pulse.setDisabled(False)
            self.ui.radiobutton_individual.setChecked(True)

    def map_step(self, dir: int) -> None:
        value_now = int(self.ui.spinbox.value())
        self.ui.spinbox.setValue(value_now + dir)

    def f(self) -> None:
        from time import sleep

        for i in range(1, 500):
            self.ui.spinbox.setValue(i)
            sleep(0.2)

    def button_play_maps(self) -> None:
        from threading import Thread

        t = Thread(target=self.f)
        t.start()

    def fileQuit(self) -> None:
        self.close()

    def closeEvent(self, ce) -> None:  # noqa: N802, D401
        self.fileQuit()

    def modelIsChanged_ui(self, ui: dict) -> None:
        for name, value in ui.items():
            widget = getattr(self.ui, name)
            if isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QLineEdit):
                if name not in ["lineedit_save_folder"]:
                    if name == "lineedit_save_file_name":
                        short_value = [value]
                        value = self.ui.lineedit_save_folder.text() + "\\" + value
                    if not isinstance(value, list):
                        value = [value]
                    for val in value:
                        chk = []
                        for i in range(self.ui.combobox_files_selected.count()):
                            if val != self.ui.combobox_files_selected.itemText(i):
                                chk.append(True)
                            else:
                                chk.append(False)
                                break
                        if all(chk):
                            self.ui.combobox_files_selected.addItem(val)
                    if name != "lineedit_save_file_name":
                        widget.setText("; ".join(value))
                    else:
                        widget.setText("; ".join(short_value))

            elif isinstance(widget, QProgressBar):
                widget.setValue(int(value[0] / value[1] * 100))

    def modelIsChanged(
        self,
        measurement: Measurement,
        map_index: int,
        critical_info: CriticalInfoHamamatsu | None = None,
        new: bool = False,
        cursors: Cursors2D | None = None,
    ) -> None:
        self.ui.spinbox.setValue(map_index)
        self.ui.data_slider.setValue(map_index)
        if new:
            self.ui.data_slider.setMaximum(critical_info.number_maps - 1)  # type: ignore[union-attr]
            self.ui.spinbox.setMaximum(critical_info.number_maps - 1)  # type: ignore[union-attr]
            self.ui.datacanvas.new_data(measurement, cursors, map_index)
            self.ui.kineticscanvas.new_data(measurement, cursors)
            self.ui.kinetics_average_canvas.new_data(critical_info)  # type: ignore[arg-type]
            self.ui.kinetics_average_canvas_copy.new_data(critical_info)  # type: ignore[arg-type]
            self.update_kinetics_slider(critical_info.timedelays_length - 1, cursors)  # type: ignore[union-attr]
            self.ui.spectracanvas.new_data(measurement, cursors)
            self.update_spectrum_slider(critical_info.wavelengths_length - 1, cursors)  # type: ignore[union-attr]
        else:
            self.ui.datacanvas.update_data(measurement, cursors=cursors, map_index=map_index)
            self.ui.kineticscanvas.update_data(measurement, cursors=cursors)
            self.ui.spectracanvas.update_data(measurement, cursors=cursors)
        if cursors:
            self.ui.datacanvas.draw_cursors(cursors=cursors, draw=True)
            self.ui.kineticscanvas.draw_cursors(cursors=cursors, draw=True)
            self.ui.spectracanvas.draw_cursors(cursors=cursors, draw=True)
            self.update_kinetics_slider(cursors=cursors)
            self.update_spectrum_slider(cursors=cursors)

    def update_kinetics_slider(self, maxValue: int = -1, cursors: Cursors2D | None = None) -> None:  # noqa: N803
        self.ui.kinetics_slider.setStart(int(cursors.y1[0]))  # type: ignore[union-attr]
        self.ui.kinetics_slider.setEnd(int(cursors.y2[0]))  # type: ignore[union-attr]
        if maxValue > 0:
            self.ui.kinetics_slider.setMax(maxValue)
        self.ui.kinetics_slider.update_Sliderpos()

    def update_spectrum_slider(self, maxValue: int = -1, cursors: Cursors2D | None = None) -> None:  # noqa: N803
        self.ui.spectrum_slider.setStart(int(cursors.x1[0]))  # type: ignore[union-attr]
        self.ui.spectrum_slider.setEnd(int(cursors.x2[0]))  # type: ignore[union-attr]
        if maxValue > 0:
            self.ui.spectrum_slider.setMax(maxValue)
        self.ui.spectrum_slider.update_Sliderpos()
