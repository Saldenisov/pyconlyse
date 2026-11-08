"""Cleaning requires explicit mode, precision and qualified pixel ranges."""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web/backend"
sys.path.insert(0, str(BACKEND))
from pump_probe_v0_dataset import load_payload, treat_dataset


SOURCE = b"0\t-1\t0\t1\t2\n500\t0\t100\t300\t8\n600\t0\t100\t300\t8\n"


def operation(mode="approx", **updates):
    return {"kind": "kinetic_clean", "mode": mode, "wavelength_pixels": [0, 1],
            "delay_pixels": [0, 3], "od_bounds": [0., 10.], "precision": "float64", **updates}


def test_cleaning_capability_tracks_finite_compatible_map():
    assert "kinetic_clean" in load_payload("sample.dat", SOURCE)["capabilities"]
    assert "kinetic_clean" not in load_payload("sample.dat", b"0\t0\n500\tnan\n")["capabilities"]


@pytest.mark.parametrize("mode,expected_rows", [("delete", [0, 3]), ("approx", [0, 1, 2, 3])])
def test_explicit_cleaning_contract_replaces_old_unconditional_gate(mode, expected_rows):
    source = load_payload("sample.dat", SOURCE)
    _dataset, response = treat_dataset("sample.dat", SOURCE, [operation(mode)], source["source_sha256"])
    assert response["source_row_indices"] == expected_rows
    assert response["operations"][0]["precision"] == "float64"


@pytest.mark.parametrize("missing", ["mode", "precision", "wavelength_pixels", "delay_pixels", "od_bounds"])
def test_implicit_cleaning_settings_are_rejected(missing):
    recipe = operation()
    del recipe[missing]
    source = load_payload("sample.dat", SOURCE)
    with pytest.raises(ValueError):
        treat_dataset("sample.dat", SOURCE, [recipe], source["source_sha256"])


def test_pixel_bounds_do_not_become_unchecked_array_indices():
    source = load_payload("sample.dat", SOURCE)
    with pytest.raises(ValueError):
        treat_dataset("sample.dat", SOURCE, [operation(delay_pixels=[-1, 3])], source["source_sha256"])
