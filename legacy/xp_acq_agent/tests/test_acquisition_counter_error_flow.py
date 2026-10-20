"""Offline supplied-return native counter error traces on Python 3.4."""

import json
import unittest

from legacy.xp_acq_agent.elyse_agent.acquisition_counter_error_flow import (
    ABORT_TOP_LEVEL,
    NO_ERROR,
    NO_RESPONSE,
    RETURNED,
    UNASSIGNED,
    UNSUPPLIED,
    UNWIRED,
    CounterCallerResult,
    CounterErrorFlowResult,
    HandlerOutcome,
    NativeCall,
    NativeErrorCluster,
    NativeReturn,
    TaskReference,
    clear_all_errors,
    continue_counter_caller,
    execute_counter_error_flow,
)

ORIGINAL = TaskReference("original")
INPUT_ERROR = NativeErrorCluster(True, -10, "input")
POLL_ERROR = NativeErrorCluster(True, -20, "poll")
STOP_ERROR = NativeErrorCluster(True, -30, "stop")
PROPERTY_ERROR = NativeErrorCluster(True, -40, "property")
START_ERROR = NativeErrorCluster(True, -50, "start")


def bank(selector=1.0, offset=0):
    return tuple(float(index + offset) for index in range(32)) + (selector,)


class Harness(object):
    """Explicit fixture assumptions, never a native adapter or driver import."""

    def __init__(self):
        self.requests = []
        self.returns = {}
        self.final_poll = 0
        self.missing_poll = None
        self.raise_at = None
        self.error = RuntimeError("callback failure")

    def invoke(self, requested):
        self.requests.append(requested)
        if self.raise_at == requested.stage:
            raise self.error
        key = (requested.stage, requested.iteration)
        if key in self.returns:
            return self.returns[key]
        stage = requested.stage
        if stage == "read_co_pulse_done":
            data = (requested.iteration >= self.final_poll,)
            if self.missing_poll == requested.iteration:
                data = UNSUPPLIED
            return NativeReturn(
                TaskReference("poll%d" % requested.iteration), NO_ERROR, data
            )
        if stage == "stop_task":
            return NativeReturn(TaskReference("stopped"), NO_ERROR)
        if stage == "write_co_timing_properties":
            return NativeReturn(TaskReference("configured"), NO_ERROR)
        if stage == "start_task":
            return NativeReturn(TaskReference("started"), NO_ERROR)
        return NativeReturn(UNWIRED, NO_ERROR)

    def run(self, error_in=INPUT_ERROR):
        return execute_counter_error_flow(
            self.invoke, ORIGINAL, 0.125, -0.075, error_in
        )

    def call(self, stage):
        return [value for value in self.requests if value.stage == stage][0]


