"""Literal comparator helper semantics, including the hardwired phase flag."""

import math
import unittest

from DeviceServers.control.elyse_acq.vi_simulation.deviation_helpers import (
    compare_line_cluster,
)


def cluster(count, command=1.0, readback=0.0):
    return tuple(
        (False, True, True, False, True, command, readback, True, False, True, False)
        for _ in range(count)
    )


class DeviationHelperTests(unittest.TestCase):
    def test_direct_phase_flag_is_false_even_when_deviation_exceeds_threshold(self):
        result = compare_line_cluster(cluster(11), 0.5, direct=True)
        self.assertEqual(tuple(c[2] for c in result), (True, True, False) + (True,) * 8)

    def test_all_nine_deviated_flags_use_the_comparator(self):
        result = compare_line_cluster(cluster(9), 0.5, direct=False)
        self.assertTrue(all(c[2] for c in result))

    def test_strict_greater_than_boundary(self):
        for value, expected in (
            (0.5, False),
            (math.nextafter(0.5, math.inf), True),
            (math.nextafter(0.5, -math.inf), False),
        ):
            result = compare_line_cluster(cluster(9, value), 0.5, direct=False)
            self.assertIs(result[0][2], expected)

    def test_difference_sign_is_removed(self):
        self.assertEqual(
            tuple(
                c[2] for c in compare_line_cluster(cluster(9, -1), 0.5, direct=False)
            ),
            tuple(c[2] for c in compare_line_cluster(cluster(9, 1), 0.5, direct=False)),
        )

    def test_preserves_other_fields_without_mutating_input(self):
        original = cluster(11)
        result = compare_line_cluster(original, 2.0, direct=True)
        for before, after in zip(original, result):
            self.assertEqual(after[:2], before[:2])
            self.assertEqual(after[3:], before[3:])
            self.assertTrue(before[2])

    def test_nan_is_not_an_invented_fault_or_clamp(self):
        for command, readback, threshold in (
            (math.nan, 0.0, 0.5),
            (math.inf, math.inf, 0.5),
            (1.0, 0.0, math.nan),
        ):
            result = compare_line_cluster(
                cluster(9, command, readback), threshold, direct=False
            )
            self.assertFalse(result[0][2])

    def test_infinite_difference_and_negative_threshold_are_literal(self):
        self.assertTrue(
            compare_line_cluster(cluster(9, math.inf), 0.5, direct=False)[0][2]
        )
        self.assertTrue(compare_line_cluster(cluster(9, 0), -0.1, direct=False)[0][2])

    def test_shape_guards_are_python_boundaries_not_equipment_interlocks(self):
        for value, direct in (
            ((), True),
            (cluster(9), True),
            (list(cluster(9)), False),
            (cluster(9), 1),
        ):
            with self.assertRaises(ValueError):
                compare_line_cluster(value, 0.5, direct=direct)


if __name__ == "__main__":
    unittest.main()
