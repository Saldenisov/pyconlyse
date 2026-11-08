"""Analytical checks for preservation, independent detection, and RAW evidence."""

import unittest

import numpy as np
from utilities.dataio.temporal_outlier_correction import (
    OutlierConfig,
    correct_temporal_outliers,
    detect_unstable_repeats,
    fill_missing_neighbors,
)


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.t = np.arange(40, dtype=float)
        self.base = np.full((3, 40), 0.04)

    def test_independent_rows_and_adjacent_mean(self):
        y = self.base.copy()
        y[0, 10:13] = [0.041, 0.039, -0.03]
        y[1, 20] = 0.10
        result = correct_temporal_outliers(self.t, y)
        self.assertTrue(result.corrected_mask[0, 12])
        self.assertTrue(result.corrected_mask[1, 20])
        self.assertEqual(result.od[0, 12], 0.0395)
        self.assertEqual(result.od[1, 20], 0.04)
        self.assertFalse(result.corrected_mask[2].any())
        self.assertEqual(int(result.corrected_mask.sum()), 2)
        np.testing.assert_array_equal(y[2], self.base[2])

    def test_noise_below_absolute_threshold_is_preserved(self):
        rng = np.random.default_rng(519)
        y = self.base + rng.uniform(-0.001, 0.001, self.base.shape)
        result = correct_temporal_outliers(self.t, y)
        self.assertFalse(result.corrected_mask.any())
        np.testing.assert_array_equal(result.od, y)

    def test_noisy_wavelength_has_its_own_scale(self):
        y = self.base.copy()
        y[1] += 0.015 * np.sin(np.arange(40) * 2.2)
        y[:, 20] += 0.02
        result = correct_temporal_outliers(self.t, y)
        self.assertTrue(result.corrected_mask[0, 20])
        self.assertFalse(result.corrected_mask[1, 20])
        self.assertTrue(result.corrected_mask[2, 20])

    def test_real_step_is_preserved(self):
        y = self.base.copy()
        y[:, 15:] += 0.2
        result = correct_temporal_outliers(self.t, y)
        self.assertFalse(result.corrected_mask.any())
        np.testing.assert_array_equal(result.od, y)

    def test_resolved_peak_and_monotonic_decay_are_preserved(self):
        y = np.vstack(
            [
                0.1 * np.exp(-(((self.t - 15) / 5) ** 2)),
                0.1 * np.exp(-self.t / 8),
                0.002 * self.t,
            ]
        )
        result = correct_temporal_outliers(self.t, y)
        self.assertFalse(result.corrected_mask.any())

    def test_irregular_spacing_respects_linear_trend(self):
        t = np.cumsum(np.geomspace(0.1, 100, 40))
        y = np.vstack([0.00002 * t, 0.03 - 0.00001 * t])
        result = correct_temporal_outliers(t, y)
        self.assertFalse(result.corrected_mask.any())

    def test_missing_values_and_real_zero_are_preserved(self):
        y = self.base.copy()
        y[0, 10] = np.nan
        y[1] = 0
        result = correct_temporal_outliers(self.t, y)
        np.testing.assert_array_equal(np.isnan(result.od), np.isnan(y))
        np.testing.assert_array_equal(result.od[1], y[1])
        self.assertFalse(result.corrected_mask.any())

    def test_no_replacement_across_missing_neighbor(self):
        y = self.base.copy()
        y[0, 11], y[0, 12] = np.nan, -0.08
        result = correct_temporal_outliers(self.t, y)
        self.assertFalse(result.candidate_mask[0, 12])
        self.assertFalse(result.corrected_mask[0, 12])
        self.assertEqual(result.od[0, 12], -0.08)

    def test_short_scan_is_untouched(self):
        y = np.array([[0.0, 0.0, 1.0, 0.0, 0.0]])
        result = correct_temporal_outliers(np.arange(5), y)
        np.testing.assert_array_equal(result.od, y)

    def test_first_two_and_last_points_are_not_extrapolated(self):
        y = self.base.copy()
        y[:, [0, 1, -1]] = 0.5
        result = correct_temporal_outliers(self.t, y)
        self.assertFalse(result.corrected_mask.any())

    def test_adjacent_candidates_are_left_unchanged(self):
        y = self.base.copy()
        y[:, 15:17] = [0.3, -0.3]
        result = correct_temporal_outliers(
            self.t, y, OutlierConfig(max_neighbor_change_fraction=0.9)
        )
        self.assertTrue(result.candidate_mask[:, 15:17].all())
        self.assertFalse(result.corrected_mask.any())

    def test_protected_interval_preserves_known_physical_feature(self):
        y = self.base.copy()
        y[:, 20] = 0.2
        result = correct_temporal_outliers(
            self.t, y, OutlierConfig(protected_delay_intervals_ps=((19, 21),))
        )
        np.testing.assert_array_equal(result.od, y)

    def test_repeat_flag_lowers_threshold_without_forcing_change(self):
        y = self.base.copy()
        y[0] += 0.002 * np.sin(self.t * 2.0)
        y[0, 20] += 0.012
        normal = correct_temporal_outliers(self.t, y, OutlierConfig(sigma_multiplier=8))
        mask = np.zeros(40, dtype=bool)
        mask[20] = True
        suspect = correct_temporal_outliers(
            self.t, y, OutlierConfig(sigma_multiplier=8), mask
        )
        self.assertFalse(normal.corrected_mask[0, 20])
        self.assertTrue(suspect.corrected_mask[0, 20])
        self.assertFalse(suspect.corrected_mask[1:].any())

    def test_no_input_mutation_and_audit(self):
        y = self.base.copy()
        y[:, 20] = 0.2
        before = y.copy()
        result = correct_temporal_outliers(self.t, y)
        np.testing.assert_array_equal(y, before)
        self.assertEqual(result.audit()["corrected_cells"], 3)
        self.assertFalse(result.audit()["baseline_zero_correction"])

    def test_nonfinite_values_become_nan_not_interpolated(self):
        y = self.base.copy()
        y[0, 10] = np.inf
        result = correct_temporal_outliers(self.t, y)
        self.assertTrue(np.isnan(result.od[0, 10]))
        self.assertFalse(result.corrected_mask[0, 10])

    def test_invalid_axes_shapes_masks_and_thresholds(self):
        with self.assertRaises(ValueError):
            correct_temporal_outliers(self.t[::-1], self.base)
        with self.assertRaises(ValueError):
            correct_temporal_outliers(self.t, self.base.T)
        with self.assertRaises(ValueError):
            correct_temporal_outliers(
                self.t, self.base, unstable_delay_mask=np.ones(40)
            )
        with self.assertRaises(ValueError):
            OutlierConfig(min_excursion_od=-1)
        with self.assertRaises(ValueError):
            OutlierConfig(max_neighbor_change_fraction=1)


