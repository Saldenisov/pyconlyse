"""Offline dataset replay, immutable RAW and exact coordinate identity."""

import hashlib
import json
import sys
from io import BytesIO, StringIO
from pathlib import Path

import h5py
import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web/backend"
sys.path.insert(0, str(BACKEND))
from pump_probe_v0_dataset import (derive_dataset, export_dat, load_payload, read_dataset,
                                   treat_dataset, treat_derived_dataset)
from pump_probe_v0_processing import V0_RAW_GROUPS, apply_dataset_recipe, apply_recipe


def dat_bytes(delays, values, waves=(500., 600.)):
    od = np.asarray(values, dtype=np.float64)
    matrix = np.empty((len(waves) + 1, len(delays) + 1))
    matrix[0, 0], matrix[0, 1:], matrix[1:, 0] = 0, delays, waves
    matrix[1:, 1:] = od.T
    stream = StringIO()
    np.savetxt(stream, matrix, fmt="%.17g", delimiter="\t")
    return stream.getvalue().encode()


def source_h5():
    stream = BytesIO()
    waves = np.array([512.1234567890123, np.nextafter(512.1234567890123, np.inf)])
    delays = np.array([.125, .125, 5., 9.])
    with h5py.File(stream, "w") as handle:
        handle["wavelength_nm"], handle["delay_ps"] = waves, delays
        handle["od"] = np.repeat(np.array([[0., 100., 300., 8.]]), 2, axis=0)
        raw = np.full((4, 6, 4, 2), np.nan, dtype=np.float32)
        for index, count in enumerate([1, 2, 3, 4]):
            values = np.array([0, 10, 40 * (index + 1), 0, 10, 10], dtype=np.float32)
            raw[index, :, :count, :] = values[:, None, None]
        handle["raw_data"], handle["frame_counts"] = raw, [1, 2, 3, 4]
        handle.create_dataset("raw_group_names", data=np.array(V0_RAW_GROUPS, dtype=h5py.string_dtype()))
    return stream.getvalue()


def clean(mode="delete", **updates):
    return {"kind": "kinetic_clean", "mode": mode, "wavelength_pixels": [0, 1],
            "delay_pixels": [0, 3], "od_bounds": [0., 10.], "precision": "float64", **updates}


def treated(payload, operations, name="source.h5"):
    return treat_dataset(name, payload, operations, hashlib.sha256(payload).hexdigest())


def test_delete_uses_source_ordinals_not_equal_delay_values_and_never_writes_raw():
    payload = source_h5()
    payload_hash = hashlib.sha256(payload).hexdigest()
    source, _ = read_dataset("source.h5", payload)
    raw_before = [block.tobytes() for block in source.blocks]
    dataset, response = treated(payload, [clean()])
    assert response["source_row_indices"] == [0, 3]
    assert response["delays"] == [.125, 9.]
    assert response["source_delays"] == [.125, .125, 5., 9.]
    assert response["frame_counts"] == [1, 4]
    assert response["source_frame_counts"] == [1, 2, 3, 4]
    assert response["channels"][2]["values"] == [[40., 40.], [160., 160.]]
    assert [block.tobytes() for block in dataset.blocks] == raw_before
    assert hashlib.sha256(payload).hexdigest() == payload_hash
    assert len(dataset.blocks) == 4 and len(dataset.delays) == 2
    assert all(not block.flags.writeable for block in dataset.blocks)
    assert not dataset.source_delays.flags.writeable and not dataset.source_od.flags.writeable
    with pytest.raises(ValueError):
        dataset.blocks[0][0, 0, 0] = 123
    assert response["raw_lineage"]["unchanged"] is True
    assert response["raw_lineage"]["numeric_equality_to_treated_od"] is False


def test_approx_marks_modified_rows_and_uses_sequential_neighbors():
    dataset, response = treated(source_h5(), [clean("approx")])
    np.testing.assert_array_equal(dataset.od[:, 0], [0., 150., 79., 8.])
    assert response["source_row_indices"] == [0, 1, 2, 3]
    assert response["modified_source_row_indices"] == [1, 2]
    assert response["modified_row_indices"] == [1, 2]
    assert response["frame_counts"] == response["source_frame_counts"] == [1, 2, 3, 4]


def test_two_deletes_compose_original_row_map():
    dataset, response = treated(source_h5(), [clean(), clean(delay_pixels=[0, 1], od_bounds=[0., 5.])])
    assert response["source_row_indices"] == [0]
    assert response["removed_source_row_indices"] == [1, 2, 3]
    assert dataset.od.shape == (1, 2)


