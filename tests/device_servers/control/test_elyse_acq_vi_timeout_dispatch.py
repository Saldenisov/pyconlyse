"""Golden fixtures of bounded procedure selection and counter caller semantics."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    UNSUPPLIED,
    UNWIRED,
    ErrorCluster,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.timeout_dispatch import (
    TARGETS,
    counter_intent,
    counter_publication_frame,
    counter_reset_frame,
    procedure_dispatch,
)


class TimeoutDispatchProjectionTests(unittest.TestCase):
    def test_no_request_sets_action_false_and_raw_index_minus_one(self):
        result = procedure_dispatch((False,) * 29)
        self.assertEqual(
            (result.first_true_index, result.case_selector, result.bank43_assignment),
            (-1, 0, -1),
        )
        self.assertIs(result.action_assignment, False)
        self.assertIs(result.property_intent, UNWIRED)

    def test_all_24_explicit_targets(self):
        expected_events = (
            3,
            4,
            5,
            6,
            12,
            7,
            13,
            8,
            14,
            9,
            15,
            10,
            11,
            18,
            19,
            20,
            22,
            21,
            23,
            24,
            16,
            25,
            None,
            17,
        )
        for field, (ddo, _) in enumerate(TARGETS):
            with self.subTest(field=field):
                result = procedure_dispatch(tuple(i == field for i in range(29)))
                self.assertEqual(result.case_selector, field + 1)
                self.assertEqual(result.property_intent.target_ddo, ddo)
                self.assertEqual(
                    result.property_intent.registered_event, expected_events[field]
                )
                self.assertEqual(
                    result.property_intent.assignments,
                    (("Value", True), ("Val(Sgnl)", True)),
                )
                self.assertIs(result.property_intent.error_in, UNWIRED)
                self.assertIs(result.action_assignment, UNWIRED)

    def test_first_asserted_wins_without_clearing_any_request(self):
        snapshot = tuple(i in (1, 3, 15) for i in range(29))
        result = procedure_dispatch(snapshot)
        self.assertEqual(result.case_selector, 2)
        self.assertEqual(snapshot, tuple(i in (1, 3, 15) for i in range(29)))

    def test_five_tail_requests_keep_index_and_use_saved_default(self):
        for field in range(24, 29):
            result = procedure_dispatch(tuple(i == field for i in range(29)))
            self.assertEqual(result.case_selector, field + 1)
            self.assertEqual(result.bank43_assignment, field)
            self.assertIs(result.action_assignment, False)
            self.assertIs(result.property_intent, UNWIRED)

    def test_all_16_integer_counter_requests_use_c10_not_c11(self):
        tasks = tuple(TaskReference("task" + str(i)) for i in range(8))
        for n in range(1, 17):
            values = tuple(float(i) for i in range(32)) + (float(n),)
            result = counter_intent(values, tasks)
            q = (n - 1) // 2
            self.assertTrue(result.accepted)
            self.assertEqual(
                (
                    result.task_index,
                    result.task,
                    result.delay_index,
                    result.width_index,
                ),
                (q, tasks[q], 2 * q, 2 * q + 1),
            )
            self.assertEqual(
                (result.delay, result.width), (float(2 * q), float(2 * q + 1))
            )
            self.assertIs(result.error_in, UNWIRED)

    def test_outside_range_has_no_counter_call(self):
        tasks = tuple(TaskReference(str(i)) for i in range(8))
        for n in (-1.0, 0.0, 17.0, 18.0):
            result = counter_intent((0.0,) * 32 + (n,), tasks)
            self.assertFalse(result.accepted)
            self.assertIs(result.task, UNWIRED)

    def test_fractional_selector_admitted_but_not_coerced(self):
        tasks = tuple(TaskReference(str(i)) for i in range(8))
        for n in (0.1, 1.5, 16.9):
            result = counter_intent((0.0,) * 32 + (n,), tasks)
            self.assertTrue(result.accepted)
            self.assertIs(result.task_index, UNSUPPLIED)

    def test_error_return_does_not_gate_reset_after_frame_completion(self):
        values = tuple(float(i + 100) for i in range(32)) + (7.0,)
        for error in (NO_ERROR, ErrorCluster(True, -200001, "fixture fault")):
            reset = counter_reset_frame(values, helper_returned_error=error)
            self.assertEqual(reset, values[:32] + (-1.0,))
        self.assertEqual(values[32], 7.0)

    def test_publication_uses_its_own_snapshot_with_unwired_error(self):
        new_snapshot = (4.0,) * 32 + (9.0,)
        result = counter_publication_frame(new_snapshot)
        self.assertEqual(result.data, new_snapshot)
        self.assertTrue(result.uri.endswith("/C1011NI6602"))
        self.assertIs(result.error_in, UNWIRED)
        self.assertIs(result.returned_error_consumer, UNWIRED)

    def test_strict_fixture_shape_not_a_labview_coercion_claim(self):
        with self.assertRaises(TypeError):
            procedure_dispatch((False,) * 24)
        with self.assertRaises(TypeError):
            procedure_dispatch((0,) * 29)
        with self.assertRaises(TypeError):
            counter_publication_frame((0.0,) * 32)


if __name__ == "__main__":
    unittest.main()
