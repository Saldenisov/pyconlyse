"""MCR options and plots for the Gamma viewer."""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)


def ask_mcr_options(parent, defaults):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Fit MCR-ALS")
    layout = QFormLayout(dialog)
    components = QSpinBox()
    components.setRange(1, 3)
    components.setValue(defaults.get("components", 1))
    layout.addRow("Sample components", components)
    layout.addRow(QLabel("The measured blank drift is included separately."))
    spectra = QCheckBox("Allow negative spectral bands")
    spectra.setChecked(defaults.get("signed_spectra", False))
    layout.addRow(spectra)
    amplitudes = QCheckBox("Allow negative amplitudes")
    amplitudes.setChecked(defaults.get("signed_amplitudes", False))
    layout.addRow(amplitudes)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    if dialog.exec_() != QDialog.Accepted:
        return None
    return dict(components=components.value(), signed_spectra=spectra.isChecked(),
                signed_amplitudes=amplitudes.isChecked())


def show_mcr_dialog(parent, result, allow_refit):
    dialog = QDialog(parent)
    dialog.setWindowTitle("MCR-ALS")
    dialog.resize(850, 680)
    layout = QVBoxLayout(dialog)
    summary = QLabel(f"RMSE {result['rmse']:.4g} OD  |  Relative residual {result['relative_residual']:.2%}")
    if result["stale"]:
        summary.setText(summary.text() + "  |  A newer blank correction is available. Refit to use it.")
    summary.setWordWrap(True)
    summary.setToolTip(f"{result['path']}\nSource: {result['source']}\n{result['stop_flags']}")
    layout.addWidget(summary)

    tabs = QTabWidget()
    layout.addWidget(tabs)
    components = QWidget()
    component_layout = QVBoxLayout(components)
    axis = QComboBox()
    axis.addItem("Elapsed time (min)", False)
    if result["dose"] is not None and np.isfinite(result["dose"]).any():
        axis.addItem("Accumulated dose (Gy)", True)
        axis.setCurrentIndex(1)
    component_layout.addWidget(axis)
    spectra = pg.PlotWidget(title="Sample component spectra")
    spectra.setLabel("bottom", "Wavelength", units="nm")
    spectra.setLabel("left", "Normalized loading")
    spectra.addLegend()
    kinetics = pg.PlotWidget(title="Sample component kinetics")
    kinetics.setLabel("left", "Relative amplitude")
    kinetics.addLegend()
    component_layout.addWidget(spectra)
    component_layout.addWidget(kinetics)
    tabs.addTab(components, "Spectra and kinetics")

    reconstruction = QWidget()
    reconstruction_layout = QVBoxLayout(reconstruction)
    time_label = QLabel()
    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, len(result["time"]) - 1)
    slider.setValue(len(result["time"]) - 1)
    selector = QHBoxLayout()
    selector.addWidget(time_label)
    selector.addWidget(slider)
    reconstruction_layout.addLayout(selector)
    reconstructed = pg.PlotWidget(title="Reconstructed OD at the selected point")
    reconstructed.setLabel("bottom", "Wavelength", units="nm")
    reconstructed.setLabel("left", "Optical density")
    reconstructed.addLegend()
    reconstruction_layout.addWidget(reconstructed)
    tabs.addTab(reconstruction, "Reconstruction")

    blank_tab = QWidget()
    blank_layout = QVBoxLayout(blank_tab)
    blank_selector = QHBoxLayout()
    blank_selector.addWidget(QLabel("Wavelength (nm)"))
    blank_wavelength = QDoubleSpinBox()
    wavelength = result["wavelength"]
    blank_wavelength.setRange(float(wavelength.min()), float(wavelength.max()))
    blank_wavelength.setValue(float(wavelength[np.argmax(np.abs(result["anchor_drift"][-1]))]))
    blank_selector.addWidget(blank_wavelength)
    blank_selector.addStretch()
    blank_layout.addLayout(blank_selector)
    blank_plot = pg.PlotWidget(title="Measured blank drift at the selected wavelength")
    blank_plot.setLabel("left", "Optical density change")
    blank_points = blank_plot.plot(pen=pg.mkPen("#999999", width=2), symbol="o")
    blank_layout.addWidget(blank_plot)
    tabs.addTab(blank_tab, "Blank anchors")

    curve_kinetics, curve_components = [], []
    for i, spectrum in enumerate(result["spectra"]):
        pen = pg.mkPen(pg.intColor(i, hues=len(result["spectra"])), width=2)
        name = f"Sample {i + 1}"
        spectra.plot(result["wavelength"], spectrum, pen=pen, name=name)
        curve_kinetics.append(kinetics.plot(pen=pen, name=name))
        curve_components.append(reconstructed.plot(pen=pen, name=name))
    sample_curve = reconstructed.plot(pen=pg.mkPen("w", width=2), name="Total sample OD")
    blank_curve = reconstructed.plot(pen=pg.mkPen("#999999", width=2, style=Qt.DashLine), name="Blank drift")

    def update_kinetics():
        dose = axis.currentData()
        x = result["dose"] if dose else result["time"] / 60
        finite = np.isfinite(x)
        kinetics.setLabel("bottom", "Accumulated dose" if dose else "Elapsed time", units="Gy" if dose else "min")
        for curve, amplitude in zip(curve_kinetics, result["amplitudes"].T):
            curve.setData(x[finite], amplitude[finite])
        update_blank()

    def update_blank():
        column = int(np.argmin(np.abs(wavelength - blank_wavelength.value())))
        use_dose = axis.currentData() and result["anchor_dose"] is not None
        x = result["anchor_dose"] if use_dose else result["anchor_time"] / 60
        blank_plot.setLabel("bottom", "Accumulated dose" if use_dose else "Elapsed time", units="Gy" if use_dose else "min")
        blank_points.setData(x, result["anchor_drift"][:, column])

    def update_reconstruction(index):
        time_s = result["time"][index]
        label = f"{time_s / 60:.2f} min"
        if result["dose"] is not None and np.isfinite(result["dose"][index]):
            label += f"  |  {result['dose'][index]:.3f} Gy"
        time_label.setText(label)
        contributions = result["amplitudes"][index, :, None] * result["spectra"]
        wavelength = result["wavelength"]
        for curve, values in zip(curve_components, contributions):
            curve.setData(wavelength, values)
        sample_curve.setData(wavelength, contributions.sum(axis=0))
        anchors = result["anchor_time"]
        stop = int(np.searchsorted(anchors, time_s))
        if time_s == anchors[stop]:
            drift = result["anchor_drift"][stop]
        else:
            fraction = (time_s - anchors[stop - 1]) / (anchors[stop] - anchors[stop - 1])
            drift = (1 - fraction) * result["anchor_drift"][stop - 1] + fraction * result["anchor_drift"][stop]
        blank_curve.setData(wavelength, drift)

    axis.currentIndexChanged.connect(update_kinetics)
    blank_wavelength.valueChanged.connect(update_blank)
    slider.valueChanged.connect(update_reconstruction)
    update_kinetics()
    update_reconstruction(slider.value())
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dialog.reject)
    if allow_refit:
        refit = buttons.addButton("Refit…", QDialogButtonBox.ActionRole)
        refit.clicked.connect(dialog.accept)
    layout.addWidget(buttons)
    return dialog.exec_() == QDialog.Accepted
