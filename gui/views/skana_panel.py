"""SK-Ana analysis tab shared by both TreatmentVD2 desktop entry points.

Only copies treatment measurements and calls the common numerical facade. It
does not open acquisition files, change the treatment result or control devices.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from threading import Event, Lock

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# Workers must outlive a forcibly deleted widget until their run() finishes.
# A normal window close uses prepare_close() and waits asynchronously instead.
_ACTIVE_WORKERS = set()


def _analyze(dataset, method, options, cancel):
    from utilities.skana import analyze

    return analyze(dataset, method=method, options=options, cancel=cancel)


class _AnalysisWorker(QThread):
    result_ready = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)
    cancelled = pyqtSignal(int)

    def __init__(self, generation, dataset, method, options, runner):
        super().__init__()
        self.generation = generation
        self.dataset = dataset
        self.method = method
        self.options = options
        self.runner = runner
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()
        self.requestInterruption()

    def run(self):
        try:
            result = self.runner(self.dataset, self.method, self.options, self.cancel_event.is_set)
            if self.cancel_event.is_set():
                self.cancelled.emit(self.generation)
            else:
                self.result_ready.emit(self.generation, result)
        except Exception as exc:
            if self.cancel_event.is_set():
                self.cancelled.emit(self.generation)
            else:
                self.failed.emit(self.generation, str(exc))


class SkAnaPanel(QWidget):
    """Treat the current real measurement without changing its source data."""

    _measurement_ready = pyqtSignal(object, object, object, object)
    METHODS = (("SVD", "svd"), ("MCR-ALS", "mcr_als"),
               ("Reaction kinetics / MAP", "target"))

    def __init__(self, parent=None, *, runner=None, protected_paths=None):
        super().__init__(parent)
        self.setObjectName("skana_analysis_tab")
        self._runner = runner or _analyze
        self._protected_paths = protected_paths or (lambda: ())
        self._dataset = None
        self._input_path = None
        self._result = None
        self._generation = 0
        self._notification_lock = Lock()
        self._latest_notification_token = 0
        self._worker = None
        self._closing = False

        self.input_label = QLabel("Select or calculate a treatment measurement to enable SK-Ana.")
        self.input_label.setWordWrap(True)
        self.method_combo = QComboBox()
        for label, method in self.METHODS:
            self.method_combo.addItem(label, method)
        self.method_combo.setObjectName("skana_method")
        self.rank_spin = QSpinBox()
        self.rank_spin.setRange(1, 10)
        self.rank_spin.setValue(2)
        self.rank_spin.setObjectName("skana_components")

        self.nonnegative_c = QCheckBox("Nonnegative concentration profiles")
        self.nonnegative_c.setChecked(True)
        self.nonnegative_s = QCheckBox("Nonnegative spectra")
        self.nonnegative_s.setChecked(True)
        self.component_signs = QLineEdit()
        self.component_signs.setPlaceholderText("Optional: +, free, + (one per component)")
        self.initialization = QComboBox()
        for label, key in (("|SVD|", "svd"), ("PCA", "pca"), ("NMF", "nmf"), ("Sequential", "seq")):
            self.initialization.addItem(label, key)
        self.normalization = QComboBox()
        for label, key in (("Maximum absolute intensity", "max"), ("L1", "l1"), ("None", "none")):
            self.normalization.addItem(label, key)
        self.iterations = QSpinBox()
        self.iterations.setRange(1, 5000)
        self.iterations.setValue(1000)
        self.tolerance = QLineEdit("1e-6")

        self.kinetic_nonnegative_s = QCheckBox("Nonnegative kinetic-model spectra")
        self.global_generations = QSpinBox()
        self.global_generations.setRange(0, 30)
        self.global_generations.setValue(0)
        self.population_factor = QSpinBox()
        self.population_factor.setRange(1, 100)
        self.population_factor.setValue(30)
        self.kinetic_tolerance = QLineEdit("1e-8")
        self.weighted = QCheckBox("Weighted likelihood")
        self.sigma = QLineEdit("1.0")
        self.spectral_smooth = QDoubleSpinBox()
        self.spectral_smooth.setRange(0, 1)
        self.spectral_smooth.setSingleStep(0.1)
        self.time_unit_override = QComboBox()
        self.time_unit_override.addItem("Use input label", "")
        for unit in ("fs", "ps", "ns", "us", "ms", "s"):
            self.time_unit_override.addItem(unit, unit)
        self.scheme = QPlainTextEdit(
            "A -> B ; 1 / 1.2\nc0_A_1 = 1 / 1\neps_A = 1 / 1\neps_B = 1 / 1"
        )
        self.scheme.setMinimumHeight(135)
        self.advanced_options = QPlainTextEdit()
        self.advanced_options.setPlaceholderText("{}")
        self.advanced_options.setMaximumHeight(95)

        self.option_stack = QStackedWidget()
        self.option_stack.addWidget(self._svd_options())
        self.option_stack.addWidget(self._als_options())
        self.option_stack.addWidget(self._target_options())

        self.run_button = QPushButton("Run SK-Ana")
        self.run_button.setObjectName("skana_run")
        self.run_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.export_button = QPushButton("Export JSON / CSV…")
        self.export_button.setEnabled(False)
        self.status_label = QLabel("No measurement loaded. Initial display placeholders are not analyzed.")
        self.status_label.setWordWrap(True)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(165)

        controls = QWidget()
        controls.setMinimumWidth(250)
        controls.setMaximumWidth(390)
        controls_layout = QVBoxLayout(controls)
        controls_layout.addWidget(self.input_label)
        method_form = QFormLayout()
        method_form.addRow("Method", self.method_combo)
        method_form.addRow("Components", self.rank_spin)
        controls_layout.addLayout(method_form)
        controls_layout.addWidget(self.option_stack)
        advanced_group = QGroupBox("Advanced existing-engine options (JSON overrides)")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.addWidget(QLabel("Overrides controls; unsupported keys are rejected."))
        advanced_layout.addWidget(self.advanced_options)
        controls_layout.addWidget(advanced_group)
        self.advanced_group = advanced_group
        control_buttons = QHBoxLayout()
        control_buttons.addWidget(self.run_button)
        control_buttons.addWidget(self.cancel_button)
        controls_layout.addLayout(control_buttons)
        controls_layout.addWidget(self.export_button)
        controls_layout.addWidget(self.status_label)
        controls_layout.addWidget(self.result_text)
        controls_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)

        self.figure = Figure(figsize=(8, 6), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter = QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SK-Ana · Python spectrokinetic analysis"))
        note = QLabel(
            "Uses the complete selected matrix, not the display preview. Time units are preserved. "
            "Analysis uses the existing SK-Ana Python engine. Source treatment data are unchanged."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(splitter, 1)

        self.method_combo.currentIndexChanged.connect(self._method_changed)
        self.rank_spin.valueChanged.connect(self._settings_changed)
        for checkbox in (self.nonnegative_c, self.nonnegative_s, self.kinetic_nonnegative_s, self.weighted):
            checkbox.stateChanged.connect(self._settings_changed)
        for editor in (self.component_signs, self.tolerance, self.kinetic_tolerance, self.sigma):
            editor.textChanged.connect(self._settings_changed)
        for combo in (self.initialization, self.normalization, self.time_unit_override):
            combo.currentIndexChanged.connect(self._settings_changed)
        for spin in (self.iterations, self.global_generations, self.population_factor, self.spectral_smooth):
            spin.valueChanged.connect(self._settings_changed)
        self.scheme.textChanged.connect(self._settings_changed)
        self.advanced_options.textChanged.connect(self._settings_changed)
        self.run_button.clicked.connect(self.start_analysis)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.export_button.clicked.connect(self.export_result)
        self._measurement_ready.connect(self._receive_measurement)
        self._method_changed(0)
        self._clear_plots()

    @staticmethod
    def _form_widget(rows):
        widget = QWidget()
        form = QFormLayout(widget)
        for label, field in rows:
            form.addRow(label, field) if label else form.addRow(field)
        return widget

    def _svd_options(self):
        label = QLabel("Uncentered SVD. Component count is chosen by the user, not proof of a species count.")
        label.setWordWrap(True)
        return self._form_widget((("", label),))

    def _als_options(self):
        return self._form_widget((("", self.nonnegative_c), ("", self.nonnegative_s),
            ("Spectral constraints", self.component_signs), ("Initialization", self.initialization),
            ("Spectral normalization", self.normalization), ("Maximum iterations", self.iterations),
            ("Relative tolerance", self.tolerance)))

    def _target_options(self):
        note = QLabel("Scheme factors: 1 fixes a parameter; factors above 1 use the existing log-prior MAP fit.")
        note.setWordWrap(True)
        return self._form_widget((("Reaction scheme", self.scheme), ("", note)))

    def _settings_changed(self, *_args):
        if self._worker is None:
            self._result = None
            self.export_button.setEnabled(False)
            self.result_text.clear()
            self._clear_plots()

    def _method_changed(self, index):
        self.option_stack.setCurrentIndex(index)
        self.rank_spin.setEnabled(index in (0, 1) and self._worker is None)
        # Kinetic controls are a shared group below the method-specific page.
        if not hasattr(self, "kinetic_group"):
            self.kinetic_group = QGroupBox("Kinetic fit options")
            form = QFormLayout(self.kinetic_group)
            form.addRow("Explicit time-unit label (no conversion)", self.time_unit_override)
            form.addRow("Global generations", self.global_generations)
            form.addRow("Population factor", self.population_factor)
            form.addRow("Convergence tolerance", self.kinetic_tolerance)
            form.addRow(self.weighted)
            form.addRow("Likelihood sigma", self.sigma)
            form.addRow("Spectral smoothing", self.spectral_smooth)
            form.addRow(self.kinetic_nonnegative_s)
            self.option_stack.parentWidget().layout().insertWidget(3, self.kinetic_group)
        self.kinetic_group.setVisible(index == 2)
        self._settings_changed()

    def modelIsChanged(self, measurement=None, map_index=0, critical_info=None, new=False, cursors=None):  # noqa: N802
        """Observer contract: cursor-only changes never replace the dataset."""
        if measurement is None:
            return
        # Assign order when requested, before copying or posting a queued event.
        # A main-thread update may overtake an older playback-thread signal.
        with self._notification_lock:
            self._latest_notification_token += 1
            token = self._latest_notification_token
        source_path = getattr(critical_info, "file_path", None)
        try:
            from utilities.skana import from_measurement

            # Copy in the notifying thread before a playback producer can reuse
            # its buffers; only the receiver below may touch Qt widgets.
            dataset = from_measurement(measurement, source=str(source_path) if source_path is not None else None)
            input_path = self._normalized_path(source_path) if source_path is not None else None
        except Exception as exc:
            self._measurement_ready.emit(token, None, None, str(exc))
        else:
            self._measurement_ready.emit(token, dataset, input_path, "")

    def _receive_measurement(self, token, dataset, input_path, error):
        if self._closing:
            return
        with self._notification_lock:
            if token != self._latest_notification_token:
                return
        self._generation += 1
        if input_path is not None:
            self._input_path = input_path
        self.cancel_analysis()
        self._result = None
        self.export_button.setEnabled(False)
        self.result_text.clear()
        self._clear_plots()
        if error:
            self._dataset = None
            self.input_label.setText("Selected measurement cannot be analyzed.")
            self.status_label.setText(error)
            self.run_button.setEnabled(False)
            return
        self._dataset = dataset
        time_unit = str(dataset.time_unit or "unknown")
        self.input_label.setText(
            f"{len(dataset.times)} time points × {len(dataset.wavelengths)} wavelengths · "
            f"time unit: {time_unit}. No time-unit conversion."
        )
        self.rank_spin.setMaximum(max(1, min(10, *dataset.matrix.shape)))
        self.run_button.setEnabled(self._worker is None and not self._closing)
        self.status_label.setText("Measurement copied. Choose analysis settings and run SK-Ana.")

    @staticmethod
    def _normalized_path(path):
        # Lexical comparison only: do not stat/open the active input or an SMB path.
        return os.path.normcase(os.path.abspath(os.fspath(path)))

    @staticmethod
    def _positive_number(text, name):
        try:
            value = float(text)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite positive number") from exc
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite positive number")
        return value

    def analysis_options(self):
        method = self.method_combo.currentData()
        if method == "svd":
            options = {"rank": self.rank_spin.value()}
        elif method == "mcr_als":
            constraints = self.nonnegative_s.isChecked()
            if self.component_signs.text().strip():
                tokens = [token.strip().lower() for token in self.component_signs.text().split(",")]
                if len(tokens) != self.rank_spin.value() or any(token not in ("+", "free") for token in tokens):
                    raise ValueError("Use one '+' or 'free' spectral constraint per component")
                constraints = [token == "+" for token in tokens]
            normalization = self.normalization.currentData()
            options = dict(n_components=self.rank_spin.value(),
                           nonneg_c=self.nonnegative_c.isChecked(), nonneg_s=constraints,
                           init_method=self.initialization.currentData(), norm_s=normalization != "none",
                           norm_mode="l1" if normalization == "l1" else "intensity",
                           maxiter=self.iterations.value(),
                           thresh=self._positive_number(self.tolerance.text(), "Tolerance"))
        else:
            options = dict(scheme=self.scheme.toPlainText(),
                           nonnegative_s=self.kinetic_nonnegative_s.isChecked(),
                           global_generations=self.global_generations.value(),
                           population_factor=self.population_factor.value(),
                           tol=self._positive_number(self.kinetic_tolerance.text(), "Kinetic tolerance"),
                           weighted=self.weighted.isChecked(),
                           sigma=self._positive_number(self.sigma.text(), "Likelihood sigma"),
                           spectral_smooth=self.spectral_smooth.value())
            if self.time_unit_override.currentData():
                options["time_unit"] = self.time_unit_override.currentData()
        raw = self.advanced_options.toPlainText().strip()
        if raw:
            if len(raw) > 100000:
                raise ValueError("Advanced options exceed 100 kB")
            def reject_constant(value):
                raise ValueError("Advanced options require finite JSON numbers: " + value)
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate advanced option: " + key)
                    result[key] = value
                return result
            try:
                advanced = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
            except json.JSONDecodeError as exc:
                raise ValueError("Advanced options must be a JSON object") from exc
            if not isinstance(advanced, dict):
                raise ValueError("Advanced options must be a JSON object")
            options.update(advanced)
        if method == "target" and self._dataset is not None:
            unit = options.get("time_unit") or self._dataset.time_unit
            if not unit or unit in ("??", "unknown"):
                raise ValueError("Select the physical time-unit label before a kinetic fit; no conversion is applied")
        return options

    def start_analysis(self):
        if self._dataset is None or self._worker is not None or self._closing:
            return
        try:
            options = self.analysis_options()
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self._result = None
        self.export_button.setEnabled(False)
        self.result_text.clear()
        self._clear_plots()
        worker = _AnalysisWorker(self._generation, self._dataset, self.method_combo.currentData(), options, self._runner)
        self._worker = worker
        _ACTIVE_WORKERS.add(worker)
        worker.result_ready.connect(self._accept_result)
        worker.failed.connect(self._analysis_failed)
        worker.cancelled.connect(self._analysis_cancelled)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(lambda: _ACTIVE_WORKERS.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self.run_button.setEnabled(False)
        self.method_combo.setEnabled(False)
        self.option_stack.setEnabled(False)
        self.kinetic_group.setEnabled(False)
        self.advanced_group.setEnabled(False)
        self.rank_spin.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Analysis running. Source treatment data are unchanged.")
        worker.start()

    def cancel_analysis(self):
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Result discard requested. Waiting for the existing numerical call to finish.")

    def _accept_result(self, generation, result):
        if (generation != self._generation or self._closing or self._worker is None
                or self._worker.cancel_event.is_set()):
            return
        try:
            # Validate serializability before enabling export or claiming success.
            json.dumps(result, allow_nan=False)
            self._plot_result(result)
        except Exception as exc:
            self._analysis_failed(generation, f"Invalid analysis result: {exc}")
            return
        self._result = result
        self.export_button.setEnabled(True)
        converged = result.get("converged")
        status = ("Analysis completed." if converged is not False else
                  "Convergence was not reached. Inspect the fit diagnostics.")
        warnings = result.get("warnings") or []
        if warnings:
            status += "\nWarning: " + "; ".join(str(warning) for warning in warnings)
        self.status_label.setText(status)
        summary = {key: result[key] for key in ("method", "components", "lof_percent", "rmse", "converged",
                   "iterations", "parameters", "diagnostics") if key in result}
        self.result_text.setPlainText(json.dumps(summary, indent=2, ensure_ascii=False))

    def _analysis_failed(self, generation, message):
        if generation == self._generation and not self._closing:
            self._result = None
            self.export_button.setEnabled(False)
            self.status_label.setText("Analysis failed: " + message)

    def _analysis_cancelled(self, generation):
        if generation == self._generation and not self._closing:
            self.status_label.setText("Analysis cancelled. No fitted result was applied.")

    def _worker_finished(self):
        self._worker = None
        self.cancel_button.setEnabled(False)
        self.method_combo.setEnabled(True)
        self.option_stack.setEnabled(True)
        self.kinetic_group.setEnabled(True)
        self.advanced_group.setEnabled(True)
        self.rank_spin.setEnabled(self.method_combo.currentData() in ("svd", "mcr_als"))
        self.run_button.setEnabled(self._dataset is not None and not self._closing)
        if self._closing:
            QTimer.singleShot(0, self.window().close)

    def prepare_close(self):
        """Delay parent-window destruction until its worker has stopped."""
        self._closing = True
        self._generation += 1
        if self._worker is not None:
            self.cancel_analysis()
            return False
        return True

    def closeEvent(self, event):  # noqa: N802
        if self.prepare_close():
            event.accept()
        else:
            event.ignore()

    def _clear_plots(self):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.set_axis_off()
        axis.text(0.5, 0.5, "No SK-Ana result", ha="center", va="center", transform=axis.transAxes)
        self.canvas.draw_idle()

    def _plot_result(self, result):
        times = np.asarray(result["times"], dtype=float)
        wavelengths = np.asarray(result["wavelengths"], dtype=float)
        concentrations = np.asarray(result["concentrations"], dtype=float)
        spectra = np.asarray(result["spectra"], dtype=float)
        residuals = np.asarray(result["residuals"], dtype=float)
        if concentrations.shape[0] != times.size or spectra.shape[0] != wavelengths.size:
            raise ValueError("Fitted axes do not match the factor matrices")
        if residuals.shape != (times.size, wavelengths.size):
            raise ValueError("Residual orientation must be time × wavelength")
        self.figure.clear()
        axes = self.figure.subplots(2, 2)
        for index in range(spectra.shape[1]):
            axes[0, 0].plot(wavelengths, spectra[:, index], label=str(index + 1))
            axes[0, 1].plot(times, concentrations[:, index], label=str(index + 1))
        axes[0, 0].set(title="Component spectra", xlabel="Wavelength", ylabel="Signal / profile scale")
        axes[0, 1].set(title="Concentration / kinetic profiles", xlabel=f"Time ({result.get('time_unit') or 'unknown'})")
        axes[0, 0].legend(title="Component")
        singular_values = result.get("singular_values")
        if singular_values is not None:
            singular_values = np.asarray(singular_values, dtype=float)
            axes[1, 0].semilogy(np.arange(1, singular_values.size + 1), np.maximum(singular_values, np.finfo(float).tiny), "o-")
            axes[1, 0].set(title="Singular values", xlabel="Index")
        else:
            axes[1, 0].set_axis_off()
            axes[1, 0].text(0.0, 0.9, f"LOF: {result.get('lof_percent', '?')} %\nRMSE: {result.get('rmse', '?')}\n"
                f"Converged: {result.get('converged', '?')}", va="top", transform=axes[1, 0].transAxes)
        time_indices = np.linspace(0, times.size - 1, min(160, times.size), dtype=int)
        wave_indices = np.linspace(0, wavelengths.size - 1, min(160, wavelengths.size), dtype=int)
        image = axes[1, 1].pcolormesh(wavelengths[wave_indices], times[time_indices],
            residuals[np.ix_(time_indices, wave_indices)], shading="auto", cmap="RdBu_r")
        self.figure.colorbar(image, ax=axes[1, 1])
        axes[1, 1].set(title="Residual: data − model (display sampled)", xlabel="Wavelength", ylabel="Time")
        self.canvas.draw_idle()

    def export_result(self):
        if self._result is None:
            return
        filename, selected_filter = QFileDialog.getSaveFileName(self, "Export SK-Ana result", "skana_result.json",
            "SK-Ana JSON (*.json);;SK-Ana long-form CSV (*.csv)", options=QFileDialog.DontConfirmOverwrite)
        if not filename:
            return
        kind = "csv" if "CSV" in selected_filter else "json"
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix("." + kind)
        elif path.suffix.lower() in (".json", ".csv"):
            kind = path.suffix.lower()[1:]
        else:
            self.status_label.setText("Choose a .json or .csv analysis export; treatment input files are preserved.")
            return
        overwrite = False
        if path.exists():
            answer = QMessageBox.question(self, "Replace result file?", f"Replace {path.name}?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            overwrite = True
        try:
            self.write_export(path, kind, overwrite=overwrite)
        except Exception as exc:
            self.status_label.setText("Export failed: " + str(exc))
        else:
            self.status_label.setText("Exported analysis result: " + str(path))

    def write_export(self, path, kind="json", *, overwrite=False):
        """Atomically save only to a caller-selected destination."""
        if QThread.currentThread() != self.thread():
            raise RuntimeError("Analysis export must run on the GUI thread")
        if self._result is None:
            raise ValueError("No analysis result is available")
        if kind not in ("json", "csv"):
            raise ValueError("Export format must be json or csv")
        path = Path(path)
        protected = {self._input_path} if self._input_path is not None else set()
        try:
            for source_path in self._protected_paths():
                if source_path is not None:
                    protected.add(self._normalized_path(source_path))
        except Exception as exc:
            raise ValueError("Cannot verify protected treatment paths; export was not written") from exc
        if self._normalized_path(path) in protected:
            raise ValueError("Choose a separate analysis output; the current treatment input is preserved")
        if path.suffix.lower() != "." + kind:
            raise ValueError("Export filename extension must match its JSON or CSV format")
        if path.exists() and not overwrite:
            raise FileExistsError("Result already exists; explicit overwrite confirmation required")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                             prefix=".skana-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                if kind == "json":
                    json.dump(self._result, handle, ensure_ascii=False, allow_nan=False, indent=2)
                else:
                    self._write_csv(handle)
                handle.flush()
                os.fsync(handle.fileno())
            if path.exists() and not overwrite:
                raise FileExistsError("Destination changed during export; existing file preserved")
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _write_csv(self, handle):
        result = self._result
        writer = csv.writer(handle)
        writer.writerow(("section", "time", "time_unit", "wavelength", "component", "value"))
        unit = result.get("time_unit", "")
        for row, time in zip(result["concentrations"], result["times"]):
            for component, value in enumerate(row, 1):
                writer.writerow(("concentration", time, unit, "", component, value))
        for row, wavelength in zip(result["spectra"], result["wavelengths"]):
            for component, value in enumerate(row, 1):
                writer.writerow(("spectrum", "", "", wavelength, component, value))
        for section in ("reconstruction", "residuals"):
            for row, time in zip(result[section], result["times"]):
                for value, wavelength in zip(row, result["wavelengths"]):
                    writer.writerow((section, time, unit, wavelength, "", value))
        for section in ("singular_values", "parameters"):
            values = result.get(section, [])
            values = values.items() if isinstance(values, dict) else enumerate(values, 1)
            for component, value in values:
                writer.writerow((section, "", "", "", component, value))