def test_raw_recalculation_replays_original_full_axis_after_prior_delete():
    payload = source_h5()
    shortened, _ = treated(payload, [clean()])
    assert len(shortened.delays) == 2
    fresh, response = treated(payload, [{"kind": "raw_od"}])
    assert response["source_row_indices"] == [0, 1, 2, 3]
    assert response["delays"] == [.125, .125, 5., 9.]
    np.testing.assert_allclose(fresh.od[:, 0], np.log10([4, 8, 12, 16]))
    assert response["shot_selection"]["used_counts"] == [1, 2, 3, 4]
    with pytest.raises(ValueError, match="first"):
        treated(payload, [clean(), {"kind": "raw_od"}])


def test_source_shot_counts_and_view_counts_remain_separate():
    _dataset, response = treated(source_h5(), [{"kind": "raw_od"}, clean(od_bounds=[0., .7])])
    assert response["source_row_indices"] == [0]
    assert response["shot_selection"]["used_counts"] == [1]
    assert response["shot_selection"]["source_used_counts"] == [1, 2, 3, 4]


def test_delete_export_preserves_exact_double_axes_and_original_file_bytes(tmp_path):
    path = tmp_path / "original.h5"
    payload = source_h5()
    path.write_bytes(payload)
    dataset, _ = treated(payload, [clean()])
    restored, _ = read_dataset("candidate.dat", export_dat(dataset).encode())
    np.testing.assert_array_equal(restored.wavelengths.view(np.uint64), dataset.wavelengths.view(np.uint64))
    np.testing.assert_array_equal(restored.delays.view(np.uint64), dataset.delays.view(np.uint64))
    np.testing.assert_array_equal(restored.od, dataset.od)
    assert path.read_bytes() == payload


def test_legacy_baseline_shortens_delays_with_shape_and_keeps_source_raw():
    dataset, response = treated(source_h5(), [{"kind": "legacy_baseline", "delay_pixels": [0, 1]}])
    assert dataset.od.shape == (2, 2)
    np.testing.assert_array_equal(dataset.od, [[-50., -50.], [50., 50.]])
    assert response["source_row_indices"] == [0, 1]
    assert response["delays"] == [.125, .125]
    assert response["frame_counts"] == [1, 2]
    assert len(dataset.blocks) == 4


def test_nonfinite_baseline_details_remain_strict_json_without_changing_od():
    payload = dat_bytes([0., 1.], [[float("nan"), 1.], [2., float("inf")]])
    dataset, response = treated(payload, [{"kind": "legacy_baseline", "delay_pixels": [0, 1]}], name="a.dat")
    assert np.isneginf(dataset.od[1, 0])
    assert response["treatment_details"][0]["details"]["background"] == [None, None]
    assert response["nonfinite_counts"]["negative_inf"] == 1
    json.dumps(response, allow_nan=False)


def test_canonical_recipe_fingerprint_is_stable_and_order_sensitive():
    payload = source_h5()
    _, implicit = treated(payload, [{"kind": "raw_od"}, {"kind": "scale", "factor": 2}])
    _, explicit = treated(payload, [{"kind": "raw_od", "zero_slot_policy": "retain"},
                                    {"kind": "scale", "factor": 2.0}])
    assert implicit["recipe_fingerprint"] == explicit["recipe_fingerprint"]
    _, a = treated(payload, [{"kind": "scale", "factor": 2}, {"kind": "scale", "factor": 3}])
    _, b = treated(payload, [{"kind": "scale", "factor": 3}, {"kind": "scale", "factor": 2}])
    assert a["heatmap"] == b["heatmap"]
    assert a["recipe_fingerprint"] != b["recipe_fingerprint"]
    json.dumps(explicit, allow_nan=False)


def test_old_three_tuple_recipe_and_rich_axes_contract_both_work():
    data = np.arange(8, dtype=float).reshape(4, 2)
    legacy = apply_recipe(data, None, None, [{"kind": "scale", "factor": 2}])
    assert len(legacy) == 3
    np.testing.assert_array_equal(legacy[0], data * 2)
    rich = apply_dataset_recipe(data, None, None, [], [500., 600.], [2., 1., 1., 0.])
    np.testing.assert_array_equal(rich["delays"], [2., 1., 1., 0.])
    np.testing.assert_array_equal(data, np.arange(8).reshape(4, 2))


def test_only_feasible_numeric_capabilities_are_advertised():
    payload = dat_bytes([0.], [[float("inf")]], [500.])
    source = load_payload("a.dat", payload)
    assert "replace_nonfinite" in source["capabilities"]
    assert not {"kinetic_clean", "legacy_baseline", "savitzky_golay"}.intersection(source["capabilities"])
    dataset, _ = treated(payload, [{"kind": "replace_nonfinite", "nan": 0., "positive_inf": 2., "negative_inf": -2.}], name="a.dat")
    assert dataset.od[0, 0] == 2.


