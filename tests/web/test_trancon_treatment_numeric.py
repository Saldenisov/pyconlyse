"""Offline numerical contracts and lineage; no device or RAW inputs."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web/backend"
sys.path.insert(0, str(BACKEND))
from trancon_treatment import apply_od_operation


def clean(**changes):
    operation = {"kind": "kinetic_clean", "mode": "approx", "wavelength_pixels": [0, 1],
                 "delay_pixels": [0, 3], "od_bounds": [0., 10.], "precision": "float64"}
    operation.update(changes)
    return operation


def sg(**changes):
    operation = {"kind": "savitzky_golay", "side": 1, "order": 1, "axis": "wavelength"}
    operation.update(changes)
    return operation


def test_adjacent_approximation_uses_repaired_left_neighbour_and_entire_row():
    data = np.array([[0., 0.], [100., 100.], [300., 300.], [8., 8.]])
    original = data.copy()
    operation = clean()
    before = deepcopy(operation)
    result = apply_od_operation(data, operation)
    np.testing.assert_array_equal(result["od"], [[0, 0], [150, 150], [79, 79], [8, 8]])
    assert result["modified_indices"] == [1, 2]
    assert result["details"]["flagged_indices"] == [1, 2]
    np.testing.assert_array_equal(result["retained_indices"], [0, 1, 2, 3])
    np.testing.assert_array_equal(data, original)
    assert operation == before
    assert not np.shares_memory(result["od"], data)


def test_projection_uses_selected_columns_but_repairs_all_columns():
    data = [[0, 10, 0], [100, 30, 200], [0, 50, 0]]
    result = apply_od_operation(data, clean(delay_pixels=[0, 2], wavelength_pixels=[0, 0]))
    np.testing.assert_array_equal(result["od"], [[0, 10, 0], [0, 30, 0], [0, 50, 0]])
    assert result["details"]["kinetics"] == [0., 100., 0.]


def test_clean_projection_has_source_column_reduction_order():
    data = [[1e16, 1., -1e16, 1.], [0., 0., 0., 0.]]
    result = apply_od_operation(data, clean(wavelength_pixels=[0, 3], delay_pixels=[0, 1],
                                           od_bounds=[.2, .3], mode="delete"))
    assert result["details"]["kinetics"] == [.25, 0.]
    np.testing.assert_array_equal(result["retained_indices"], [0])


def test_delete_lineage_is_positional_even_when_delay_values_repeat():
    delays = np.array([4., 4., 9., 4.])
    result = apply_od_operation([[0, 0], [100, 100], [300, 300], [8, 8]], clean(mode="delete"))
    np.testing.assert_array_equal(result["retained_indices"], [0, 3])
    np.testing.assert_array_equal(delays[result["retained_indices"]], [4, 4])
    assert result["modified_indices"] == [1, 2]


def test_clean_bounds_and_pixels_are_inclusive_and_flag_strict_outside():
    result = apply_od_operation([[-1, -1], [0, 0], [10, 10], [11, 11]],
                                clean(mode="delete", delay_pixels=[1, 3]))
    np.testing.assert_array_equal(result["retained_indices"], [0, 1, 2])
    assert result["details"]["flagged_indices"] == [3]


def test_boundary_repairs_are_sequential_and_singleton_is_fail_closed():
    result = apply_od_operation([[100, 100], [2, 2], [100, 100]], clean(delay_pixels=[0, 2]))
    np.testing.assert_array_equal(result["od"], [[2, 2], [2, 2], [2, 2]])
    with pytest.raises(ValueError, match="singleton"):
        apply_od_operation([[100, 100]], clean(delay_pixels=[0, 0]))


def test_delete_all_rows_keeps_wavelength_dimension_and_empty_lineage():
    result = apply_od_operation([[100, 100], [200, 200]], clean(mode="delete", delay_pixels=[0, 1]))
    assert result["od"].shape == (0, 2)
    assert result["retained_indices"].dtype.kind == "i"
    assert result["retained_indices"].tolist() == []
    assert result["modified_indices"] == [0, 1]


def test_legacy_sgl_rounds_before_selection_and_reports_unflagged_quantization():
    data = np.array([[1. + 2**-25, 1. + 2**-25], [2., 2.]])
    kwargs = dict(mode="delete", delay_pixels=[0, 1], od_bounds=[0., 1.])
    dbl = apply_od_operation(data, clean(**kwargs))
    legacy = apply_od_operation(data, clean(**kwargs, precision="legacy_sgl"))
    assert dbl["retained_indices"].tolist() == []
    assert legacy["retained_indices"].tolist() == [0]
    assert legacy["od"].dtype == np.float32
    np.testing.assert_array_equal(legacy["od"], [[1., 1.]])
    assert legacy["modified_indices"] == [0, 1]
    assert legacy["details"]["computation_dtype"] == "float64"
    assert legacy["details"]["precision_policy"] == "round_input_sgl_compute_dbl_round_output_sgl"


def test_legacy_sgl_rounds_repaired_output_after_dbl_computation():
    data = [[1., 1.], [9., 9.], [1. + 2**-23, 1. + 2**-23]]
    result = apply_od_operation(data, clean(delay_pixels=[1, 1], od_bounds=[0., 2.], precision="legacy_sgl"))
    assert result["od"][1, 0] == np.float32(1.)
    assert result["details"]["flagged_indices"] == [1]


def test_baseline_preserves_source_scalar_indexing_and_truncation():
    result = apply_od_operation([[1., 10.], [3., 30.], [9., 90.]],
                                {"kind": "legacy_baseline", "delay_pixels": [0, 1]})
    np.testing.assert_array_equal(result["od"], [[-1, 8], [-17, 10]])
    np.testing.assert_array_equal(result["retained_indices"], [0, 1])
    assert result["modified_indices"] == [0, 1, 2]
    assert result["details"]["background"] == [2., 20.]
    assert result["details"]["removed_indices"] == [2]


def test_baseline_equal_bounds_select_two_adjacent_delays():
    result = apply_od_operation([[1, 10], [3, 30], [9, 90]],
                                {"kind": "legacy_baseline", "delay_pixels": [1, 1]})
    assert result["details"]["effective_delay_pixels"] == [1, 2]
    assert result["details"]["background"] == [6., 60.]
    with pytest.raises(ValueError, match="Equal-last"):
        apply_od_operation([[1, 10], [3, 30]], {"kind": "legacy_baseline", "delay_pixels": [1, 1]})


def test_baseline_does_not_omit_nonfinite_and_returns_float64_explicitly():
    data = np.array([[np.nan, 1], [3, np.inf]], dtype=np.float32)
    result = apply_od_operation(data, {"kind": "legacy_baseline", "delay_pixels": [0, 1]})
    assert np.isnan(result["od"][0]).all()
    assert np.isneginf(result["od"][1, 0]) and np.isnan(result["od"][1, 1])
    assert result["od"].dtype == np.float64
    assert result["details"]["input_dtype"] == "float32"
    assert np.isnan(data[0, 0]) and np.isposinf(data[1, 1])


def test_sg_bounded_native_impulse_and_constant_references():
    result = apply_od_operation([[1., 0., 0.], [3., 3., 3.]], sg())
    np.testing.assert_allclose(result["od"][0], [.833333, .333333, -.166667], atol=5e-6, rtol=0)
    np.testing.assert_allclose(result["od"][1], [3, 3, 3], atol=5e-6, rtol=0)
    np.testing.assert_array_equal(result["retained_indices"], [0, 1])
    assert result["operation"]["version"] == "shifted-polynomial-v1"
    assert result["operation"]["weights"] == []
    assert result["details"]["whole_NI_equivalence"] is False


def test_sg_delay_axis_and_longer_polynomial_are_explicit_model_properties():
    data = np.column_stack(([16, 9, 4, 1, 0, 1, 4, 9, 16], [3] * 9))
    result = apply_od_operation(data, sg(side=2, order=2, axis="delay"))
    np.testing.assert_allclose(result["od"], data, atol=1e-12, rtol=0)
    assert result["od"].shape == data.shape
    assert result["retained_indices"].tolist() == list(range(9))


def test_sg_zero_side_identity_and_short_input_guard():
    data = np.array([[1., 2.], [3., 4.]])
    result = apply_od_operation(data, sg(side=0, order=0))
    np.testing.assert_array_equal(result["od"], data)
    assert not np.shares_memory(result["od"], data)
    with pytest.raises(ValueError, match="shorter"):
        apply_od_operation([[1., 2., 3.]], sg(side=2, order=2))


def test_nonfinite_replacement_is_explicit_distinguishes_sign_and_never_mutates_input():
    data = np.array([[np.nan, np.inf, -np.inf, -0.], [1., 2., 3., 4.]])
    result = apply_od_operation(data, {"kind": "replace_nonfinite", "nan": -1, "positive_inf": 9, "negative_inf": -9})
    np.testing.assert_array_equal(result["od"], [[-1, 9, -9, -0.], [1, 2, 3, 4]])
    assert np.signbit(result["od"][0, 3])
    assert result["modified_indices"] == [0]
    assert result["details"]["replacement_counts"] == {"nan": 1, "positive_inf": 1, "negative_inf": 1}
    assert np.isnan(data[0, 0]) and np.isposinf(data[0, 1]) and np.isneginf(data[0, 2])


@pytest.mark.parametrize("operation", [clean(delay_pixels=[0, 1]), sg()])
@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_clean_and_sg_reject_nonfinite_without_implicit_cleanup(operation, bad):
    data = np.ones((2, 3))
    data[0, 1] = bad
    with pytest.raises(ValueError, match="finite"):
        apply_od_operation(data, operation)


@pytest.mark.parametrize("data", [[], [1, 2], [[1], [2, 3]], [[True]], [[1j]], [["1"]], np.empty((0, 2)), np.empty((2, 0))])
def test_invalid_matrix_shape_and_scalar_types_are_rejected(data):
    with pytest.raises(ValueError, match="matrix"):
        apply_od_operation(data, {"kind": "replace_nonfinite", "nan": 0, "positive_inf": 0, "negative_inf": 0})


@pytest.mark.parametrize("operation", [
    clean(delay_pixels=[3, 1]), clean(delay_pixels=[0, 4]), clean(delay_pixels=[False, 1]),
    clean(wavelength_pixels=[0, 2]), clean(od_bounds=[10, 0]), clean(od_bounds=[0, np.inf]),
    clean(mode="guess"), clean(precision="implicit"), clean(extra=True),
    {k: v for k, v in clean().items() if k != "precision"},
    sg(side=-1), sg(side=True), sg(order=3), sg(order=1.5), sg(axis="both"),
    sg(weights=[1, 1, 1]), sg(version="NI-exact"), sg(derivative=1),
    {"kind": "legacy_baseline", "delay_pixels": [0, 1], "precision": "legacy_sgl"},
    {"kind": "replace_nonfinite", "nan": True, "positive_inf": 0, "negative_inf": 0},
    {"kind": "replace_nonfinite", "nan": 0, "positive_inf": np.nan, "negative_inf": 0},
    {"kind": "raw_od"}, {}, None,
])
def test_invalid_operation_parameters_fail_closed(operation):
    with pytest.raises(ValueError):
        apply_od_operation(np.ones((4, 2)), operation)


def test_clean_rejects_unqualified_single_column_and_sgl_overflow():
    with pytest.raises(ValueError, match="two wavelength"):
        apply_od_operation(np.ones((4, 1)), clean(wavelength_pixels=[0, 0]))
    with pytest.raises(ValueError, match="finite"):
        apply_od_operation(np.full((4, 2), 1e100), clean(precision="legacy_sgl"))


def test_malformed_parameter_keys_and_unrepresentable_replacement_fail_as_value_errors():
    with pytest.raises(ValueError, match="Unknown operation parameter"):
        apply_od_operation(np.ones((4, 2)), {**clean(), 1: "unknown"})
    with pytest.raises(ValueError, match="finite float64"):
        apply_od_operation(np.ones((4, 2)), {"kind": "replace_nonfinite", "nan": 10**1000,
                                            "positive_inf": 0, "negative_inf": 0})


def test_data_and_returned_canonical_operation_do_not_alias_input_parameters():
    operation = clean(mode="delete")
    result = apply_od_operation(np.ones((4, 2)), operation)
    result["operation"]["wavelength_pixels"][0] = 1
    result["retained_indices"][0] = 3
    result["od"][0, 0] = 9
    assert operation["wavelength_pixels"] == [0, 1]
