"""Golden counter traces: bounded polling, ordinary tunnels and clear boundary."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNASSIGNED,
    UNSUPPLIED,
    CallKey,
    ErrorCluster,
    ScriptedBoundary,
    TaskReference,
    exact_u32_ticks,
    labview_u32_ticks,
    record_ni6602_reconfiguration,
)
from DeviceServers.control.elyse_acq.vi_simulation.write_ni6602 import (
    POLL_UID,
    POST_POLL_UIDS,
    SOURCE,
)

TASK = TaskReference("supplied-counter")
FAULT = ErrorCluster(True, -740, "supplied pulse fault")


def polls(values):
    return {CallKey(SOURCE.name, POLL_UID, i): (v,) for i, v in enumerate(values)}


def run(boundary, error=NO_ERROR):
    return record_ni6602_reconfiguration(
        boundary,
        task=TASK,
        delay_microseconds=10,
        width_microseconds=25,
        error_in=error,
    )


class CounterWriterGoldenTests(unittest.TestCase):
    def test_done_first_iteration_then_stop_clear_config_start(self):
        boundary = ScriptedBoundary(data=polls((True,)))
        result = run(boundary)
        boundary.assert_all_fixtures_used()
        self.assertEqual(
            (result.poll_iterations, result.exit_reason), (1, "pulse_done")
        )
        self.assertEqual(
            [c.key.node_uid for c in result.calls], [POLL_UID, "3194", *POST_POLL_UIDS]
        )
        self.assertEqual((result.delay_ticks, result.high_ticks), (200, 500))
        self.assertEqual(result.calls[-2].args["property_codes"], (664, 4465, 4457))
        self.assertEqual(result.calls[-2].args["initial_delay_ticks"], 200)
        self.assertEqual(result.calls[-2].args["low_ticks"], 200)
        self.assertEqual(result.calls[-2].args["high_ticks"], 500)

    def test_false_until_bound_means_22_not_20_iterations(self):
        boundary = ScriptedBoundary(data=polls((False,) * 22))
        result = run(boundary)
        boundary.assert_all_fixtures_used()
        self.assertEqual(
            (result.poll_iterations, result.exit_reason), (22, "iteration_limit")
        )
        self.assertFalse(result.final_pulse_done)
        self.assertEqual(len(result.calls), 48)
        self.assertEqual(
            [c.key.iteration for c in result.calls if c.key.node_uid == POLL_UID],
            list(range(22)),
        )

    def test_bound_can_exit_even_if_final_done_return_is_unknown(self):
        result = run(ScriptedBoundary(data=polls((False,) * 21)))
        self.assertEqual(result.exit_reason, "iteration_limit")
        self.assertIs(result.final_pulse_done, UNSUPPLIED)
        self.assertEqual(result.poll_iterations, 22)

    def test_unknown_first_done_value_is_not_false_or_success(self):
        result = run(ScriptedBoundary())
        self.assertEqual(result.exit_reason, "missing_poll_value")
        self.assertIs(result.error_out, UNASSIGNED)
        self.assertIs(result.final_pulse_done, UNSUPPLIED)
        self.assertEqual(len(result.calls), 2)

    def test_each_poll_reuses_original_task_and_error_not_previous_return(self):
        changed = TaskReference("supplied-intermediate-task")
        boundary = ScriptedBoundary(
            data=polls((False, True)),
            tasks={CallKey(SOURCE.name, POLL_UID, 0): changed},
            errors={CallKey(SOURCE.name, POLL_UID, 0): FAULT},
        )
        result = run(boundary)
        reads = [c for c in result.calls if c.key.node_uid == POLL_UID]
        self.assertEqual(
            [(c.task_in, c.error_in) for c in reads], [(TASK, NO_ERROR)] * 2
        )
        self.assertEqual(result.calls[4].task_in, TASK)
        self.assertEqual(result.calls[4].error_in, NO_ERROR)
        self.assertEqual(result.error_out, NO_ERROR)

    def test_last_poll_task_and_error_forwarded_to_stop(self):
        last_task = TaskReference("supplied-final-task")
        boundary = ScriptedBoundary(
            data=polls((False, True)),
            tasks={CallKey(SOURCE.name, POLL_UID, 1): last_task},
            errors={CallKey(SOURCE.name, POLL_UID, 1): FAULT},
        )
        result = run(boundary)
        stopped = result.calls[4]
        self.assertEqual((stopped.task_in, stopped.error_in), (last_task, FAULT))
        self.assertEqual(
            result.error_out, FAULT
        )  # Default fixture, not Clear Errors semantics.

    def test_poll_error_does_not_add_legacy_error_exit(self):
        result = run(ScriptedBoundary(data=polls((False, False, True))), FAULT)
        self.assertEqual(result.poll_iterations, 3)
        self.assertEqual(result.exit_reason, "pulse_done")
        self.assertTrue(result.error_out.status)

    def test_clear_return_can_mask_stop_fault_and_allow_clean_start_input(self):
        boundary = ScriptedBoundary(
            data=polls((True,)),
            errors={
                CallKey(SOURCE.name, "2976"): FAULT,
                CallKey(SOURCE.name, "309"): NO_ERROR,
            },
        )
        result = run(boundary)
        boundary.assert_all_fixtures_used()
        self.assertEqual(result.calls[3].error_in, FAULT)
        self.assertEqual(result.calls[4].error_in, NO_ERROR)
        self.assertEqual(result.calls[5].error_in, NO_ERROR)
        self.assertEqual(result.error_out, NO_ERROR)

    def test_each_post_poll_return_controls_next_edge_without_added_retry(self):
        for uid in POST_POLL_UIDS:
            with self.subTest(uid=uid):
                result = run(
                    ScriptedBoundary(
                        data=polls((True,)),
                        errors={CallKey(SOURCE.name, uid): FAULT},
                    )
                )
                self.assertEqual(len(result.calls), 6)
                self.assertEqual(result.error_out, FAULT)
                faulty = next(
                    i for i, c in enumerate(result.calls) if c.key.node_uid == uid
                )
                for call in result.calls[faulty + 1 :]:
                    self.assertEqual(call.error_in, FAULT)

    def test_exact_tick_subset_does_not_round_or_clamp_invalid_input(self):
        self.assertEqual(exact_u32_ticks(0.05), 1)
        self.assertEqual(exact_u32_ticks(2000), 40000)
        self.assertEqual(exact_u32_ticks(0), 0)  # Driver acceptance is not assumed.
        for value in (-1, 0.025, 2**32, float("nan"), float("inf"), True, "10"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                exact_u32_ticks(value)
        boundary = ScriptedBoundary()
        with self.assertRaises(ValueError):
            record_ni6602_reconfiguration(
                boundary,
                task=TASK,
                delay_microseconds=float("nan"),
                width_microseconds=25,
                error_in=NO_ERROR,
            )
        self.assertEqual(boundary.calls, ())

    def test_saved_u32_conversion_rounds_instead_of_truncating_half_ticks(self):
        for microseconds, expected in ((0.025, 0), (0.075, 2), (0.125, 2), (0.16, 3)):
            self.assertEqual(labview_u32_ticks(microseconds), expected)
        for value in (-1, float("nan"), float("inf"), 2**32, 10**1000, True):
            with self.assertRaises(ValueError):
                labview_u32_ticks(value)
        result = record_ni6602_reconfiguration(
            ScriptedBoundary(data=polls((True,))),
            task=TASK,
            delay_microseconds=0.075,
            width_microseconds=0.125,
            error_in=NO_ERROR,
        )
        self.assertEqual((result.delay_ticks, result.high_ticks), (2, 2))

    def test_poll_fixture_requires_exactly_one_boolean(self):
        for value in ((), (1,), (False, True), ("True",)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(ScriptedBoundary(data={CallKey(SOURCE.name, POLL_UID, 0): value}))

    def test_saved_i32_then_u32_path_is_used_by_writer_trace(self):
        result = record_ni6602_reconfiguration(
            ScriptedBoundary(data=polls((True,))),
            task=TASK,
            delay_microseconds=-0.05,
            width_microseconds=2147483648 / 20.0,
            error_in=NO_ERROR,
        )
        self.assertEqual(
            (result.delay_ticks, result.high_ticks), (4294967295, 2147483647)
        )
        self.assertEqual(result.calls[-2].args["low_ticks"], 4294967295)
        # Trace value is not evidence that a real NI task accepts it.

    def test_no_hardware_adapter_can_be_substituted(self):
        with self.assertRaisesRegex(TypeError, "in-memory ScriptedBoundary"):
            run(object())


if __name__ == "__main__":
    unittest.main()
