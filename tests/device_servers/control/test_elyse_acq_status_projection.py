"""Offline checks for saved ACQ cooling-start local status writes."""

import unittest

from DeviceServers.control.elyse_acq.acq_status_projection import (
    COOLING_START_DPS_FIELDS,
    COOLING_START_EPS_FIELDS,
    COOLING_STOP_DPS_FIELDS,
    COOLING_STOP_EPS_FIELDS,
    COOLING_STOP_FRAME_WAITS,
    COOLING_FLOW_TRIP_DPS_FIELDS,
    COOLING_FLOW_TRIP_EPS_FIELDS,
    GENERAL_MODULATOR_STOP_DPS_FIELDS,
    GENERAL_MODULATOR_STOP_EPS_FIELDS,
    project_cooling_start_local_completion,
    project_cooling_stop_local_completion,
    project_cooling_flow_trip_local_completion,
    project_general_modulator_stop_local_completion,
    project_timeout_remote_eps_ingest,
)
from DeviceServers.control.elyse_acq.contracts import Operation
from DeviceServers.control.elyse_acq.plans import get_plan


class CoolingStartProjectionTests(unittest.TestCase):
    def test_frame_10_sets_exactly_six_local_status_bits(self):
        self.assertEqual(
            COOLING_START_EPS_FIELDS,
            ((0, False), (1, False), (2, True), (5, False), (8, True)),
        )
        self.assertEqual(COOLING_START_DPS_FIELDS, ((0, False),))
        old_eps = [True] * 77
        old_dps = [True] * 29
        eps, dps = project_cooling_start_local_completion(old_eps, old_dps)
        for index, value in COOLING_START_EPS_FIELDS:
            self.assertIs(eps[index], value)
        self.assertEqual(dps[0], False)
        self.assertTrue(all(eps[index] for index in range(77)
                            if index not in (0, 1, 2, 5, 8)))
        self.assertTrue(all(dps[index] for index in range(1, 29)))
        self.assertEqual(old_eps, [True] * 77)
        self.assertEqual(old_dps, [True] * 29)

    def test_rejects_wrong_shapes_and_non_boolean_fields(self):
        for eps, dps in (
            ([False] * 76, [False] * 29),
            ([False] * 76 + [1], [False] * 29),
            ([False] * 77, [False] * 28),
            ([False] * 77, [False] * 28 + [1]),
        ):
            with self.subTest(eps=len(eps), dps=len(dps)):
                with self.assertRaises(ValueError):
                    project_cooling_start_local_completion(eps, dps)

    def test_existing_non_actuating_plan_matches_four_pulse_targets(self):
        plan = get_plan("cooling.start")
        self.assertEqual(plan.legacy_event_case, 3)
        writes = [(step.targets, step.value) for step in plan.steps
                  if step.operation == Operation.WRITE_DIGITAL]
        self.assertEqual(writes, [
            (("C3_OUT_DIO96.00",), True),
            (("C3_OUT_DIO96.00",), False),
            (("C3_OUT_DIO96.03",), True),
            (("C3_OUT_DIO96.03",), False),
            (("C4_OUT_DIO96.00",), True),
            (("C4_OUT_DIO96.00",), False),
            (("C4_OUT_DIO96.02",), True),
            (("C4_OUT_DIO96.02",), False),
        ])
        waits = [step.duration_s for step in plan.steps
                 if step.operation == Operation.WAIT]
        self.assertEqual(waits, [1.0, 0.8, 1.0, 1.0, 0.5, 1.0, 5.0])

    def test_stop_frame_updates_only_its_five_local_status_bits(self):
        self.assertEqual(
            COOLING_STOP_FRAME_WAITS,
            ((0, 0.150), (2, 0.400), (3, 0.150), (4, 0.150), (6, 0.100)),
        )
        self.assertEqual(
            COOLING_STOP_EPS_FIELDS,
            ((1, False), (2, False), (3, False), (5, True)),
        )
        self.assertEqual(COOLING_STOP_DPS_FIELDS, ((1, False),))
        old_eps = [True] * 77
        old_dps = [True] * 29
        eps, dps = project_cooling_stop_local_completion(old_eps, old_dps)
        for index, value in COOLING_STOP_EPS_FIELDS:
            self.assertIs(eps[index], value)
        self.assertIs(dps[1], False)
        self.assertIs(eps[8], True)  # no GENERAL Mod. OK assignment in event 4
        self.assertTrue(all(eps[index] for index in range(77)
                            if index not in (1, 2, 3, 5)))
        self.assertTrue(all(dps[index] for index in range(29) if index != 1))
        self.assertEqual(old_eps, [True] * 77)
        self.assertEqual(old_dps, [True] * 29)

    def test_stop_projection_rejects_invalid_inputs(self):
        for eps, dps in (
            ([False] * 76, [False] * 29),
            ([False] * 76 + [1], [False] * 29),
            ([False] * 77, [False] * 28),
            ([False] * 77, [False] * 28 + [1]),
        ):
            with self.subTest(eps=len(eps), dps=len(dps)):
                with self.assertRaises(ValueError):
                    project_cooling_stop_local_completion(eps, dps)

    def test_start_then_stop_preserves_general_modulator_ok_local_flag(self):
        eps, dps = project_cooling_start_local_completion(
            [False] * 77, [False] * 29
        )
        self.assertTrue(eps[2])
        self.assertTrue(eps[8])
        eps, dps = project_cooling_stop_local_completion(eps, dps)
        self.assertFalse(eps[2])
        self.assertTrue(eps[5])
        self.assertTrue(eps[8])
        self.assertFalse(dps[0])
        self.assertFalse(dps[1])

    def test_timeout_flow_trip_sets_fault_without_clearing_general_modulator_ok(self):
        self.assertEqual(
            COOLING_FLOW_TRIP_EPS_FIELDS,
            ((1, True), (2, False), (3, False), (5, True)),
        )
        self.assertEqual(COOLING_FLOW_TRIP_DPS_FIELDS, ((1, False),))
        eps, dps = project_cooling_start_local_completion(
            [False] * 77, [False] * 29
        )
        eps, dps = project_cooling_flow_trip_local_completion(eps, dps)
        self.assertTrue(eps[1])
        self.assertFalse(eps[2])
        self.assertFalse(eps[3])
        self.assertTrue(eps[5])
        self.assertTrue(eps[8])
        self.assertFalse(dps[1])

    def test_timeout_flow_trip_rejects_invalid_inputs(self):
        for eps, dps in (
            ([False] * 76, [False] * 29),
            ([False] * 76 + [1], [False] * 29),
            ([False] * 77, [False] * 28),
            ([False] * 77, [False] * 28 + [1]),
        ):
            with self.subTest(eps=len(eps), dps=len(dps)):
                with self.assertRaises(ValueError):
                    project_cooling_flow_trip_local_completion(eps, dps)

    def test_general_stop_clears_five_stage_ok_flags_and_sets_five_stop_ok(self):
        self.assertEqual(
            GENERAL_MODULATOR_STOP_EPS_FIELDS,
            ((8, False), (14, False), (20, False), (26, False), (32, False),
             (11, True), (17, True), (23, True), (29, True), (35, True),
             (9, False)),
        )
        self.assertEqual(GENERAL_MODULATOR_STOP_DPS_FIELDS, ((3, False),))
        original_eps = [True] * 77
        original_dps = [True] * 29
        eps, dps = project_general_modulator_stop_local_completion(
            original_eps, original_dps
        )
        for index, value in GENERAL_MODULATOR_STOP_EPS_FIELDS:
            self.assertIs(eps[index], value)
        self.assertFalse(dps[3])
        self.assertEqual(original_eps, [True] * 77)
        self.assertEqual(original_dps, [True] * 29)

    def test_general_stop_rejects_invalid_inputs(self):
        for eps, dps in (
            ([False] * 76, [False] * 29),
            ([False] * 76 + [1], [False] * 29),
            ([False] * 77, [False] * 28),
            ([False] * 77, [False] * 28 + [1]),
        ):
            with self.subTest(eps=len(eps), dps=len(dps)):
                with self.assertRaises(ValueError):
                    project_general_modulator_stop_local_completion(eps, dps)

    def test_timeout_remote_snapshot_can_replace_locally_set_general_ok(self):
        local_eps, _ = project_cooling_start_local_completion(
            [False] * 77, [False] * 29
        )
        self.assertTrue(local_eps[8])
        stale_remote_eps = [False] * 77
        next_eps = project_timeout_remote_eps_ingest(stale_remote_eps)
        self.assertFalse(next_eps[8])
        self.assertTrue(local_eps[8])  # pure replay does not mutate prior state

    def test_timeout_remote_ingest_rejects_malformed_snapshot(self):
        for snapshot in ([False] * 76, [False] * 76 + [1]):
            with self.subTest(length=len(snapshot)):
                with self.assertRaises(ValueError):
                    project_timeout_remote_eps_ingest(snapshot)


if __name__ == "__main__":
    unittest.main()
