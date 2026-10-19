"""Pure local EPS overlap replay; no PSP or hardware access."""

import unittest

from DeviceServers.control.elyse_acq.acq_status_projection import (
    HF_POWER_COMPLETION_FIELDS,
    project_hf_power_local_completion,
    project_impulsion_modulator_local_completion,
)


class HfStatusCollisionTests(unittest.TestCase):
    def test_hf_start_and_stop_assign_literal_local_fields_only(self):
        self.assertEqual(set(HF_POWER_COMPLETION_FIELDS), {18, 19})
        eps = tuple(i % 2 == 0 for i in range(77))
        dps = tuple(i % 2 == 1 for i in range(29))
        for case, (eps_fields, dps_fields) in HF_POWER_COMPLETION_FIELDS.items():
            with self.subTest(event_case=case):
                next_eps, next_dps = project_hf_power_local_completion(
                    eps, dps, event_case=case
                )
                expected_eps, expected_dps = list(eps), list(dps)
                for index, value in eps_fields:
                    expected_eps[index] = value
                for index, value in dps_fields:
                    expected_dps[index] = value
                self.assertEqual(next_eps, tuple(expected_eps))
                self.assertEqual(next_dps, tuple(expected_dps))

    def test_pulse_stop_can_set_hf_stop_ok_without_clearing_hf_start_ok(self):
        eps, dps = tuple([False] * 77), tuple([False] * 29)
        eps, dps = project_hf_power_local_completion(eps, dps, event_case=18)
        self.assertTrue(eps[39])
        self.assertFalse(eps[42])
        eps, dps = project_impulsion_modulator_local_completion(eps, dps, start=False)
        self.assertTrue(eps[39])
        self.assertTrue(eps[42])
        self.assertFalse(eps[52])
        self.assertFalse(eps[55])

    def test_invalid_shape_type_or_event_is_rejected(self):
        for eps, dps, case in (
            ([False] * 76, [False] * 29, 18),
            ([False] * 76 + [1], [False] * 29, 18),
            ([False] * 77, [False] * 28, 18),
            ([False] * 77, [False] * 28 + [1], 18),
            ([False] * 77, [False] * 29, 24),
            ([False] * 77, [False] * 29, True),
        ):
            with self.subTest(event_case=case):
                with self.assertRaises(ValueError):
                    project_hf_power_local_completion(eps, dps, event_case=case)


if __name__ == "__main__":
    unittest.main()
