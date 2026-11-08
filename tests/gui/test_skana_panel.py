"""Offscreen SK-Ana tab tests with synthetic matrices; no Treatment app startup."""

import csv
import json
import threading
from time import monotonic
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from gui.views.skana_panel import SkAnaPanel, _ACTIVE_WORKERS
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def wait_for(app, condition, timeout=8):
    deadline = monotonic() + timeout
    while not condition():
        app.processEvents()
        if monotonic() >= deadline:
            pytest.fail("Offscreen numerical worker did not settle")
        QTest.qWait(5)
    app.processEvents()


@pytest.fixture
def panel(app):
    widget = SkAnaPanel()
    yield widget
    widget.close()
    wait_for(app, lambda: widget._worker is None)
    widget.deleteLater()
    app.processEvents()


def measurement(unit="ns", scale=1.0):
    times = np.linspace(0, 5, 6)
    wavelengths = np.linspace(400, 550, 4)
    matrix = scale * np.outer(np.array([1.0, 2.0, 3.0, 4.0]), np.exp(-times))
    return Measurement(type="OD", comments="Synthetic closed test matrix", author="test", timestamp=0,
                       data=matrix, wavelengths=wavelengths, timedelays=times, time_scale=unit)


def result_for(dataset, method="svd", converged=True):
    matrix = np.asarray(dataset.matrix)
    u, values, vt = np.linalg.svd(matrix, full_matrices=False)
    reconstruction = np.outer(u[:, 0] * values[0], vt[0])
    return dict(method=method, components=1, times=dataset.times.tolist(),
                wavelengths=dataset.wavelengths.tolist(), time_unit=dataset.time_unit,
                concentrations=(u[:, :1] * values[0]).tolist(), spectra=vt[:1].T.tolist(),
                reconstruction=reconstruction.tolist(), residuals=(matrix - reconstruction).tolist(),
                singular_values=values.tolist(), lof_percent=0.0, rmse=0.0, converged=converged,
                iterations=1, diagnostics={})


def test_no_analysis_of_startup_display_placeholders(panel):
    assert not panel.run_button.isEnabled()
    assert not panel.export_button.isEnabled()
    assert panel._dataset is None
    assert "placeholders" in panel.status_label.text()
    assert [panel.method_combo.itemData(i) for i in range(panel.method_combo.count())] == ["svd", "mcr_als", "target"]
    panel.start_analysis()
    assert panel._worker is None


def test_real_measurement_is_copied_with_canonical_orientation_and_cursor_events_ignored(panel):
    source = measurement()
    expected = source.data.T.copy()
    panel.modelIsChanged(source)
    assert panel.run_button.isEnabled()
    assert panel._dataset.matrix.shape == (6, 4)
    np.testing.assert_array_equal(panel._dataset.matrix, expected)
    source.data[:] = 500
    np.testing.assert_array_equal(panel._dataset.matrix, expected)
    prior_dataset, prior_generation = panel._dataset, panel._generation
    panel.modelIsChanged(None, cursors={"x1": 2})
    assert panel._dataset is prior_dataset and panel._generation == prior_generation


def test_unknown_units_preserved_and_kinetic_fit_requires_explicit_unit_label(panel):
    panel.modelIsChanged(measurement("??"))
    assert panel._dataset.time_unit == "??"
    assert "??" in panel.input_label.text()
    panel.method_combo.setCurrentIndex(2)
    with pytest.raises(ValueError, match="time-unit label"):
        panel.analysis_options()
    panel.time_unit_override.setCurrentIndex(panel.time_unit_override.findData("ps"))
    options = panel.analysis_options()
    assert options["time_unit"] == "ps"
    assert options["global_generations"] == 0
    assert options["nonnegative_s"] is False
    assert "??" == panel._dataset.time_unit  # declaring fit units does not change measurement


def test_playback_thread_copies_measurement_then_queues_gui_update(panel, app):
    source = measurement()
    expected = source.data.T.copy()
    producer = threading.Thread(target=panel.modelIsChanged, args=(source,))
    producer.start()
    producer.join(3)
    assert not producer.is_alive()
    assert panel._dataset is None  # no widget update happened in producer thread
    source.data[:] = 800
    wait_for(app, lambda: panel._dataset is not None)
    np.testing.assert_array_equal(panel._dataset.matrix, expected)


