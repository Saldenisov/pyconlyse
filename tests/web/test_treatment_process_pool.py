"""Exercise actual Windows-spawn-compatible treatment workers with local H5."""

import pickle
from pathlib import Path

import h5py
import numpy as np
import pytest

import treatment_api


def _write_h5(path, value):
    with h5py.File(path, "w") as handle:
        handle.create_dataset("raw_data", data=np.full((3, 2, 4), value))
        handle.create_dataset("wavelengths", data=[500.0, 550.0])
        handle.create_dataset("timedelays", data=[0.0, 1.0, 2.0, 3.0])


def test_workers_keep_importable_entry_points():
    for worker in (
        treatment_api._convert_folder_source_worker,
        treatment_api._convert_staged_h5_worker,
        treatment_api._queue_convert_worker,
        treatment_api._queue_clean_worker,
    ):
        assert pickle.loads(pickle.dumps(worker)) is worker
    with treatment_api._cpu_executor(2) as executor:
        assert executor._mp_context.get_start_method() == "spawn"


def test_spawned_workers_convert_h5_and_deliver_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(treatment_api, "_treatment_worker_count", lambda count: 2)
    items = {}
    for role, value in (("ABS", 10), ("BASE", 20)):
        source = tmp_path / f"{role}-raw.h5"
        output = tmp_path / f"{role}-compressed.h5"
        _write_h5(source, value)
        items[role] = (str(source), str(output))
    progress = []
    completed = []

    results = treatment_api._run_parallel_cpu_jobs(
        items,
        treatment_api._convert_staged_h5_worker,
        on_progress=lambda role, *event: progress.append((role, *event)),
        on_complete=lambda role, result: completed.append(role),
    )

    assert set(results) == set(completed) == {"ABS", "BASE"}
    assert {event[0] for event in progress} == {"ABS", "BASE"}
    for role, value in (("ABS", 10), ("BASE", 20)):
        source, output = map(Path, items[role])
        treatment_api._validate_canonical_h5(output)
        with h5py.File(source, "r") as before, h5py.File(output, "r") as after:
            np.testing.assert_array_equal(before["raw_data"][:], after["raw_data"][:])
            assert after["raw_data"].compression == "gzip"
            assert after["raw_data"][0, 0, 0] == value
            assert after["timedelays"][0] == 0


def test_spawned_worker_failure_reports_role_and_preserves_input(tmp_path, monkeypatch):
    monkeypatch.setattr(treatment_api, "_treatment_worker_count", lambda count: 2)
    source = tmp_path / "invalid.h5"
    source.write_bytes(b"incomplete recording")
    errors = []

    with pytest.raises(ValueError):
        treatment_api._run_parallel_cpu_jobs(
            {"ABS": (str(source), str(tmp_path / "output.h5"))},
            treatment_api._convert_staged_h5_worker,
            on_error=lambda role, exc: errors.append((role, str(exc))),
        )

    assert len(errors) == 1
    assert errors[0][0] == "ABS"
    assert source.read_bytes() == b"incomplete recording"
