"""Non-actuating checks for the saved ACQ controlled-stop HT ramp."""

import unittest

from DeviceServers.control.elyse_acq.acq_shutdown_projection import (
    AcqPspErrorStopAssignment,
    CONTROLLED_STOP_HT_SUPPLY_FRAMES,
    CONTROLLED_STOP_PHASE_MARKERS,
    COOLING_STOP_C3_PULSE_FIELDS,
    COOLING_STOP_DPS_FIELD_VALUES,
    COOLING_STOP_EPS_FIELD_VALUES,
    COOLING_STOP_EXPLICIT_WAITS_S,
    HT_RAMP_AUX_PARAM50_VALUE,
    HT_RAMP_DECREMENT,
    HT_RAMP_EXIT_BELOW,
    HT_RAMP_WAIT_S,
    MAGNET_STOP_C3_FALSE_FIELDS,
    MAGNET_STOP_C6_ZERO_FIELDS,
    MAGNET_STOP_C7_ZERO_FIELDS,
    MAGNET_STOP_FRAME_WAITS_S,
    PULSE_POLL_INDEX_EXIT_ABOVE,
    PULSE_POLL_WAIT_S,
    PULSE_STOP_POST_WAIT_S,
    PULSE_STOP_TASK_FIELDS,
    STAGE_STOP_C4_PULSE_FIELDS,
    STAGE_STOP_INTERSTAGE_WAITS_S,
    controlled_stop_pulse_poll_exits,
    project_acq_psp_error_stop_assignment,
    project_controlled_stop_ht_ramp,
)


class ControlledStopHtRampProjectionTests(unittest.TestCase):
    def test_saved_threshold_step_and_wait_literals(self):
        self.assertEqual(HT_RAMP_EXIT_BELOW, 6.6)
        self.assertEqual(HT_RAMP_DECREMENT, 0.1)
        self.assertEqual(HT_RAMP_WAIT_S, 0.5)
        self.assertEqual(HT_RAMP_AUX_PARAM50_VALUE, 6.0)

    def test_phase_markers_and_ht_stop_frames_preserve_saved_order(self):
        self.assertEqual(
            CONTROLLED_STOP_PHASE_MARKERS,
            (6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0),
        )
        self.assertEqual(
            [(frame.frame_index, frame.c4_field19_write, frame.wait_s)
             for frame in CONTROLLED_STOP_HT_SUPPLY_FRAMES],
            [(0, False, 0.150), (1, True, None), (2, None, 1.0)],
        )

    def test_below_threshold_exits_without_command_write_or_wait(self):
        steps = project_controlled_stop_ht_ramp(6.5)
        self.assertEqual(len(steps), 1)
        self.assertTrue(steps[0].exits_loop)
        self.assertIsNone(steps[0].c9_field0_write)
        self.assertIsNone(steps[0].wait_s)
        self.assertEqual(steps[0].local_param48_mirror, 6.5)
        self.assertEqual(steps[0].local_param50_assignment, 6.0)

    def test_equal_threshold_decrements_once_then_exits(self):
        steps = project_controlled_stop_ht_ramp(6.6)
        self.assertEqual(len(steps), 2)
        self.assertFalse(steps[0].exits_loop)
        self.assertAlmostEqual(steps[0].c9_field0_write, 6.5)
        self.assertEqual(steps[0].wait_s, 0.5)
        self.assertTrue(steps[1].exits_loop)
        self.assertLess(steps[1].observed_c9_field0, 6.6)

    def test_each_write_is_previous_observation_minus_point_one(self):
        steps = project_controlled_stop_ht_ramp(7.0)
        self.assertTrue(steps[-1].exits_loop)
        for step in steps[:-1]:
            self.assertAlmostEqual(
                step.c9_field0_write,
                step.observed_c9_field0 - 0.1,
            )
            self.assertEqual(step.wait_s, 0.5)

    def test_python_only_guards_reject_nonfinite_or_unbounded_replay(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                project_controlled_stop_ht_ramp(value)
        with self.assertRaises(ValueError):
            project_controlled_stop_ht_ramp(8.0, max_iterations=1)
        with self.assertRaises(ValueError):
            project_controlled_stop_ht_ramp(7.0, max_iterations=0)

    def test_pulse_stop_poll_predicate_and_saved_literals(self):
        self.assertEqual(PULSE_STOP_TASK_FIELDS, (3, 4))
        self.assertEqual(PULSE_POLL_INDEX_EXIT_ABOVE, 40)
        self.assertEqual(PULSE_POLL_WAIT_S, 0.001)
        self.assertEqual(PULSE_STOP_POST_WAIT_S, 1.0)
        self.assertFalse(controlled_stop_pulse_poll_exits(False, 40))
        self.assertTrue(controlled_stop_pulse_poll_exits(False, 41))
        self.assertTrue(controlled_stop_pulse_poll_exits(True, 0))
        for done, index in ((1, 0), (False, -1), (False, 0.0)):
            with self.subTest(done=done, index=index), self.assertRaises(ValueError):
                controlled_stop_pulse_poll_exits(done, index)

    def test_magnet_stop_phase_preserves_selected_field_sets(self):
        self.assertEqual(MAGNET_STOP_C6_ZERO_FIELDS, (0, 1, 2, 3, 4, 5, 6, 7, 9))
        self.assertEqual(MAGNET_STOP_C7_ZERO_FIELDS, (0, 1, 3, 4, 5, 6, 7, 8, 9))
        self.assertEqual(
            MAGNET_STOP_C3_FALSE_FIELDS,
            (9, 11, 15, 17, 21, 23, 25, 27, 29,
             31, 32, 33, 34, 35, 36, 37, 38, 39),
        )
        self.assertEqual(MAGNET_STOP_FRAME_WAITS_S, (None, 1.0, None, 1.0))

    def test_stage_and_cooling_stop_field_projections(self):
        self.assertEqual(STAGE_STOP_C4_PULSE_FIELDS, (8, 17, 6, 4, 1))
        self.assertEqual(STAGE_STOP_INTERSTAGE_WAITS_S,
                         (1.0, 1.0, 1.0, 2.0, 1.0))
        self.assertEqual(COOLING_STOP_C3_PULSE_FIELDS, (1, 4))
        self.assertEqual(COOLING_STOP_EPS_FIELD_VALUES,
                         ((3, False), (2, False), (5, True), (1, False)))
        self.assertEqual(COOLING_STOP_DPS_FIELD_VALUES, ((1, False),))
        self.assertEqual(COOLING_STOP_EXPLICIT_WAITS_S, (0.4, 0.1))

    def test_saved_psp_error_arms_have_asymmetric_stop_assignments(self):
        self.assertEqual(
            project_acq_psp_error_stop_assignment("write"),
            AcqPspErrorStopAssignment(True, True, None),
        )
        self.assertEqual(
            project_acq_psp_error_stop_assignment("read"),
            AcqPspErrorStopAssignment(False, False, None),
        )
        with self.assertRaises(ValueError):
            project_acq_psp_error_stop_assignment("timeout")


if __name__ == "__main__":
    unittest.main()