def test_older_queued_playback_notification_cannot_replace_newer_main_thread_measurement(panel, app):
    older = measurement(scale=1.0)
    newer = measurement(scale=3.0)
    producer = threading.Thread(target=panel.modelIsChanged, args=(older,))
    producer.start()
    producer.join(3)
    assert not producer.is_alive()
    assert panel._dataset is None  # old snapshot is queued, not delivered
    panel.modelIsChanged(newer)  # direct main-thread notification overtakes queued one
    expected = newer.data.T.copy()
    np.testing.assert_array_equal(panel._dataset.matrix, expected)
    latest_generation = panel._generation
    app.processEvents()
    np.testing.assert_array_equal(panel._dataset.matrix, expected)
    assert panel._generation == latest_generation


def test_existing_engine_options_and_per_component_signed_spectra(panel):
    panel.modelIsChanged(measurement())
    assert panel.analysis_options() == {"rank": 2}
    panel.method_combo.setCurrentIndex(1)
    panel.component_signs.setText("+, free")
    panel.normalization.setCurrentIndex(panel.normalization.findData("l1"))
    panel.advanced_options.setPlainText('{"broadening": true, "close_c": true, "maxiter": 12}')
    options = panel.analysis_options()
    assert options["nonneg_s"] == [True, False]
    assert options["norm_s"] is True and options["norm_mode"] == "l1"
    assert options["init_method"] == "svd" and options["maxiter"] == 12
    assert options["close_c"] is True and options["broadening"] is True
    assert "max_iterations" not in options and "nonnegative_spectra" not in options


@pytest.mark.parametrize("raw", ['[]', '{"x": NaN}', '{"maxiter":1,"maxiter":2}', '{bad'])
def test_invalid_advanced_options_are_not_sent_to_worker(panel, raw):
    panel.modelIsChanged(measurement())
    panel.advanced_options.setPlainText(raw)
    panel.start_analysis()
    assert panel._worker is None
    assert "Analysis running" not in panel.status_label.text()


def test_real_shared_engine_svd_runs_off_ui_thread_and_result_invalidation(panel, app):
    source = measurement()
    before = source.data.copy()
    panel.modelIsChanged(source)
    panel.start_analysis()
    wait_for(app, lambda: panel._worker is None)
    assert panel._result is not None, panel.status_label.text()
    assert panel.export_button.isEnabled()
    assert panel._result["method"] == "svd"
    np.testing.assert_allclose(panel._result["reconstruction"], before.T, atol=1e-12)
    np.testing.assert_array_equal(source.data, before)
    assert len(panel.figure.axes) >= 4
    panel.rank_spin.setValue(1)
    assert panel._result is None and not panel.export_button.isEnabled()


def test_worker_runs_in_another_thread_and_nonconvergence_is_explicit(panel, app):
    main_thread = threading.get_ident()
    calls = []
    def runner(dataset, method, options, cancel):
        calls.append((threading.get_ident(), method, options))
        return result_for(dataset, method, converged=False)
    panel._runner = runner
    panel.modelIsChanged(measurement())
    panel.start_analysis()
    wait_for(app, lambda: panel._worker is None)
    assert calls[0][0] != main_thread
    assert calls[0][1:] == ("svd", {"rank": 2})
    assert "Convergence was not reached" in panel.status_label.text()
    assert panel.export_button.isEnabled()  # clearly labelled partial result can be exported


def test_existing_engine_qualification_warning_is_visible_without_opening_diagnostics(panel, app):
    warning = "Existing SK-Ana Python forces a nonnegative spectrum for exactly one free active kinetic component."
    def runner(dataset, method, options, cancel):
        result = result_for(dataset, method)
        result["warnings"] = [warning]
        result["diagnostics"]["warnings"] = [warning]
        return result
    panel._runner = runner
    panel.modelIsChanged(measurement())
    panel.start_analysis()
    wait_for(app, lambda: panel._worker is None)
    assert "Warning:" in panel.status_label.text()
    assert warning in panel.status_label.text()
    assert panel._result["warnings"] == [warning]


def test_measurement_changed_while_existing_solver_runs_discards_old_result(panel, app):
    entered, release = threading.Event(), threading.Event()
    def runner(dataset, method, options, cancel):
        entered.set()
        assert release.wait(4)
        return result_for(dataset)
    panel._runner = runner
    panel.modelIsChanged(measurement())
    panel.start_analysis()
    assert entered.wait(3)
    old_worker = panel._worker
    try:
        panel.modelIsChanged(measurement(scale=2.0))
        assert old_worker.cancel_event.is_set()
        assert not panel.run_button.isEnabled()
    finally:
        release.set()
    wait_for(app, lambda: panel._worker is None)
    assert panel._result is None and not panel.export_button.isEnabled()
    assert panel.run_button.isEnabled()
    np.testing.assert_allclose(panel._dataset.matrix[0], [2, 4, 6, 8])


