import unittest

from supervision_reconstruction.domain.deviation import (
    DEVIATED_LINE_CHANNELS,
    DIRECT_LINE_CHANNELS,
    compute_deviation_flags,
)


class DeviationTests(unittest.TestCase):
    def test_direct_line_inventory_is_evidenced_and_complete(self) -> None:
        self.assertEqual(
            DIRECT_LINE_CHANNELS,
            (
                "dipole_1",
                "focale",
                "phase_hf_laser",
                "h1",
                "v1",
                "h2",
                "v2",
                "triplet_1_1",
                "triplet_1_2",
                "h3",
                "v3",
            ),
        )

    def test_deviated_line_inventory_is_evidenced_and_complete(self) -> None:
        self.assertEqual(
            DEVIATED_LINE_CHANNELS,
            ("q1", "q2", "t2_1", "t2_2", "h4", "v4", "dipole_2", "h5", "v5"),
        )

    def test_flags_use_absolute_difference_and_strict_greater_than(self) -> None:
        result = compute_deviation_flags(
            channels=("below", "equal", "above", "negative_direction"),
            commands={"below": 10.0, "equal": 10.0, "above": 10.0, "negative_direction": 3.0},
            readbacks={"below": 8.1, "equal": 8.0, "above": 7.9, "negative_direction": 5.5},
            threshold=2.0,
        )

        self.assertAlmostEqual(result.absolute_differences["below"], 1.9)
        self.assertEqual(result.absolute_differences["equal"], 2.0)
        self.assertAlmostEqual(result.absolute_differences["above"], 2.1)
        self.assertEqual(result.absolute_differences["negative_direction"], 2.5)
        self.assertEqual(
            result.orange_flags,
            {"below": False, "equal": False, "above": True, "negative_direction": True},
        )

    def test_per_channel_thresholds_and_missing_values_fail_closed(self) -> None:
        result = compute_deviation_flags(
            channels=("a", "b"),
            commands={"a": 5.0, "b": 5.0},
            readbacks={"a": 4.0, "b": 4.0},
            threshold={"a": 0.9, "b": 1.0},
        )
        self.assertEqual(result.orange_flags, {"a": True, "b": False})

        with self.assertRaises(KeyError):
            compute_deviation_flags(
                channels=("unmapped",),
                commands={},
                readbacks={"unmapped": 1.0},
                threshold=1.0,
            )

    def test_nonfinite_measurements_thresholds_and_negative_thresholds_are_rejected(self) -> None:
        for name, command, readback, threshold in (
            ("command", float("nan"), 0.0, 1.0),
            ("readback", 0.0, float("inf"), 1.0),
            ("threshold", 0.0, 0.0, float("nan")),
            ("threshold", 0.0, 0.0, float("inf")),
            ("threshold", 0.0, 0.0, -1.0),
        ):
            with self.assertRaisesRegex(ValueError, name):
                compute_deviation_flags(
                    channels=("one",),
                    commands={"one": command},
                    readbacks={"one": readback},
                    threshold=threshold,
                )
