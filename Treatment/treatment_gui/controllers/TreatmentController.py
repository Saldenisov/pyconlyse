"""Forked Treatment controller for the Treatment GUI.

Copied from ``gui.controllers.TreatmentController`` and adjusted to use
local Treatment GUI models and views.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List

import h5py
import numpy as np
from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import (
    QDialog,
    QErrorMessage,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QTextEdit,
)

from ..models.ClientGUIModels import TreatmentModel
from ..views.ClientsGUIViews.VD2Treatment import TreatmentView
from utilities.myfunc import info_msg, error_logger
from gui.controllers.openers.Opener import Opener, CriticalInfo
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement

module_logger = logging.getLogger(__name__)


class TreatmentController:

    def __init__(self, in_model: TreatmentModel):
        self.logger = logging.getLogger("VD2Treatment")
        self.name = "VD2TreatmentModel:controller"
        info_msg(self, "INITIALIZING")
        self.model = in_model
        self.view = TreatmentView(self)
        self.view.show()

        info_msg(self, "INITIALIZED")

    def average_noise(self) -> None:
        res, comments = self.model.average_noise()
        if not res:
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def calc_abs(self) -> None:
        self.view.ui.progressbar_calc.setValue(0)
        exp = TreatmentModel.ExpDataStruct(self.view.ui.combobox_type_exp.currentText())
        if self.view.ui.radiobutton_individual.isChecked():
            how = "individual"
        elif self.view.ui.radiobutton_averaged.isChecked():
            how = "averaged"
        else:
            how = "individual"

        first_map_with_electrons: bool = self.view.ui.checkbox_first_img_with_pulse.isChecked()
        self.model.calc_abs(exp, how, first_map_with_electrons)

    def combobox_files_changed(self) -> None:
        file_path = Path(self.view.ui.combobox_files_selected.currentText())
        if file_path.is_file():
            if self.view.ui.data_slider.value() != 0:
                self.view.ui.data_slider.setValue(0)
            else:
                self.model.read_data(file_path, 0, new=True)

    def data_cursor_update(self, eclick, erelease) -> None:
        """Legacy method for RectangleSelector (kept for compatibility)."""
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        if data_path.is_file():
            self.model.update_data_cursors(
                data_path, eclick.xdata, erelease.xdata, eclick.ydata, erelease.ydata
            )
        else:
            error_logger(self, self.data_cursor_update, "Data path is not a file")
    
    def data_cursor_update_draggable(self, x1, x2, y1, y2) -> None:
        """Handle draggable cursor position updates."""
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        if data_path.is_file():
            self.model.update_data_cursors(
                data_path, x1, x2, y1, y2
            )
        else:
            error_logger(self, self.data_cursor_update_draggable, "Data path is not a file")

    def data_folder_changed(self) -> None:
        dialog = QFileDialog()
        foo_dir = dialog.getExistingDirectory(self.view, "Select a directory")
        folder = Path(str(foo_dir))
        if folder.is_dir():
            self.view.ui.lineedit_save_folder.setText(str(folder))
            self.model.save_folder = folder
            self.view.ui.redraw_file_tree(folder)

    def get_average(self, user_type: str = "kinetics") -> None:
        error = False
        if user_type == "kinetics":
            line = self.view.ui.lineedit_kinetics_ranges.text()
        elif user_type == "spectra":
            line = self.view.ui.lineedit_spectra_ranges.text()
        else:
            error = True
            self.show_error(self.get_average, f'User_type {user_type} is not "kinetics" or "spectra"')

        if not error:
            file = self.view.ui.combobox_files_selected.currentText()
            file_path = Path(file)
            if file_path.exists() and file:
                n = self.view.ui.spinbox.value()
                s = self.model.average_range(line, file_path, user_type, n)
                if s:
                    line_new = []
                    for key, value in s.items():
                        line_new.append(f" {key} {value}")
                    if user_type == "kinetics":
                        self.view.ui.lineedit_kinetics_ranges.setText(";".join(line_new).strip())
                    elif user_type == "spectra":
                        self.view.ui.lineedit_spectra_ranges.setText(";".join(line_new).strip())
            else:
                self.show_error(self.get_average, f"File_path {file_path} does not exist.")

    def save(self) -> None:
        self.model.save()

    def save_file_path_changed(self) -> None:
        folder = self.view.ui.lineedit_save_folder.text()
        file = self.view.ui.lineedit_save_file_name.text()
        self.model.save_file_path_change(folder, file)

    def save_file_folder_changed(self) -> None:
        folder = self.view.ui.lineedit_save_folder.text()
        file = self.view.ui.lineedit_save_file_name.text()
        self.model.save_file_path_change(folder, file)

    def set_path(self, index: QModelIndex, exp_data_type: TreatmentModel.DataTypes) -> None:
        try:
            file_path = Path(self.view.ui.tree.model().filePath(index))
            if file_path.is_file() and file_path.exists():
                self.model.add_data_path(file_path, exp_data_type)
        except Exception as e:  # noqa: BLE001
            error_logger(self, self.set_path, f"Error in picking files from Tree: {e}")

    def slider_kinetics(self, index_slider, start, end) -> None:  # noqa: ARG002
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        self.model.update_data_cursors(data_path=data_path, y1=start, y2=end, pixels=True)

    def slider_spectra(self, index_slider, start, end) -> None:  # noqa: ARG002
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        self.model.update_data_cursors(data_path=data_path, x1=start, x2=end, pixels=True)

    def spinbox_map_selector_change(self) -> None:
        value = int(self.view.ui.spinbox.value())
        self.view.ui.data_slider.setValue(value)

    def slider_map_selector_change(self) -> None:
        value = int(self.view.ui.data_slider.value())
        data_path = Path(self.view.ui.combobox_files_selected.currentText())
        if data_path.is_file():
            self.model.read_data(data_path, value)
            self.view.ui.spinbox.setValue(value)

    def show_error(self, func: Callable, comments: str = "") -> None:
        error_logger(self, func, comments)
        error_dialog = QErrorMessage()
        error_dialog.showMessage(comments)
        error_dialog.exec_()

    def calc_sam(self) -> None:

        def spectral_angle_mapping(pixel_spectrum, reference_spectrum):
            pixel_spectrum /= np.linalg.norm(pixel_spectrum)
            reference_spectrum /= np.linalg.norm(reference_spectrum)
            dot_product = np.dot(pixel_spectrum, reference_spectrum)
            spectral_angle_radians = np.arccos(np.clip(dot_product, -1.0, 1.0))
            spectral_angle_degrees = np.degrees(spectral_angle_radians)
            return spectral_angle_degrees

        data = self.view.ui.kinetics_average_canvas.measurements_formed[:]
        ref_array = np.mean(data, axis=0)
        spectral_angles = []
        for pixel_spectrum in data:
            sam_value = spectral_angle_mapping(pixel_spectrum, ref_array)
            spectral_angles.append(sam_value)

        spectral_angles = np.array(spectral_angles)

        self.view.ui.sam_values.setText(str(spectral_angles))
        self.view.ui.kinetics_average_canvas.spectral_angles = spectral_angles

    def clean_his_sam(self) -> None:
        threshold = self.view.ui.spinbox_set_angle.value()
        self.calc_sam()
        spectral_angles = self.view.ui.kinetics_average_canvas.spectral_angles
        measurements = self.view.ui.kinetics_average_canvas.measurements
        measurements_cleaned: List[Measurement] = []
        for angle, measurement in zip(spectral_angles, measurements):
            if angle <= threshold:
                surface = np.sum(np.mean(measurement.data, axis=0))
                max_surface = self.view.ui.kinetics_average_canvas.average_surface
                diff = np.abs((max_surface - surface) / max_surface * 100)
                if diff < self.view.ui.spinbox_set_surface.value():
                    measurements_cleaned.append(measurement)

        if measurements_cleaned:
            self.view.ui.kinetics_average_canvas.new_data(measurements=measurements_cleaned)
            self.view.ui.kinetics_average_canvas_copy.new_data(measurements=measurements_cleaned)

    def open_config_file(self) -> None:
        """Open the Treatment/config.json file in an in-app editor dialog.

        This avoids depending on the OS default editor (e.g. Visual Studio)
        and lets users edit the JSON directly inside the PyQt application.
        """

        # Treatment/ folder containing main.py and config.json
        treatment_root = Path(__file__).resolve().parents[2]
        config_path = treatment_root / "config.json"

        if not config_path.exists():
            # Lazily create a minimal default config if missing.
            default_json = '{"TreatmentDataFolder": "E:/"}\n'
            config_path.write_text(default_json, encoding="utf-8")

        # Create a modal dialog attached to the main view window.
        dialog = QDialog(self.view)
        dialog.setWindowTitle("Edit Treatment config.json")
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit(dialog)

        try:
            current_text = config_path.read_text(encoding="utf-8")
        except OSError:
            current_text = '{"TreatmentDataFolder": "E:/"}\n'

        text_edit.setPlainText(current_text)
        layout.addWidget(text_edit)

        button_row = QHBoxLayout()
        btn_save = QPushButton("Save", dialog)
        btn_cancel = QPushButton("Cancel", dialog)
        button_row.addWidget(btn_save)
        button_row.addWidget(btn_cancel)
        layout.addLayout(button_row)

        def on_save() -> None:
            new_text = text_edit.toPlainText()
            # Validate that it is valid JSON before writing.
            try:
                import json

                json.loads(new_text)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(
                    dialog,
                    "Invalid JSON",
                    f"The config file is not valid JSON:\n{exc}",
                )
                return

            try:
                config_path.write_text(new_text, encoding="utf-8")
            except OSError as exc:  # noqa: BLE001
                QMessageBox.critical(
                    dialog,
                    "Write error",
                    f"Could not write config.json:\n{exc}",
                )
                return

            QMessageBox.information(
                dialog,
                "Config saved",
                "config.json was saved. Please restart the Treatment GUI "
                "for changes to take effect.",
            )
            dialog.accept()

        def on_cancel() -> None:
            dialog.reject()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(on_cancel)

        dialog.exec_()

    def save_clean_h5(self) -> None:

        def dataset_update(h5_file: h5py.File, dataset_name: str, data, comments: str = "") -> None:  # noqa: ARG001
            if dataset_name in h5_file:
                del h5_file[dataset_name]
                h5_file.create_dataset(
                    name=dataset_name,
                    shape=data.shape,
                    dtype=data.dtype,
                    data=data,
                    compression="gzip",
                    compression_opts=4,
                )
            else:
                h5_file.create_dataset(
                    name=dataset_name,
                    shape=data.shape,
                    dtype=data.dtype,
                    data=data,
                    compression="gzip",
                    compression_opts=4,
                )

        critical_info: CriticalInfo = self.view.ui.kinetics_average_canvas.critical_info
        measurements: List[Measurement] = self.view.ui.kinetics_average_canvas.measurements
        data = []
        for measurement in measurements:
            data.append(measurement.data)
        data = np.array(data)
        comments = measurements[0].comments
        if critical_info.file_path.suffix == ".h5":
            with h5py.File(critical_info.file_path.with_suffix(".h5"), "r+") as f:
                dataset_update(f, "raw_data", data)
        else:
            with h5py.File(critical_info.file_path.with_suffix(".h5"), "w") as f:
                metadata_group = f.create_group("metadata")
                timedelays = critical_info.timedelays
                wavelengths = critical_info.wavelengths
                dataset_update(f, "timedelays", timedelays, comments="")
                dataset_update(f, "wavelengths", wavelengths, comments="")
                dataset_update(f, "raw_data", data, comments="")
                metadata_group.attrs["description"] = critical_info.header.replace("\0", "").encode("utf-8")
