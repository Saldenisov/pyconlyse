"""Discriminating offline detector admission contracts; no device imports."""

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))

from pump_probe_v0_detector_filters import (
    FILTER_VERSION, REPUMP_VERSION, SIMILARITY_VERSION,
    apply_detector_filters, validate_detector_filter_settings,
)


def profile(**stages):
    return {"all_cycles": False, "filters": {
        "version": FILTER_VERSION, "repump": {"enabled": False},
        "nonfinite": {"enabled": False}, "similarity": {"enabled": False}, **stages}}


def groups(count=3, width=4):
    data = np.zeros((count, 6, width), dtype=np.float32)
    data[:, 2:4] = 10
    data[:, 4:6] = 20
    return data


def similarity(**changes):
    return {"enabled": True, "version": SIMILARITY_VERSION,
            "threshold_ref_channel": 1., "mode": "python", "metric": "euclidean",
            "diff": 2., "min_distance": -1., "from_pixel": 0, "to_pixel": 2, **changes}


def test_disabled_explicit_profile_preserves_duplicate_order_and_RAW():
    data = groups()
    data[2] = data[0]
    original = data.copy()
    settings = profile()
    before = copy.deepcopy(settings)
    result = apply_detector_filters(data, settings)
    assert result["accepted_indices"] == [0, 1, 2]
    assert result["rejected_indices"] == []
    assert result["details"]["order"] == ["repump", "nonfinite", "similarity"]
    np.testing.assert_array_equal(data, original)
    assert settings == before


def test_single_cycle_is_normalized_without_changing_input():
    assert apply_detector_filters(groups(1)[0], profile())["accepted_indices"] == [0]


def test_all_true_bypasses_nonfinite_criterion_without_replacing_OD():
    data = groups(1)
    data[:, 2] = 0  # denominator 0: OD contains a nonfinite result.
    settings = profile(nonfinite={"enabled": True, "max_percent": 0})
    settings["all_cycles"] = True
    result = apply_detector_filters(data, settings)
    assert result["accepted_indices"] == [0]
    assert result["details"]["stages"][1]["status"] == "bypassed_source_All_true"
    assert data[0, 2, 0] == 0


def test_nonfinite_uses_greater_equal_fraction_not_strict_greater():
    data = groups(3)
    data[0, 2, 0] = 0
    data[1, 2, :2] = 0
    data[2, 2, :3] = 0
    result = apply_detector_filters(data, profile(nonfinite={"enabled": True, "max_percent": 50}))
    assert result["accepted_indices"] == [0]
    assert result["rejected_indices"] == [1, 2]
    assert result["details"]["stages"][1]["nonfinite_counts"] == [1, 2, 3]
    assert result["reasons"] == [[], ["nonfinite_OD_quota"], ["nonfinite_OD_quota"]]


def test_zero_percent_is_not_an_implicit_disable():
    result = apply_detector_filters(groups(1), profile(nonfinite={"enabled": True, "max_percent": 0}))
    assert result["accepted_indices"] == []
    assert result["details"]["stages"][1]["nonfinite_counts"] == [0]


def test_nonfinite_counts_nan_and_both_infinities():
    data = groups(1)
    # 0/0 -> NaN; positive/0 -> +Inf OD; ratio0 -> -Inf OD.
    data[0, 2, :2] = 0
    data[0, 4, 0] = 0
    data[0, 4, 2] = 0
    result = apply_detector_filters(data, profile(nonfinite={"enabled": True, "max_percent": 75}))
    assert result["details"]["stages"][1]["nonfinite_counts"] == [3]
    assert result["rejected_indices"] == [0]


def test_missing_external_repump_rejects_pairs_before_other_filters():
    settings = profile(repump={"enabled": True, "version": REPUMP_VERSION,
                              "repump_min": 2., "repump_max": 4.},
                       similarity=similarity())
    result = apply_detector_filters(groups(), settings)
    assert result["accepted_indices"] == []
    assert result["reasons"] == [["repump_monitor_missing_or_unaligned"]] * 3
    assert result["details"]["stages"][2]["status"] == "no_remaining_cycles"


def test_repump_strict_bounds_keep_only_independently_aligned_interior():
    settings = profile(repump={"enabled": True, "version": REPUMP_VERSION,
                              "repump_min": 2., "repump_max": 4.})
    result = apply_detector_filters(groups(), settings,
                                   repump={"version": REPUMP_VERSION, "values": [2., 3., 4.]})
    assert result["accepted_indices"] == [1]
    assert result["rejected_indices"] == [0, 2]


@pytest.mark.parametrize("monitor", [[], {"values": [3., 3., 3.]},
                                     {"version": REPUMP_VERSION, "values": [3.]},
                                     {"version": REPUMP_VERSION, "values": [3., np.nan, 3.]},
                                     {"version": REPUMP_VERSION, "values": [[3.], [], [3.]]}])
