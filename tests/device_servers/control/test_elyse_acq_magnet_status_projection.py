"""Pure magnet-event local status projection; no PSP or NI access."""

import unittest

from DeviceServers.control.elyse_acq.acq_status_projection import (
    MAGNET_COMPLETION_FIELDS,
    project_magnet_local_completion,
)


class MagnetStatusProjectionTests(unittest.TestCase):
    def test_each_event_assigns_only_its_literal_fields(self):
        self.assertEqual(set(MAGNET_COMPLETION_FIELDS), {16, 17, 25})
        eps = tuple(index % 2 == 0 for index in range(77))
        dps = tuple(index % 2 == 1 for index in range(29))
        for event_case, (eps_fields, dps_fields) in MAGNET_COMPLETION_FIELDS.items():
            with self.subTest(event_case=event_case):
                projected_eps, projected_dps = project_magnet_local_completion(
                    eps, dps, event_case=event_case
                )
                expected_eps, expected_dps = list(eps), list(dps)
                for index, value in eps_fields:
                    expected_eps[index] = value
                for index, value in dps_fields:
                    expected_dps[index] = value
                self.assertEqual(projected_eps, tuple(expected_eps))
                self.assertEqual(projected_dps, tuple(expected_dps))
        self.assertEqual(eps, tuple(index % 2 == 0 for index in range(77)))
        self.assertEqual(dps, tuple(index % 2 == 1 for index in range(29)))

    def test_start_then_zero_then_stop_preserves_unassigned_fields(self):
        eps, dps = tuple([False] * 77), tuple([False] * 29)
        for case in (16, 25, 17):
            eps, dps = project_magnet_local_completion(eps, dps, event_case=case)
        self.assertFalse(eps[58])
        self.assertFalse(eps[61])
        self.assertFalse(eps[64])
        self.assertTrue(eps[67])
        self.assertEqual((dps[20], dps[21], dps[23]), (False, False, False))

    def test_rejects_invalid_shape_type_or_event(self):
        for eps, dps, case in (
            ([False] * 76, [False] * 29, 16),
            ([False] * 76 + [1], [False] * 29, 16),
            ([False] * 77, [False] * 28, 16),
            ([False] * 77, [False] * 28 + [1], 16),
            ([False] * 77, [False] * 29, 22),
            ([False] * 77, [False] * 29, True),
        ):
            with self.subTest(case=case, eps_len=len(eps), dps_len=len(dps)):
                with self.assertRaises(ValueError):
                    project_magnet_local_completion(eps, dps, event_case=case)


if __name__ == "__main__":
    unittest.main()
