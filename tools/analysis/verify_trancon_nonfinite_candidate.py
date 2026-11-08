"""Test the historical-OpenG candidate, not original LabVIEW behavior."""

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from legacy.trancon_client.candidates.nan_inf_replaced.devtrancondependeciesnan_inf_replaced import nan_inf_replaced
from legacy.trancon_client.candidates.nan_inf_replaced.openg.devtrancon_analysisnonfinite_2026_10_03openg_sourcesearch_array__ogtk import search_array__ogtk


class NonfiniteCandidateTests(unittest.TestCase):
    def check(self, values, value=2.0):
        original = np.asarray(values).copy()
        expected = original.copy()
        expected[np.isposinf(original)] = value
        expected[np.isneginf(original)] = -value
        actual = np.asarray(nan_inf_replaced(values, value).out_with_nan_and_inf_replaced)
        np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(np.signbit(actual[~np.isnan(actual)]),
                                      np.signbit(expected[~np.isnan(expected)]))
        np.testing.assert_array_equal(values, original)  # immutable input
        return actual

    def test_adjacent_nonfinite_and_finite_preservation(self):
        self.check([3.0, float("nan"), float("inf"), -float("inf"), float("inf"), 4.0])

    def test_default_value_is_saved_two(self):
        np.testing.assert_array_equal(
            nan_inf_replaced([float("inf"), -float("inf")]).out_with_nan_and_inf_replaced, [2, -2])

    def test_empty_and_single_elements(self):
        self.assertEqual(nan_inf_replaced().out_with_nan_and_inf_replaced, [])
        for values in ([1.5], [float("nan")], [float("inf")], [-float("inf")]):
            self.check(values)

    def test_negative_replacement(self):
        self.check([float("nan"), float("inf"), -float("inf"), -3.0], -3.0)

    def test_zero_replacement_preserves_sign(self):
        actual = self.check([float("inf"), -float("inf"), 0.0, -0.0], 0.0)
        self.assertEqual(math.copysign(1, actual[1]), -1)

    def test_nonfinite_replacement_uses_original_indices(self):
        # All three search calls read original input, before the replacement loops.
        for value in (float("inf"), -float("inf"), float("nan")):
            self.check([float("inf"), -float("inf"), float("nan"), 1.0], value)

    def test_random_mask_and_no_mutation(self):
        values = np.random.default_rng(103).normal(size=1001)
        values[::7], values[::11], values[::17] = float("inf"), -float("inf"), float("nan")
        self.check(values.tolist(), 5.25)

    def test_substituted_openg_equality_preserves_nan(self):
        values = [float("nan"), float("inf"), -float("inf"), float("inf"), 5, 5]
        self.assertEqual(search_array__ogtk(values, float("nan")).indices_of_elements, [])
        self.assertEqual(search_array__ogtk(values, float("inf")).indices_of_elements, [1, 3])
        self.assertEqual(search_array__ogtk(values, 5).indices_of_elements, [4, 5])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NonfiniteCandidateTests))
    print(f"tests={result.testsRun}; native_execution=False; substitute_openg=True")
    raise SystemExit(not result.wasSuccessful())
