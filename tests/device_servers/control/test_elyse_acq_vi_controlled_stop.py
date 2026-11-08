"""Explicit snapshots, stage order and non-actuating stop/fault projections."""

import math
import unittest
from unittest.mock import patch

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNSUPPLIED,
    CallKey,
    ErrorCluster,
    SampleMatrix,
    ScriptedBoundary,
)
from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import (
    CONTROLLED_STOP,
    all_stop_phases,
    controlled_counter_should_stop,
    project_ht_ramp_iteration,
    project_outer_tcp_decision,
    project_stop_frame,
    project_stop_operator_iteration,
    record_stop_io,
)
from DeviceServers.control.elyse_acq.vi_simulation.read_ni6071e import SOURCE as AI
from tests.device_servers.control.test_elyse_acq_vi_runtime_io import run


class ControlledStopTests(unittest.TestCase):
    def test_fixed_sequence_wait_arguments_are_not_a_shutdown_latency(self):
        requested = sum(
            effect[1]
            for _, effects in all_stop_phases()
            for effect in effects
            if effect[0] == "wait"
        )
        # Excludes variable HT iterations, counter polls and concurrent I/O.
        # No claim about frame execution time or electrical pulse width.
        self.assertEqual(requested, 12850)

    def test_seven_phases_and_all_40_wrapper_leaf_plans_preserve_order(self):
        self.assertEqual(
            [uid for uid, _ in CONTROLLED_STOP],
            ["60323", "51962", "43360", "129793", "1722", "52159", "64826"],
        )
        self.assertEqual(len(all_stop_phases()), 40)
        self.assertEqual(
            project_stop_frame("60323", {}).loop_requests,
            (("ht_ramp", "18613", "42212"),),
        )
        self.assertEqual(
            [p[0] for p in project_stop_frame("51962", {}).subsequence_requests[0]],
            ["47671", "47989", "48537"],
        )

    def test_no_stop_frame_performs_any_network_or_sleep(self):
        snapshots = {
            9: (9.0,) * 10,
            10: (10.0,) * 10,
            15: (True,) * 32,
            17: (True,) * 40,
            36: (True,) * 29,
            44: (True,) * 77,
        }
        with (
            patch(
                "socket.socket.connect", side_effect=AssertionError("network forbidden")
            ),
            patch("time.sleep", side_effect=AssertionError("sleep forbidden")),
        ):
            for uid, _ in all_stop_phases():
                project_stop_frame(uid, snapshots)

    def test_strict_ht_threshold_and_independent_mirrored_read(self):
        for value in (-10.0, 0.0, math.nextafter(6.6, -math.inf)):
            result = project_ht_ramp_iteration((value,) + (0.0,) * 9)
            self.assertTrue(result.should_stop)
            self.assertEqual(dict(result.local_writes), {50: 6.0, 48: value})
            self.assertEqual(result.wait_requests_ms, ())
        result = project_ht_ramp_iteration((6.6,) + (1.0,) * 9, (99.0,) * 10)
        self.assertFalse(result.should_stop)
        self.assertEqual(dict(result.local_writes)[12], (6.6 - 0.1,) + (99.0,) * 9)
        self.assertEqual(result.wait_requests_ms, (500,))

    def test_ramp_requires_fresh_base_and_does_not_merge_other_writer(self):
        check = (12.7,) + (1.0,) * 9
        base = (3.0,) * 10
        with self.assertRaises(ValueError):
            project_ht_ramp_iteration(check)
        result = project_ht_ramp_iteration(check, base)
        self.assertEqual(dict(result.local_writes)[12], (12.7 - 0.1,) + (3.0,) * 9)
        self.assertEqual(check, (12.7,) + (1.0,) * 9)
        # A competing writer may keep restoring the checked command indefinitely.
        self.assertTrue(
            all(
                not project_ht_ramp_iteration(check, base).should_stop
                for _ in range(100)
            )
        )

    def test_invalid_and_nonfinite_dbldata_do_not_gain_fabricated_behavior(self):
        for snapshot in ((0.0,) * 9, (0,) * 10, (math.nan,) * 10, (math.inf,) * 10):
            with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                project_ht_ramp_iteration(snapshot)

    def test_isolated_12_7_command_needs_62_returning_decrement_frames(self):
        state = (12.7,) + (3.0,) * 9
        requested_wait = 0
        for iterations in range(100):
            result = project_ht_ramp_iteration(state, state)
            if result.should_stop:
                break
            requested_wait += sum(result.wait_requests_ms)
            state = dict(result.local_writes)[12]
        else:
            self.fail("bounded isolated normal-range fixture failed to exit")
        # Supplied unchanged read epochs and returning frames, not NI execution.
        self.assertEqual(iterations, 62)
        self.assertEqual(requested_wait, 31000)
        self.assertLess(state[0], 6.6)
        self.assertAlmostEqual(state[0], 6.5)
        self.assertEqual(state[1:], (3.0,) * 9)
        self.assertNotIn(12, dict(result.local_writes))

    def test_large_finite_seed_can_be_a_self_stalling_binary64_fixed_point(self):
        state = (1e200,) + (3.0,) * 9
        self.assertTrue(math.isfinite(state[0]))
        self.assertEqual(state[0] - 0.1, state[0])
        for _ in range(3):
            result = project_ht_ramp_iteration(state, state)
            self.assertFalse(result.should_stop)
            self.assertEqual(dict(result.local_writes)[12], state)
            self.assertEqual(result.wait_requests_ms, (500,))
        # Fixed-point state plus deterministic isolated step implies no progress.
        # This does NOT prove that such an out-of-range seed is reachable in NI.

    def test_counter_threshold_is_42_polls_not_time_or_error_gate(self):
        for uid in ("47770", "48062"):
            self.assertFalse(
                any(controlled_counter_should_stop(uid, i, False) for i in range(41))
            )
            self.assertTrue(controlled_counter_should_stop(uid, 41, False))
            self.assertTrue(controlled_counter_should_stop(uid, 0, True))
        with self.assertRaises(TypeError):
            controlled_counter_should_stop("47770", 0, 1)

    def test_output_zeroing_preserves_c6_field8_c7_field2(self):
        result = dict(
            project_stop_frame(
                "128452", {9: (9.0,) * 10, 10: (10.0,) * 10}
            ).local_writes
        )
        self.assertEqual(result[9], (0.0,) * 8 + (9.0, 0.0))
        self.assertEqual(result[10], (0.0, 0.0, 10.0) + (0.0,) * 7)
        self.assertEqual(result[50], 3.0)

    def test_duplicate_status_frames_are_retained(self):
        snapshots = {36: (True,) * 29, 44: (True,) * 77}
        first = project_stop_frame("54590", snapshots)
        second = project_stop_frame("58827", snapshots)
        self.assertEqual(first.local_writes, second.local_writes)
        self.assertNotEqual(first.diagram_uid, second.diagram_uid)
        self.assertEqual(
            dict(second.local_writes)[44][1:6], (False, False, False, True, True)
        )

    def test_same_frame_wait_and_local_writes_have_no_ordering_api(self):
        result = project_stop_frame("64826", {})
        self.assertEqual(dict(result.local_writes), {46: True, 47: False, 50: 0.0})
        self.assertEqual(result.wait_requests_ms, (1000,))
        self.assertFalse(hasattr(result, "executed"))
        pulse = project_stop_frame("54530", {17: (False,) * 40})
        self.assertEqual(pulse.wait_requests_ms, (150,))
        self.assertTrue(dict(pulse.local_writes)[17][4])

    def test_tcp_false_skips_controlled_stop_and_true_starts_two_loops(self):
        self.assertEqual(project_outer_tcp_decision(False), ())
        self.assertEqual(project_outer_tcp_decision(True), ("41705", "42592"))
        with self.assertRaises(TypeError):
            project_outer_tcp_decision(1)

    def test_emergency_stop_sample_does_not_cancel_entered_body(self):
        result = project_stop_operator_iteration(True, True)
        self.assertTrue(result.sampled_should_stop)
        self.assertEqual(result.sequence_requests, (CONTROLLED_STOP,))
        self.assertEqual(result.enabled_property_requests, ())
        idle = project_stop_operator_iteration(False, False)
        self.assertEqual(len(idle.enabled_property_requests), 5)
        self.assertEqual(idle.sequence_requests, ())
        self.assertEqual(idle.wait_requests_ms, (50,))

    def stop_io(self, boundary, stop=False):
        # Reuse immutable task/bank fixtures of the runtime caller, not its code.
        with patch(
            "tests.device_servers.control.test_elyse_acq_vi_runtime_io.record_runtime_io",
            side_effect=lambda b, **kw: record_stop_io(b, emergency_stop=stop, **kw),
        ):
            return run(boundary)

    def test_stop_io_mirrors_c2_input_field7_not_c1_or_dac(self):
        boundary = ScriptedBoundary(
            data={
                CallKey(AI.name, "1269"): SampleMatrix(((99.0,),) * 64),
                CallKey(AI.name, "269"): SampleMatrix(((2.0,),) * 64),
            }
        )
        result = self.stop_io(boundary, True)
        self.assertEqual(dict(result.scalar_assignments)[49], 2.0 * 2.44)
        self.assertEqual(result.io_result.calls[-1].key.node_uid, "55822")
        self.assertTrue(result.sampled_should_stop)
        self.assertEqual(result.wait_requests_ms, (50,))
        self.assertEqual(len(result.io_result.calls), 13)
        boundary.assert_all_fixtures_used()

    def test_short_c2_readback_does_not_invent_zero_or_previous_ht(self):
        result = self.stop_io(
            ScriptedBoundary(
                data={
                    CallKey(AI.name, "269"): SampleMatrix(((2.0,),) * 7),
                }
            )
        )
        self.assertIs(dict(result.scalar_assignments)[49], UNSUPPLIED)

    def test_every_injected_io_fault_remains_distinct_from_stop_condition(self):
        baseline = self.stop_io(ScriptedBoundary()).io_result
        for call in baseline.calls:
            result = self.stop_io(
                ScriptedBoundary(errors={call.key: ErrorCluster(True, -99)})
            )
            self.assertFalse(result.sampled_should_stop)
            self.assertEqual(
                tuple(c.key for c in result.io_result.calls),
                tuple(c.key for c in baseline.calls),
            )
            self.assertNotEqual(result.io_result.calls[-1].returned.error, NO_ERROR)


if __name__ == "__main__":
    unittest.main()