def test_closing_waits_for_existing_solver_without_forcing_thread_termination(panel, app):
    entered, release = threading.Event(), threading.Event()
    def runner(dataset, method, options, cancel):
        entered.set()
        assert release.wait(4)
        return result_for(dataset)
    panel._runner = runner
    panel.modelIsChanged(measurement())
    panel.show()
    panel.start_analysis()
    assert entered.wait(3)
    worker = panel._worker
    try:
        panel.close()
        assert worker.isRunning()
        assert worker.cancel_event.is_set()
        assert worker in _ACTIVE_WORKERS
        assert panel.isVisible()  # ignored close until its worker finishes
    finally:
        release.set()
    wait_for(app, lambda: panel._worker is None)
    wait_for(app, lambda: not panel.isVisible())
    assert panel._result is None
    assert worker not in _ACTIVE_WORKERS


def test_result_export_is_atomic_and_existing_file_requires_explicit_overwrite(panel, tmp_path):
    panel.modelIsChanged(measurement())
    panel._result = result_for(panel._dataset)
    output = tmp_path / "result.json"
    panel.write_export(output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["time_unit"] == "ns"
    assert saved["residuals"] == panel._result["residuals"]
    output.write_text("retain existing file", encoding="utf-8")
    with pytest.raises(FileExistsError):
        panel.write_export(output)
    assert output.read_text(encoding="utf-8") == "retain existing file"
    panel.write_export(output, overwrite=True)
    assert json.loads(output.read_text(encoding="utf-8"))["method"] == "svd"
    csv_path = tmp_path / "result.csv"
    panel.write_export(csv_path, "csv")
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["section"] for row in rows} >= {"concentration", "spectrum", "reconstruction", "residuals"}
    assert next(row for row in rows if row["section"] == "concentration")["time_unit"] == "ns"
    assert not list(tmp_path.glob(".skana-*.tmp"))


def test_failed_atomic_export_preserves_destination_and_cleans_temporary(panel, tmp_path, monkeypatch):
    panel.modelIsChanged(measurement())
    panel._result = result_for(panel._dataset)
    output = tmp_path / "previous.json"
    output.write_text("original", encoding="utf-8")
    def fail_replace(*args):
        raise OSError("destination locked")
    monkeypatch.setattr("gui.views.skana_panel.os.replace", fail_replace)
    with pytest.raises(OSError, match="locked"):
        panel.write_export(output, overwrite=True)
    assert output.read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob(".skana-*.tmp"))


def test_original_treatment_input_cannot_be_overwritten_by_analysis_export(panel, tmp_path):
    source_path = tmp_path / "input.csv"
    source_path.write_text("original treatment data", encoding="utf-8")
    panel.modelIsChanged(measurement(), critical_info=SimpleNamespace(file_path=source_path))
    panel.modelIsChanged(measurement(scale=2), critical_info=None)  # calculated OD publication
    panel._result = result_for(panel._dataset)
    with pytest.raises(ValueError, match="current treatment input"):
        panel.write_export(source_path, "csv", overwrite=True)
    assert source_path.read_text(encoding="utf-8") == "original treatment data"
    with pytest.raises(ValueError, match="extension"):
        panel.write_export(tmp_path / "analysis.h5", "json")


def test_export_checks_all_live_model_input_paths_on_gui_thread(panel, tmp_path):
    abs_path = tmp_path / "abs.csv"
    base_path = tmp_path / "base.csv"
    abs_path.write_text("original ABS", encoding="utf-8")
    base_path.write_text("original BASE", encoding="utf-8")
    model_paths = [abs_path]
    callback_threads = []
    def protected_paths():
        callback_threads.append(threading.get_ident())
        return tuple(model_paths)
    panel._protected_paths = protected_paths
    panel.modelIsChanged(measurement(), critical_info=SimpleNamespace(file_path=abs_path))
    panel.modelIsChanged(measurement(scale=2), critical_info=None)
    model_paths.append(base_path)  # callback must read current paths, not an initial snapshot
    panel._result = result_for(panel._dataset)
    for source_path in (abs_path, base_path):
        with pytest.raises(ValueError, match="current treatment input"):
            panel.write_export(source_path, "csv", overwrite=True)
    assert abs_path.read_text(encoding="utf-8") == "original ABS"
    assert base_path.read_text(encoding="utf-8") == "original BASE"
    assert callback_threads == [threading.get_ident(), threading.get_ident()]