class RepeatQualityTests(unittest.TestCase):
    def test_elevated_scatter_and_nan_slots(self):
        w = np.linspace(450, 750, 9)
        blocks = [
            np.tile(np.array([0.039, 0.041, 0.040, np.nan])[:, None], (1, 9))
            for _ in range(20)
        ]
        blocks[10] = np.tile(np.array([-0.03, 0.09, 0.04, np.nan])[:, None], (1, 9))
        result = detect_unstable_repeats(blocks, w)
        self.assertEqual(np.flatnonzero(result.unstable_delay_mask).tolist(), [10])
        self.assertEqual(result.valid_repeats[10], 3)

    def test_one_or_zero_repeat_cannot_establish_scatter(self):
        w = np.linspace(450, 750, 9)
        result = detect_unstable_repeats([np.zeros((1, 9)), np.full((5, 9), np.nan)], w)
        self.assertFalse(result.unstable_delay_mask.any())
        self.assertTrue(np.isnan(result.spread_od).all())


class MissingPointTests(unittest.TestCase):
    def test_single_missing_delay_mean_is_unweighted(self):
        t = np.array([-10.0, 0.0, 1.0, 10.0])
        y = np.array([[0.0, 0.02, np.nan, 0.08], [0.1, 0.2, 0.3, 0.4]])
        result = fill_missing_neighbors(t, y)
        self.assertEqual(result.od[0, 2], 0.05)
        self.assertEqual(result.left_index[0, 2], 1)
        self.assertEqual(result.right_index[0, 2], 3)
        self.assertEqual(result.method[0, 2], 1)
        np.testing.assert_array_equal(result.od[1], y[1])
        self.assertTrue(np.isnan(y[0, 2]))

    def test_boundary_mean_of_two_closest_points(self):
        y = np.array([[np.nan, 0.01, 0.03, 0.2]])
        result = fill_missing_neighbors(np.arange(4), y)
        self.assertEqual(result.od[0, 0], 0.02)
        self.assertEqual(result.method[0, 0], 2)

    def test_boundary_nearest_and_preserve_options(self):
        y = np.array([[np.nan, 0.01, 0.03]])
        self.assertEqual(
            fill_missing_neighbors(np.arange(3), y, "nearest").od[0, 0], 0.01
        )
        self.assertTrue(
            np.isnan(fill_missing_neighbors(np.arange(3), y, "preserve").od[0, 0])
        )

    def test_missing_run_uses_original_bracket_without_cascade(self):
        y = np.array([[0.01, np.nan, np.nan, 0.05]])
        result = fill_missing_neighbors(np.arange(4), y)
        np.testing.assert_allclose(result.od[0, 1:3], 0.03)
        np.testing.assert_array_equal(result.left_index[0, 1:3], [0, 0])
        np.testing.assert_array_equal(result.right_index[0, 1:3], [3, 3])

    def test_no_finite_evidence_cannot_be_invented(self):
        result = fill_missing_neighbors(np.arange(4), np.full((1, 4), np.nan))
        self.assertFalse(result.filled_mask.any())
        self.assertTrue(np.isnan(result.od).all())

    def test_stable_replicates_are_not_flagged_by_absolute_od(self):
        w = np.linspace(450, 750, 9)
        blocks = [np.full((5, 9), 0.8) for _ in range(20)]
        result = detect_unstable_repeats(blocks, w)
        self.assertFalse(result.unstable_delay_mask.any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
