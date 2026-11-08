"""Non-actuating checks for saved ACQ impulsion event status assignments."""

import unittest

from DeviceServers.control.elyse_acq.acq_status_projection import (
    IMPULSION_START_DPS_FIELDS,
    IMPULSION_START_EPS_FIELDS,
    IMPULSION_STOP_DPS_FIELDS,
    IMPULSION_STOP_EPS_FIELDS,
    project_impulsion_modulator_local_completion,
)


class ImpulsionStatusProjectionTests(unittest.TestCase):
    def test_saved_field_sets_remain_distinct(self):
        self.assertEqual(IMPULSION_START_EPS_FIELDS, ((55, False), (52, True)))
        self.assertEqual(IMPULSION_START_DPS_FIELDS, ((18, False),))
        self.assertEqual(IMPULSION_STOP_EPS_FIELDS, ((42, True), (52, False)))
        self.assertEqual(IMPULSION_STOP_DPS_FIELDS, ((19, False),))

    def test_start_then_stop_leaves_stop_impulsion_ok_unassigned(self):
        eps, dps = [False] * 77, [False] * 29
        eps[55] = True
        dps[18] = True
        after_start, after_start_dps = project_impulsion_modulator_local_completion(
            eps, dps, start=True
        )
        self.assertFalse(after_start[55])
        self.assertTrue(after_start[52])
        self.assertFalse(after_start_dps[18])
        self.assertTrue(eps[55])
        dps_after = list(after_start_dps)
        dps_after[19] = True
        after_stop, after_stop_dps = project_impulsion_modulator_local_completion(
            after_start, dps_after, start=False
        )
        self.assertTrue(after_stop[42])
        self.assertFalse(after_stop[52])
        self.assertFalse(after_stop[55])
        self.assertFalse(after_stop_dps[19])

    def test_stop_preserves_preexisting_eps55(self):
        eps, dps = [False] * 77, [False] * 29
        eps[55] = True
        result, _ = project_impulsion_modulator_local_completion(
            eps, dps, start=False
        )
        self.assertTrue(result[55])

    def test_invalid_shape_or_action_rejected(self):
        for eps, dps, start in (([False] * 76, [False] * 29, True),
                                ([False] * 77, [False] * 28, False),
                                ([False] * 76 + [0], [False] * 29, True),
                                ([False] * 77, [False] * 29, 1)):
            with self.subTest(start=start), self.assertRaises(ValueError):
                project_impulsion_modulator_local_completion(
                    eps, dps, start=start
                )


if __name__ == "__main__":
    unittest.main()