def test_unqualified_or_wrong_length_repump_is_not_fabricated(monitor):
    settings = profile(repump={"enabled": True, "version": REPUMP_VERSION,
                              "repump_min": 2., "repump_max": 4.})
    assert apply_detector_filters(groups(), settings, repump=monitor)["accepted_indices"] == []


def test_similarity_is_batch_relative_and_uses_I_track_with_stop_excluded():
    data = groups()
    data[:, 2, :2] = 0
    data[:, 4, :2] = [[1., 0.], [2., 0.], [3., 0.]]
    data[:, 4, 2:] = 1000  # excluded stop boundary cannot change distances.
    data[:, 5] = [[1., 2., 3., 4.], [100., 200., 300., 400.], [1., 1., 1., 1.]]
    result = apply_detector_filters(data, profile(similarity=similarity()))
    assert result["accepted_indices"] == [0, 1]
    stage = result["details"]["stages"][2]
    assert stage["distances"] == [1., 2., 3.]
    assert stage["relative_limit"] == 2.
    assert stage["track"] == "detector_I"


def test_similarity_absolute_limit_adds_to_relative_limit_and_keeps_equality():
    data = groups(3, 2)
    data[:, 2] = 0
    data[:, 4] = [[1., 0.], [2., 0.], [3., 0.]]
    result = apply_detector_filters(data, profile(similarity=similarity(diff=5., min_distance=2.)))
    assert result["accepted_indices"] == [0, 1]


def test_similarity_population_excludes_previously_rejected_repump_cycles():
    data = groups(3, 2)
    data[:, 2] = 0
    data[:, 4] = [[1., 0.], [2., 0.], [3., 0.]]
    settings = profile(repump={"enabled": True, "version": REPUMP_VERSION,
                              "repump_min": 2., "repump_max": 4.},
                       similarity=similarity(diff=1.5))
    result = apply_detector_filters(data, settings,
                                   repump={"version": REPUMP_VERSION, "values": [0., 3., 3.]})
    assert result["accepted_indices"] == [1, 2]  # min is2 after first rejection, limit3.
    assert result["details"]["stages"][2]["source_indices"] == [1, 2]


def test_cosine_metric_zero_antiparallel_and_undefined_distance():
    data = groups(3, 2)
    data[:, 2] = [[1., 0.], [1., 0.], [1., 0.]]
    data[:, 4] = [[1., 0.], [0., 1.], [-1., 0.]]
    result = apply_detector_filters(data, profile(similarity=similarity(metric="cosine", diff=3.)))
    assert result["accepted_indices"] == [0]
    assert result["details"]["stages"][2]["distances"] == [0., 1., 2.]
    data[1, 4] = 0
    result = apply_detector_filters(data, profile(similarity=similarity(metric="cosine")))
    assert result["accepted_indices"] == []
    assert result["reasons"] == [["similarity_distance_undefined"]] * 3


def test_source_threshold_nonpositive_bypasses_unknown_ML_capability():
    settings = profile(similarity={"enabled": True, "threshold_ref_channel": 0., "mode": "ml"})
    assert apply_detector_filters(groups(), settings)["accepted_indices"] == [0, 1, 2]


def test_enabled_ML_and_unbounded_pixels_fail_profile_capability():
    with pytest.raises(ValueError, match="External ML"):
        validate_detector_filter_settings(profile(similarity=similarity(mode="ml")))
    with pytest.raises(ValueError, match="exceeds"):
        apply_detector_filters(groups(width=1), profile(similarity=similarity()))


@pytest.mark.parametrize("change", [lambda x: x.pop("all_cycles"),
                                    lambda x: x["filters"].pop("nonfinite"),
                                    lambda x: x["filters"]["repump"].update(enabled=1),
                                    lambda x: x["filters"].update(version="guess")])
def test_profiles_do_not_inherit_unknown_runtime_flags(change):
    settings = profile()
    change(settings)
    with pytest.raises(ValueError):
        validate_detector_filter_settings(settings)


@pytest.mark.parametrize("percent", [True, 60., -1, 101, None])
def test_nonfinite_percentage_requires_explicit_source_I32_domain(percent):
    with pytest.raises(ValueError, match="max_percent"):
        validate_detector_filter_settings(profile(nonfinite={"enabled": True, "max_percent": percent}))


def test_input_shape_dtype_and_nonfinite_RAW_rejected_without_mutation():
    for raw in [np.zeros((2, 5, 3)), np.zeros((6, 0)), np.ones((6, 2), dtype=bool),
                np.full((6, 2), np.inf)]:
        with pytest.raises(ValueError, match="six groups"):
            apply_detector_filters(raw, profile())


def test_empty_qualified_batch_has_no_fabricated_cycle():
    result = apply_detector_filters(np.empty((0, 6, 3), dtype=np.float32), profile())
    assert result["accepted_indices"] == result["rejected_indices"] == []
    assert result["accepted"] is False
