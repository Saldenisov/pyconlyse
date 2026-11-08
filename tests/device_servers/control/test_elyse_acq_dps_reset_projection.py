"""Non-actuating checks for saved ACQ DPS handler reset order."""

import unittest

from DeviceServers.control.elyse_acq.dps_bridge import (
    DPS_ACQ_EVENT_CASES,
    DPS_FIELD_BY_ACQ_EVENT_CASE,
    project_dps_handler_reset,
)


class DpsHandlerResetProjectionTests(unittest.TestCase):
    def test_all_23_handlers_clear_only_their_own_request_field(self):
        self.assertEqual(set(DPS_FIELD_BY_ACQ_EVENT_CASE), set(range(3, 26)))
        for case_index, field_index in DPS_FIELD_BY_ACQ_EVENT_CASE.items():
            with self.subTest(event_case=case_index, field=field_index):
                initial = [True] * 29
                result = project_dps_handler_reset(initial, case_index)
                self.assertEqual(len(result), 29)
                self.assertFalse(result[field_index])
                self.assertEqual(sum(not value for value in result), 1)
                self.assertEqual(initial, [True] * 29)

    def test_orphaned_pt_and_unrelated_trailing_fields_are_preserved(self):
        initial = [False] * 29
        initial[2] = True
        initial[22] = True
        initial[24:] = [True, False, True, False, True]
        result = project_dps_handler_reset(initial, 5)
        self.assertFalse(result[2])
        self.assertTrue(result[22])
        self.assertEqual(result[24:], tuple(initial[24:]))
        self.assertIsNone(DPS_ACQ_EVENT_CASES[22])

    def test_malformed_snapshot_or_event_is_rejected(self):
        for flags, event_case in (([False] * 28, 5),
                                  ([False] * 28 + [0], 5),
                                  ([False] * 29, 2),
                                  ([False] * 29, True)):
            with self.subTest(event_case=event_case), self.assertRaises(ValueError):
                project_dps_handler_reset(flags, event_case)


if __name__ == "__main__":
    unittest.main()