def test_average_keeps_first_longest_axis_and_uses_exact_first_matching_row():
    a = ("a.dat", dat_bytes([2., 1., 1.], [[2., 20.], [8., 80.], [100., 1000.]]))
    b = ("b.dat", dat_bytes([1., 3.], [[4., 40.], [16., 160.]]))
    dataset, response = derive_dataset([a, b], "average")
    np.testing.assert_array_equal(dataset.delays, [2., 1., 1.])
    np.testing.assert_array_equal(dataset.od, [[2., 20.], [6., 60.], [6., 60.]])
    assert [c["source_row_index"] for c in response["contributors"][2]] == [1, 0]
    assert response["raw_lineage"]["scope"] == "no-aggregate-raw"
    assert not {"raw_od", "raw_background"}.intersection(response["capabilities"])
    assert dataset.blocks is None
    repeated, _ = derive_dataset([a, a, b], "average")
    np.testing.assert_allclose(repeated.od[1], [20/3, 200/3])


def test_average_length_tie_keeps_first_axis_and_rejects_mismatched_waves():
    a = ("a.dat", dat_bytes([2., 1., 1.], [[2, 20], [8, 80], [100, 1000]]))
    b = ("b.dat", dat_bytes([1., 3., 4.], [[4, 40], [16, 160], [32, 320]]))
    first, _ = derive_dataset([b, a], "average")
    np.testing.assert_array_equal(first.delays, [1., 3., 4.])
    bad = ("bad.dat", dat_bytes([0.], [[1, 2]], [600., 500.]))
    with pytest.raises(ValueError, match="wavelength"):
        derive_dataset([a, bad], "average")


def test_aggregate_retains_each_original_raw_without_synthetic_pool():
    payload = source_h5()
    original, _ = read_dataset("a.h5", payload)
    blocks = [block.tobytes() for block in original.blocks]
    dataset, response = derive_dataset([("a.h5", payload), ("b.h5", payload)], "average")
    assert dataset.blocks is None and len(dataset.source_datasets) == 2
    for source in dataset.source_datasets:
        assert [block.tobytes() for block in source.blocks] == blocks
        assert all(not block.flags.writeable for block in source.blocks)
    assert response["source_provenance"][0]["frame_counts"] == [1, 2, 3, 4]
    assert response["source_frame_counts"] == []


def test_merge_concatenates_spectral_segments_with_positional_duplicate_delays():
    a = ("a.dat", dat_bytes([1., 1., 0.], [[1, 2], [3, 4], [5, 6]], [600., 500.]))
    b = ("b.dat", dat_bytes([1., 1., 0.], [[10, 20], [30, 40], [50, 60]], [500., 700.]))
    dataset, response = derive_dataset([a, b], "merge")
    np.testing.assert_array_equal(dataset.wavelengths, [600., 500., 500., 700.])
    np.testing.assert_array_equal(dataset.od[1], [3., 4., 30., 40.])
    assert response["segments"][1]["start_column"] == 2
    assert response["segments"][1]["stop_column"] == 4
    assert response["contributors"][1][1]["source_row_index"] == 1
    bad = ("bad.dat", dat_bytes([0., 1., 1.], [[10, 20], [30, 40], [50, 60]]))
    with pytest.raises(ValueError, match="delay"):
        derive_dataset([a, bad], "merge")


def test_derived_replay_is_stateless_and_rejects_changed_source_fingerprint():
    a = ("a.dat", dat_bytes([.125, .125, 5., 9.], [[0, 0], [100, 100], [300, 300], [8, 8]]))
    b = ("b.dat", a[1])
    _source, loaded = derive_dataset([a, b], "merge")
    dataset, response = treat_derived_dataset([a, b], "merge", [clean()], loaded["source_sha256"])
    assert response["source_row_indices"] == [0, 3]
    assert response["contributors"][1][0]["source_row_index"] == 3
    assert response["source_spec"] == loaded["source_spec"]
    assert dataset.od.shape == (2, 4)
    reloaded, _ = derive_dataset([a, b], "merge")
    assert reloaded.od.shape == (4, 4)
    changed = ("b.dat", dat_bytes([.125, .125, 5., 9.], [[1, 1], [100, 100], [300, 300], [8, 8]]))
    with pytest.raises(ValueError, match="changed"):
        treat_derived_dataset([a, changed], "merge", [], loaded["source_sha256"])
    with pytest.raises(ValueError, match="RAW"):
        treat_derived_dataset([a, b], "merge", [{"kind": "raw_od"}], loaded["source_sha256"])
