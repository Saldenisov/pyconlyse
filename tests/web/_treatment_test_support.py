"""Shared local fixtures and data builders for treatment API contracts."""

import json
import sys
import time
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import numpy as np
import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from folder_api import folder_api
import folder_api as folder_api_module
import treatment_api as treatment_api_module
from treatment_api import session_store, treatment_api


def _write_dat(file_path, data, wavelengths=None, timedelays=None):
    data = np.asarray(data, dtype=float)
    wavelengths = np.asarray(wavelengths if wavelengths is not None else [500, 600], dtype=float)
    timedelays = np.asarray(timedelays if timedelays is not None else [1, 2], dtype=float)
    if data.shape != (len(wavelengths), len(timedelays)):
        raise ValueError(
            f"data shape {data.shape} does not match "
            f"(len(wavelengths), len(timedelays))={(len(wavelengths), len(timedelays))}"
        )
    payload = np.zeros((len(timedelays) + 1, len(wavelengths) + 1), dtype=float)
    payload[0, 1:] = wavelengths
    payload[1:, 0] = timedelays
    payload[1:, 1:] = data.transpose()
    np.savetxt(file_path, payload, delimiter="\t", fmt="%.4f")


def _measurement(data, wavelengths=None, timedelays=None, time_scale="ps"):
    array = np.asarray(data, dtype=float)
    return SimpleNamespace(
        data=array,
        wavelengths=np.asarray(
            wavelengths if wavelengths is not None else np.arange(array.shape[0], dtype=float),
            dtype=float,
        ),
        timedelays=np.asarray(
            timedelays if timedelays is not None else np.arange(array.shape[1], dtype=float),
            dtype=float,
        ),
        time_scale=time_scale,
    )


def _critical_info(file_path, number_maps, wavelengths=None, timedelays=None):
    wavelengths = np.asarray(wavelengths if wavelengths is not None else [500.0, 550.0])
    timedelays = np.asarray(timedelays if timedelays is not None else [1.0, 2.0])
    return SimpleNamespace(
        file_path=file_path,
        number_maps=number_maps,
        wavelengths=wavelengths,
        timedelays=timedelays,
        wavelengths_length=len(wavelengths),
        timedelays_length=len(timedelays),
        scaling_yunit="ps",
        header="fake HIS",
    )


def _write_gzip_h5(file_path, compression_level=9):
    h5py = treatment_api_module.h5py
    if h5py is None:
        pytest.skip("h5py is not available")
    with h5py.File(file_path, "w") as h5_file:
        h5_file.create_dataset("timedelays", data=np.asarray([1.0, 2.0]))
        h5_file.create_dataset("wavelengths", data=np.asarray([500.0, 550.0]))
        h5_file.create_dataset(
            "raw_data",
            data=np.ones((2, 2, 2), dtype=float),
            compression="gzip",
            compression_opts=compression_level,
        )
        selection = h5_file.create_group("map_selection")
        selection.create_dataset("included", data=np.ones(2, dtype=bool))
        metadata = h5_file.create_group("metadata")
        metadata.attrs["compression"] = "gzip"
        metadata.attrs["compression_level"] = compression_level


class FakeHisOpener:
    def __init__(self, pairs):
        self._pairs = list(pairs)
        self.paths = {}

    def read_map(self, _file_path, map_index):
        flat_maps = [measurement for pair in self._pairs for measurement in pair]
        return flat_maps[map_index], ""

    def give_pair_maps(self, _file_path):
        return list(self._pairs)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(tmp_path))
    monkeypatch.setenv(
        "PYCONLYSE_TREATMENT_CACHE_DIR",
        str(tmp_path.parent / f"{tmp_path.name}_treatment_cache"),
    )
    monkeypatch.setenv("PYCONLYSE_TREATMENT_CACHE_LIMIT_BYTES", str(1024 * 1024))
    session_store.reset()

    app = Flask(__name__)
    app.register_blueprint(folder_api)
    app.register_blueprint(treatment_api)

    with app.test_client() as test_client:
        yield test_client, tmp_path
