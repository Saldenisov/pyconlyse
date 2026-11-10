import numpy as np
import pytest

from utilities.dataio.vd2_paired_od import BeamPair, TaggedFrame, pair_tagged_frames, reduce_paired_od


def frame(sequence, cycle, beam_on, counts, intensity=None):
    return TaggedFrame(sequence, cycle, beam_on, np.atleast_2d(counts), intensity)


def test_tags_recover_after_missing_frame_and_handle_base_first():
    pairs, incomplete = pair_tagged_frames([
        frame(10, 1, False, 100), frame(11, 1, True, 90),
        frame(12, 2, True, 100),
        frame(14, 3, True, 90), frame(15, 3, False, 100),
    ])
    assert incomplete == (2,)
    assert [(p.absorption.camera_sequence, p.base.camera_sequence) for p in pairs] == [(11, 10), (14, 15)]


def test_ambiguous_pulse_tags_are_rejected():
    with pytest.raises(ValueError, match="verified Boolean"):
        pair_tagged_frames([frame(10, 1, None, 100)])
    pairs, incomplete = pair_tagged_frames([frame(10, 1, False, 100), frame(11, 1, False, 100)])
    assert pairs == () and incomplete == (1,)


def test_two_averaging_orders_keep_distinct_results_after_background():
    pairs = [
        BeamPair(frame(0, 0, True, 20), frame(1, 0, False, 110)),
        BeamPair(frame(2, 1, True, 100), frame(3, 1, False, 110)),
    ]
    background, roi = [[10]], [[True]]
    of_means = reduce_paired_od(pairs, background, roi, method="od_of_means")
    mean_of_pairs = reduce_paired_od(pairs, background, roi, method="mean_pair_od")
    assert of_means.roi_mod == pytest.approx(1000 * np.log10(2))
    assert mean_of_pairs.roi_mod == pytest.approx(500 * (1 + np.log10(100 / 90)))
    assert mean_of_pairs.used == ((0, 1), (2, 3))
    np.testing.assert_array_equal(mean_of_pairs.valid_count, [[2]])


def test_matched_reference_can_be_reused_with_limits():
    pairs = [
        BeamPair(frame(0, 5, True, 90, 100), frame(1, 5, False, 200, 200)),
        BeamPair(frame(2, 6, True, 90, 100), frame(3, 6, False, 100, 100)),
        BeamPair(frame(4, 50, True, 90, 100), frame(5, 50, False, 300, 300)),
    ]
    result = reduce_paired_od(
        pairs, [[0]], [[True]], method="matched_base", max_cycle_gap=2, max_relative_mismatch=0.05,
    )
    assert result.used == ((0, 3), (2, 3))
    assert result.unmatched == (4,)
    assert result.roi_mod == pytest.approx(1000 * np.log10(100 / 90))


def test_excluded_and_nonpositive_pixels_are_not_substituted():
    pairs = [
        BeamPair(frame(0, 0, True, [0, 9]), frame(1, 0, False, [1, 11])),
        BeamPair(frame(2, 1, True, [5, 9]), frame(3, 1, False, [7, 11])),
    ]
    result = reduce_paired_od(pairs, [[1, 1]], [[True, True]], excluded_cycles=[1])
    assert result.used == ((0, 1),)
    assert np.isnan(result.od[0, 0])
    assert result.od[0, 1] == pytest.approx(np.log10(10 / 8))
    assert result.roi_mod is None
    np.testing.assert_array_equal(result.valid_count, [[0, 1]])