class CounterNativeTypesTests(unittest.TestCase):
    def test_error_cluster_exact_types_i32_and_immutability(self):
        for args in (
            (1, 1, "source"),
            (True, True, "source"),
            (False, 1.0, "source"),
            (False, 0, None),
        ):
            with self.assertRaises(TypeError):
                NativeErrorCluster(*args)
        for code in (-2147483649, 2147483648):
            with self.assertRaises(ValueError):
                NativeErrorCluster(False, code)
        self.assertEqual(NativeErrorCluster(False, -1, "warning").code, -1)
        self.assertEqual(NativeErrorCluster(True, 0).status, True)
        with self.assertRaises(AttributeError):
            INPUT_ERROR.status = False

    def test_task_reference_is_opaque_nonempty_immutable_string(self):
        for value in (None, "", 0, False):
            with self.assertRaises(ValueError):
                TaskReference(value)
        with self.assertRaises(AttributeError):
            ORIGINAL.token = "replacement"

    def test_native_return_rejects_coercible_clusters_and_mutable_data(self):
        for args in (
            ("task", NO_ERROR),
            (ORIGINAL, (False, 0, "")),
            (ORIGINAL, NO_ERROR, [True]),
            (ORIGINAL, NO_ERROR, (object(),)),
        ):
            with self.assertRaises(TypeError):
                NativeReturn(*args)

    def test_handler_completion_must_be_explicit_not_assumed_continue(self):
        for value in (None, "continue", "STOP", True):
            with self.assertRaises(ValueError):
                HandlerOutcome(value)
        with self.assertRaises(TypeError):
            HandlerOutcome(RETURNED)
        for disposition in (NO_RESPONSE, ABORT_TOP_LEVEL):
            with self.assertRaises(ValueError):
                HandlerOutcome(disposition, NO_ERROR)

    def test_documented_clear_all_profile_clears_clusters_not_task_state(self):
        for cluster in (
            INPUT_ERROR,
            STOP_ERROR,
            NativeErrorCluster(False, 12, "warning"),
            NativeErrorCluster(True, 0, "status-only"),
            NO_ERROR,
        ):
            self.assertIs(clear_all_errors(cluster), NO_ERROR)
        self.assertIs(INPUT_ERROR.status, True)
        self.assertEqual(INPUT_ERROR.code, -10)
        with self.assertRaises(TypeError):
            clear_all_errors((False, 0, ""))

    def test_nonfinite_supplied_data_is_rejected_for_strict_json_reports(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(TypeError):
                NativeReturn(ORIGINAL, NO_ERROR, (value,))

    def test_namedtuple_make_cannot_bypass_callback_cluster_validation(self):
        bad_error = NativeErrorCluster._make((1, 0, "invalid"))
        h = Harness()
        h.returns[("read_co_pulse_done", 0)] = NativeReturn._make(
            (ORIGINAL, bad_error, (True,))
        )
        with self.assertRaises(TypeError):
            h.run()


class CounterNativeWiringTests(unittest.TestCase):
    def test_call_order_original_poll_inputs_and_exact_source_properties(self):
        h = Harness()
        h.final_poll = 2
        result = h.run()
        self.assertEqual(
            [value.stage for value in h.requests],
            [
                "read_co_pulse_done",
                "wait_ms",
                "read_co_pulse_done",
                "wait_ms",
                "read_co_pulse_done",
                "wait_ms",
                "stop_task",
                "clear_errors",
                "write_co_timing_properties",
                "start_task",
            ],
        )
        self.assertEqual(
            [value.node_uid for value in h.requests],
            [
                "3202",
                "3194",
                "3202",
                "3194",
                "3202",
                "3194",
                "2976",
                "309",
                "3083",
                "3032",
            ],
        )
        polls = [value for value in h.requests if value.stage == "read_co_pulse_done"]
        for requested in polls:
            self.assertIs(requested.task_in, ORIGINAL)
            self.assertIs(requested.error_in, INPUT_ERROR)
            self.assertEqual(dict(requested.arguments)["property_code"], 6414)
        waits = [value for value in h.requests if value.stage == "wait_ms"]
        for requested in waits:
            self.assertIs(requested.task_in, UNWIRED)
            self.assertIs(requested.error_in, UNWIRED)
            self.assertEqual(dict(requested.arguments)["milliseconds"], 1)
        self.assertEqual(h.call("stop_task").task_in, TaskReference("poll2"))
        self.assertEqual(
            h.call("write_co_timing_properties").task_in, TaskReference("stopped")
        )
        self.assertEqual(h.call("start_task").task_in, TaskReference("configured"))
        self.assertEqual(
            dict(h.call("write_co_timing_properties").arguments),
            {
                "property_codes": (664, 4465, 4457),
                "initial_delay_ticks": 2,
                "low_ticks": 2,
                "high_ticks": 4294967294,
            },
        )
        self.assertEqual((result.delay_ticks, result.high_ticks), (2, 4294967294))
        self.assertEqual(result.poll_iterations, 3)
        self.assertEqual(result.exit_reason, "pulse_done")
        self.assertTrue(result.completed)

    def test_intermediate_poll_errors_and_task_tokens_are_overwritten(self):
        h = Harness()
        h.final_poll = 2
        h.returns[("read_co_pulse_done", 0)] = NativeReturn(
            TaskReference("first"), POLL_ERROR, (False,)
        )
        h.returns[("read_co_pulse_done", 1)] = NativeReturn(
            TaskReference("second"), STOP_ERROR, (False,)
        )
        result = h.run()
        self.assertIs(h.call("stop_task").error_in, NO_ERROR)
        self.assertEqual(h.call("stop_task").task_in, TaskReference("poll2"))
        self.assertIs(result.error_out, NO_ERROR)
        self.assertEqual(result.calls[0].returned.error, POLL_ERROR)
        self.assertEqual(result.calls[2].returned.error, STOP_ERROR)

    def test_final_poll_error_flows_to_stop_not_earlier_or_original_error(self):
        h = Harness()
        h.returns[("read_co_pulse_done", 0)] = NativeReturn(
            TaskReference("last"), POLL_ERROR, (True,)
        )
        h.run()
        self.assertIs(h.call("stop_task").error_in, POLL_ERROR)
        self.assertEqual(h.call("stop_task").task_in, TaskReference("last"))

    def test_stop_error_is_masked_by_explicitly_supplied_clear_errors_return(self):
        h = Harness()
        h.returns[("stop_task", None)] = NativeReturn(
            TaskReference("stopped-with-error"), STOP_ERROR
        )
        result = h.run()
        self.assertIs(h.call("clear_errors").error_in, STOP_ERROR)
        self.assertIs(h.call("write_co_timing_properties").error_in, NO_ERROR)
        self.assertEqual(
            h.call("write_co_timing_properties").task_in,
            TaskReference("stopped-with-error"),
        )
        self.assertEqual(
            dict(h.call("clear_errors").arguments),
            {
                "connected_error_input_slot": 4,
                "connected_error_output_slot": 0,
                "specific_error_code": 0,
                "specific_error_code_input_wired": False,
                "specific_error_code_provenance": (
                    "unwired connector default 0 means all errors"
                ),
            },
        )
        self.assertIs(result.error_out, NO_ERROR)

    def test_no_short_circuit_is_invented_for_property_error_input(self):
        h = Harness()
        # Arbitrary external fixtures expose the wire; they do not claim that
        # Clear Errors normally returns this or that the driver executes.
        h.returns[("clear_errors", None)] = NativeReturn(UNWIRED, STOP_ERROR)
        h.returns[("write_co_timing_properties", None)] = NativeReturn(
            TaskReference("properties-returned"), PROPERTY_ERROR
        )
        h.returns[("start_task", None)] = NativeReturn(
            TaskReference("start-returned"), START_ERROR
        )
        result = h.run()
        self.assertIs(h.call("write_co_timing_properties").error_in, STOP_ERROR)
        self.assertIs(h.call("start_task").error_in, PROPERTY_ERROR)
        self.assertEqual(result.task_out, TaskReference("start-returned"))
        self.assertIs(result.error_out, START_ERROR)
        self.assertTrue(result.completed)

    def test_incoming_error_status_does_not_gate_polls_or_force_done(self):
        h = Harness()
        h.final_poll = 100
        for index in range(22):
            h.returns[("read_co_pulse_done", index)] = NativeReturn(
                TaskReference("error%d" % index), POLL_ERROR, (False,)
            )
        result = h.run()
        self.assertEqual(result.poll_iterations, 22)
        self.assertEqual(result.exit_reason, "iteration_limit")
        self.assertFalse(result.final_pulse_done)
        self.assertEqual(len([v for v in h.requests if v.stage == "wait_ms"]), 22)
        self.assertIs(h.call("stop_task").error_in, POLL_ERROR)

    def test_missing_initial_pulse_value_suspends_before_stop(self):
        h = Harness()
        h.missing_poll = 0
        result = h.run()
        self.assertEqual(len(h.requests), 2)
        self.assertFalse(result.completed)
        self.assertEqual(result.suspended_at, "pulse_done_return")
        self.assertIs(result.error_out, UNASSIGNED)
        self.assertIs(result.task_out, UNASSIGNED)

    def test_final_limit_can_exit_even_when_done_value_is_unsupplied(self):
        h = Harness()
        h.final_poll = 100
        h.missing_poll = 21
        result = h.run()
        self.assertEqual(result.poll_iterations, 22)
        self.assertEqual(result.exit_reason, "iteration_limit")
        self.assertIs(result.final_pulse_done, UNSUPPLIED)
        self.assertTrue(result.completed)

    def test_invalid_done_data_is_not_converted_to_boolean(self):
        for data in ((1,), (0.0,), (), (True, False), ("True",)):
            h = Harness()
            h.returns[("read_co_pulse_done", 0)] = NativeReturn(
                ORIGINAL, NO_ERROR, data
            )
            with self.assertRaises(ValueError):
                h.run()
            self.assertEqual(len(h.requests), 2)

    def test_absent_or_coercible_native_return_is_rejected_without_next_call(self):
        for returned in (None, (ORIGINAL, NO_ERROR, (True,))):
            h = Harness()
            h.returns[("read_co_pulse_done", 0)] = returned
            with self.assertRaises(TypeError):
                h.run()
            self.assertEqual(len(h.requests), 1)

    def test_missing_task_wire_does_not_guess_original_task(self):
        for stage in ("read_co_pulse_done", "stop_task", "write_co_timing_properties"):
            h = Harness()
            iteration = 0 if stage == "read_co_pulse_done" else None
            data = (True,) if iteration == 0 else UNSUPPLIED
            h.returns[(stage, iteration)] = NativeReturn(UNWIRED, NO_ERROR, data)
            with self.assertRaises(TypeError):
                h.run()
            self.assertNotIn("start_task", [value.stage for value in h.requests])

    def test_python_exceptions_propagate_identity_without_clear_retry_or_cleanup(self):
        stages = (
            "read_co_pulse_done",
            "wait_ms",
            "stop_task",
            "clear_errors",
            "write_co_timing_properties",
            "start_task",
        )
        for stage in stages:
            h = Harness()
            h.raise_at = stage
            with self.assertRaises(RuntimeError) as caught:
                h.run()
            self.assertIs(caught.exception, h.error)
            self.assertEqual(h.requests[-1].stage, stage)
            self.assertEqual([value.stage for value in h.requests].count(stage), 1)

    def test_json_safe_report_has_exact_error_clusters_and_non_actuation_limits(self):
        h = Harness()
        h.returns[("start_task", None)] = NativeReturn(
            TaskReference("started"), START_ERROR
        )
        result = h.run()
        report = result.to_dict()
        self.assertEqual(json.loads(json.dumps(report)), report)
        self.assertEqual(
            report["error_out"], {"status": True, "code": -50, "source": "start"}
        )
        self.assertEqual(report["mode"], "supplied-return-only")
        for name in (
            "driver_semantics_inferred",
            "hardware_acknowledged",
            "native_timing_equivalence",
            "automatic_retry",
            "resource_release_requested",
        ):
            self.assertIs(report[name], False)
        self.assertIs(type(result), CounterErrorFlowResult)
        self.assertIs(type(result.calls[0].call), NativeCall)

    def test_bad_helper_arguments_rejected_before_invoking_callbacks(self):
        rows = (
            (None, ORIGINAL, 1.0, 2.0, INPUT_ERROR),
            (Harness().invoke, "task", 1.0, 2.0, INPUT_ERROR),
            (Harness().invoke, ORIGINAL, 1.0, 2.0, (False, 0, "")),
            (Harness().invoke, ORIGINAL, float("nan"), 2.0, INPUT_ERROR),
        )
        for args in rows:
            with self.assertRaises((TypeError, ValueError)):
                execute_counter_error_flow(*args)


class CounterNativeCallerTests(unittest.TestCase):
    def setUp(self):
        self.helper = Harness().run()
        self.trace = []
        self.images = [bank(16.0, 100), bank(10.0, 200)]

    def read(self):
        self.trace.append(("read",))
        return self.images.pop(0)

    def write(self, value):
        self.trace.append(("write", value))

    def publish(self, value):
        self.trace.append(("publish", value))

    def execute(self, outcome):
        return continue_counter_caller(
            self.helper, outcome, self.read, self.write, self.publish
        )

    def test_missing_response_and_abort_suspend_without_selector_or_cleanup(self):
        for outcome, expected in (
            (HandlerOutcome(NO_RESPONSE), "handler_response"),
            (HandlerOutcome(ABORT_TOP_LEVEL), "top_level_abort"),
        ):
            result = self.execute(outcome)
            self.assertEqual(result.suspended_at, expected)
            self.assertFalse(result.completed)
            self.assertEqual(result.completed_frames, ())
            self.assertEqual(self.trace, [])
            self.assertIs(result.reset_snapshot, UNASSIGNED)
            self.assertFalse(result.to_dict()["resource_release_requested"])
            metadata = result.to_dict()
            self.assertIs(metadata["source_dialog_mode_input_wired"], False)
            self.assertEqual(metadata["saved_connector_default"], 1)
            self.assertIs(metadata["deployed_xp_handler_binary_qualified"], False)
            self.assertIs(metadata["supplied_handler_disposition_hypothetical"], True)

    def test_unfinished_helper_never_reaches_handler_continuation(self):
        h = Harness()
        h.missing_poll = 0
        self.helper = h.run()
        result = self.execute(HandlerOutcome(RETURNED, NO_ERROR))
        self.assertEqual(result.suspended_at, "helper_not_completed")
        self.assertEqual(self.trace, [])

    def test_supplied_normal_return_allows_reset_even_if_error_remains(self):
        h = Harness()
        h.returns[("start_task", None)] = NativeReturn(ORIGINAL, START_ERROR)
        self.helper = h.run()
        reset, publication = tuple(self.images)
        result = self.execute(HandlerOutcome(RETURNED, START_ERROR))
        self.assertEqual(
            self.trace,
            [
                ("read",),
                ("write", reset[:32] + (-1.0,)),
                ("read",),
                ("publish", publication),
            ],
        )
        self.assertEqual(result.handler.error_out, START_ERROR)
        self.assertEqual(result.reset_snapshot, reset)
        self.assertEqual(result.requested_reset_snapshot, reset[:32] + (-1.0,))
        self.assertEqual(result.publication_snapshot, publication)
        self.assertEqual(result.completed_frames, (0, 1, 2))
        self.assertTrue(result.completed)
        self.assertIs(type(result), CounterCallerResult)
        self.assertEqual(json.loads(json.dumps(result.to_dict())), result.to_dict())
        self.assertIs(result.to_dict()["source_dialog_mode_input_wired"], False)
        self.assertEqual(result.to_dict()["saved_connector_default"], 1)
        self.assertIs(result.to_dict()["deployed_xp_handler_binary_qualified"], False)
        self.assertIs(
            result.to_dict()["supplied_handler_disposition_hypothetical"], True
        )

    def test_normal_return_is_not_invented_from_error_free_helper(self):
        self.assertIs(self.helper.error_out, NO_ERROR)
        result = self.execute(HandlerOutcome(NO_RESPONSE))
        self.assertFalse(result.completed)
        self.assertEqual(self.trace, [])

    def test_caller_exceptions_propagate_without_retry_or_publication(self):
        error = RuntimeError("write may already have applied")

        def raising_write(value):
            self.trace.append(("failed-write", value))
            raise error

        with self.assertRaises(RuntimeError) as caught:
            continue_counter_caller(
                self.helper,
                HandlerOutcome(RETURNED, NO_ERROR),
                self.read,
                raising_write,
                self.publish,
            )
        self.assertIs(caught.exception, error)
        self.assertEqual([row[0] for row in self.trace], ["read", "failed-write"])

    def test_bad_caller_bank_or_completion_rejected_not_implicitly_acknowledged(self):
        with self.assertRaises(TypeError):
            self.execute(None)
        with self.assertRaises(TypeError):
            self.execute(HandlerOutcome._make((RETURNED, UNASSIGNED)))
        self.images = [bank()[:-1]]
        with self.assertRaises(ValueError):
            self.execute(HandlerOutcome(RETURNED, NO_ERROR))
        self.assertEqual(self.trace, [("read",)])


if __name__ == "__main__":
    unittest.main()
