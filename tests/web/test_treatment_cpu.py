"""Exercise the production process pool used for independent file conversion."""

import os
import sys
import time
from pathlib import Path
from threading import Thread

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from treatment_api import (
    _convert_folder_source_worker,
    _convert_staged_h5_worker,
    _queue_clean_worker,
    _run_parallel_cpu_jobs,
    h5py,
)


def _worker_process_id(_data_type, _progress_queue):
    time.sleep(0.75)
    return os.getpid()


def _clean_worker_with_pid(data_type, state, angle, surface, output_name, progress_queue):
    summary = _queue_clean_worker(
        data_type, state, angle, surface, output_name, progress_queue,
    )
    return {"pid": os.getpid(), "summary": summary}


def _write_source_h5(path, compression_level=9):
    with h5py.File(path, "w") as h5_file:
        h5_file.create_dataset("timedelays", data=np.asarray([1.0, 2.0]))
        h5_file.create_dataset("wavelengths", data=np.asarray([500.0, 550.0]))
        compression = (
            {"compression": "gzip", "compression_opts": compression_level}
            if compression_level is not None
            else {}
        )
        h5_file.create_dataset("raw_data", data=np.ones((2, 2, 2), dtype=float), **compression)
        selection = h5_file.create_group("map_selection")
        selection.create_dataset("included", data=np.ones(2, dtype=bool))
        h5_file.create_group("metadata")


def test_cpu_jobs_use_separate_processes():
    result = {}

    def run_from_queue_thread():
        result["process_ids"] = _run_parallel_cpu_jobs(
            {"ABS": (), "BASE": ()},
            _worker_process_id,
        )

    queue_thread = Thread(target=run_from_queue_thread, daemon=True)
    queue_thread.start()
    queue_thread.join(timeout=15)
    assert not queue_thread.is_alive()
    process_ids = result["process_ids"]
    assert len(set(process_ids.values())) == 2
    assert os.getpid() not in process_ids.values()


def test_one_worker_processes_every_item_without_spawn(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_MAX_WORKERS", "1")
    process_ids = _run_parallel_cpu_jobs(
        {"ABS": (), "BASE": ()},
        _worker_process_id,
    )
    assert process_ids == {"ABS": os.getpid(), "BASE": os.getpid()}


def test_staged_h5_files_compress_in_spawned_workers(tmp_path):
    if h5py is None:
        pytest.skip("h5py is not available")

    items = {}
    for data_type in ("ABS", "BASE"):
        source = tmp_path / f"{data_type}_source.h5"
        output = tmp_path / f"{data_type}_output.h5"
        _write_source_h5(source)
        items[data_type] = (str(source), str(output))

    progress = []
    summaries = _run_parallel_cpu_jobs(
        items,
        _convert_staged_h5_worker,
        on_progress=lambda *event: progress.append(event),
    )

    assert set(summaries) == {"ABS", "BASE"}
    assert {event[0] for event in progress} == {"ABS", "BASE"}
    for data_type in items:
        output = Path(items[data_type][1])
        with h5py.File(output, "r") as h5_file:
            assert h5_file["raw_data"].compression == "gzip"
            assert h5_file["raw_data"].compression_opts == 4


def test_folder_h5_files_recompress_in_spawned_workers(tmp_path):
    if h5py is None:
        pytest.skip("h5py is not available")

    items = {}
    for data_type in ("ABS", "BASE"):
        source = tmp_path / f"{data_type}.h5"
        _write_source_h5(source, compression_level=None)
        items[data_type] = (str(source),)

    summaries = _run_parallel_cpu_jobs(
        items,
        _convert_folder_source_worker,
    )

    assert set(summaries) == {"ABS", "BASE"}
    for data_type in items:
        source = Path(items[data_type][0])
        assert summaries[data_type]["output_path"] == str(source)
        with h5py.File(source, "r") as h5_file:
            assert h5_file["raw_data"].compression == "gzip"
            assert h5_file["raw_data"].compression_opts == 4


def test_abs_and_base_clean_in_distinct_spawned_processes(tmp_path):
    if h5py is None:
        pytest.skip("h5py is not available")

    paths = {}
    for role in ("ABS", "BASE"):
        source = tmp_path / f"{role}_source.h5"
        _write_source_h5(source, compression_level=4)
        paths[role] = str(source)
    state = {
        "paths": paths,
        "path_sources": paths,
        "save_folder": str(tmp_path),
    }
    items = {
        role: (state, 1.0, 1.0, f"{role}_cleaned.h5")
        for role in paths
    }

    results = _run_parallel_cpu_jobs(items, _clean_worker_with_pid)

    assert len({item["pid"] for item in results.values()}) == 2
    assert all(item["pid"] != os.getpid() for item in results.values())
    for role, item in results.items():
        output = tmp_path / f"{role}_cleaned.h5"
        assert item["summary"]["output_path"] == str(output)
        with h5py.File(output, "r") as h5_file:
            assert h5_file["raw_data"].compression == "gzip"
            assert h5_file["raw_data"].compression_opts == 4
