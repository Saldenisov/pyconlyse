"""Runtime faults, operator requests, two-loop completion and bypass paths."""

import itertools
import unittest
from collections import Counter
from unittest.mock import patch

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    CallKey,
    ErrorCluster,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import record_stop_io
from DeviceServers.control.elyse_acq.vi_simulation.outer_stop_schedule import (
    OUTER_LOOPS,
    ControlledFinalAssignment,
    ControlledFinalFrameEntered,
    EmergencyStopRead,
    FinalCleanupEntry,
    GeneralStopRead,
    OperatorArmReturned,
    OuterBodyReturned,
    OuterNextIteration,
    SuppliedOuterFlagChange,
    replay_outer_stop,
)
from DeviceServers.control.elyse_acq.vi_simulation.read_ni6071e import SOURCE as AI
from DeviceServers.control.elyse_acq.vi_simulation.rw_dio96 import DigitalOutputBanks
from DeviceServers.control.elyse_acq.vi_simulation.startup_publication import (
    STARTUP_COMMANDS,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    SuppliedStopChange,
    replay_runtime,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_schedule import (
    ERROR_SITES,
    RUNTIME_LOOPS,
    BodyCompleted,
    ErrorArmEntry,
    LocalAssignment,
    OuterTcpRead,
    StopLocalRead,
)
from DeviceServers.control.elyse_acq.vi_simulation.write_ni6703 import LogicalAoBanks


def runtime_join(tcp=True, prefix=(), stop=True):
    return replay_runtime(
        prefix
        + tuple(
            token
            for loop in RUNTIME_LOOPS
            for token in (StopLocalRead(loop), BodyCompleted(loop))
        )
        + (OuterTcpRead(),),
        stop_before=stop,
        tcp_before=tcp,
    )


def runtime_fault(case):
    return (ErrorArmEntry(case),) + tuple(
        LocalAssignment(node) for node, _, _ in ERROR_SITES[case][1]
    )


def final_writes():
    return (
        ControlledFinalFrameEntered(),
        ControlledFinalAssignment("43536"),
        ControlledFinalAssignment("18163"),
        OperatorArmReturned(),
    )


def late_returning_stop():
    return (
        (GeneralStopRead(),)
        + final_writes()
        + tuple(EmergencyStopRead(loop) for loop in OUTER_LOOPS)
        + tuple(OuterBodyReturned(loop) for loop in OUTER_LOOPS)
        + (FinalCleanupEntry(),)
    )


class OuterStopScheduleTests(unittest.TestCase):
    def run_outer(self, schedule, *, emergency=False, general=False, runtime=None):
        return replay_outer_stop(
            schedule,
            runtime=runtime_join() if runtime is None else runtime,
            emergency_stop=emergency,
            general_stop=general,
        )

    def test_false_tcp_bypasses_both_loops_without_a_staged_stop(self):
        result = self.run_outer(
            (FinalCleanupEntry(),), runtime=runtime_join(False), general=True
        )
        self.assertFalse(result.sampled_tcp)
        self.assertTrue(result.cleanup_entered)
        self.assertEqual(result.choices, ())
        self.assertEqual(result.final_assignments, ())
        self.assertTrue(result.memory_after.general_stop)
        self.assertFalse(result.memory_after.emergency_stop)

    def test_outer_requires_all_five_runtime_bodies_and_the_tcp_read(self):
        partial = replay_runtime((), stop_before=True, tcp_before=True)
        with self.assertRaisesRegex(ValueError, "five-loop runtime join"):
            self.run_outer((), runtime=partial)
        joined_without_read = replay_runtime(
            tuple(
                token
                for loop in RUNTIME_LOOPS
                for token in (StopLocalRead(loop), BodyCompleted(loop))
            ),
            stop_before=True,
            tcp_before=True,
        )
        with self.assertRaises(ValueError):
            self.run_outer((), runtime=joined_without_read)

    def test_each_publication_fault_can_enter_idle_outer_loops_not_shutdown(self):
        for case in ("28682", "40346"):
            with self.subTest(case=case):
                runtime = runtime_join(False, runtime_fault(case), False)
                schedule = ()
                for iteration in range(17):
                    if iteration:
                        schedule += tuple(
                            OuterNextIteration(loop) for loop in OUTER_LOOPS
                        )
                    schedule += (
                        GeneralStopRead(),
                        OperatorArmReturned(),
                        EmergencyStopRead("42592"),
                        EmergencyStopRead("41705"),
                        OuterBodyReturned("42592"),
                        OuterBodyReturned("41705"),
                    )
                result = self.run_outer(schedule, runtime=runtime)
                self.assertTrue(runtime.stop_after)
                self.assertTrue(result.sampled_tcp)
                self.assertFalse(
                    any(choice.sampled_general for choice in result.choices)
                )
                self.assertEqual(result.final_frame_entries, ())
                self.assertEqual(result.next_iteration_ready, OUTER_LOOPS)
                self.assertFalse(result.cleanup_ready)
                with self.assertRaisesRegex(ValueError, "two-loop outer join"):
                    self.run_outer(schedule + (FinalCleanupEntry(),), runtime=runtime)

    def test_receive_fault_then_supplied_stop_can_bypass_controlled_sequence(self):
        runtime = runtime_join(
            True, runtime_fault("40205") + (SuppliedStopChange(True),), True
        )
        result = self.run_outer((FinalCleanupEntry(),), runtime=runtime, general=True)
        self.assertFalse(result.sampled_tcp)
        self.assertEqual(result.final_frame_entries, ())
        self.assertTrue(result.cleanup_entered)

    def test_emergency_with_general_false_exits_bodies_without_sequence(self):
        schedule = (
            GeneralStopRead(),
            EmergencyStopRead("42592"),
            EmergencyStopRead("41705"),
            OperatorArmReturned(),
            OuterBodyReturned("42592"),
            OuterBodyReturned("41705"),
            FinalCleanupEntry(),
        )
        result = self.run_outer(schedule, emergency=True)
        self.assertEqual(result.choices[0].sequence_uid, None)
        self.assertEqual(result.final_frame_entries, ())
        self.assertEqual(result.exited_loops, OUTER_LOOPS)
        self.assertTrue(result.cleanup_entered)

    def test_true_condition_cannot_cancel_an_entered_general_sequence(self):
        partial = (EmergencyStopRead("42592"), GeneralStopRead())
        result = self.run_outer(partial, emergency=True, general=True)
        self.assertEqual(result.choices[0].sequence_uid, "51954")
        self.assertEqual(result.pending_snapshots, (("42592", 0, True),))
        self.assertFalse(result.cleanup_ready)
        for token in (OuterBodyReturned("42592"), FinalCleanupEntry()):
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.run_outer(partial + (token,), emergency=True, general=True)
        finished = self.run_outer(
            partial
            + final_writes()
            + (
                OuterBodyReturned("42592"),
                EmergencyStopRead("41705"),
                OuterBodyReturned("41705"),
                FinalCleanupEntry(),
            ),
            emergency=True,
            general=True,
        )
        self.assertEqual(finished.final_frame_entries, (0,))
        self.assertTrue(finished.cleanup_entered)

    def test_late_reads_exit_after_all_seven_phases_returned(self):
        result = self.run_outer(late_returning_stop(), general=True)
        self.assertEqual(result.final_frame_entries, (0,))
        self.assertEqual(result.returned_operator_arms, (0,))
        self.assertTrue(result.memory_after.emergency_stop)
        self.assertFalse(result.memory_after.general_stop)
        self.assertTrue(
            all(decision.sampled_emergency for decision in result.decisions)
        )
        self.assertTrue(result.cleanup_entered)

    def test_early_false_snapshots_require_another_iteration_after_sequence(self):
        schedule = (
            (
                GeneralStopRead(),
                EmergencyStopRead("41705"),
                EmergencyStopRead("42592"),
            )
            + final_writes()
            + tuple(OuterBodyReturned(loop) for loop in OUTER_LOOPS)
        )
        result = self.run_outer(schedule, general=True)
        self.assertTrue(result.memory_after.emergency_stop)
        self.assertEqual(result.next_iteration_ready, OUTER_LOOPS)
        self.assertFalse(result.cleanup_ready)
        schedule += tuple(OuterNextIteration(loop) for loop in OUTER_LOOPS)
        schedule += (
            GeneralStopRead(),
            OperatorArmReturned(),
            EmergencyStopRead("42592"),
            EmergencyStopRead("41705"),
            OuterBodyReturned("42592"),
            OuterBodyReturned("41705"),
            FinalCleanupEntry(),
        )
        final = self.run_outer(schedule, general=True)
        self.assertEqual(
            [(c.iteration, c.sampled_general) for c in final.choices],
            [(0, True), (1, False)],
        )
        self.assertEqual(final.final_frame_entries, (0,))
        self.assertTrue(final.cleanup_entered)

    def test_all24_local_orders_retain_four_outer_condition_pairs(self):
        counts = Counter()
        tokens = (
            ControlledFinalAssignment("18163"),
            ControlledFinalAssignment("43536"),
            EmergencyStopRead("41705"),
            EmergencyStopRead("42592"),
        )
        for order in itertools.permutations(tokens):
            with self.subTest(order=order):
                result = self.run_outer(
                    (GeneralStopRead(), ControlledFinalFrameEntered())
                    + order
                    + (
                        OperatorArmReturned(),
                        OuterBodyReturned("41705"),
                        OuterBodyReturned("42592"),
                    ),
                    general=True,
                )
                pair = tuple(d.sampled_emergency for d in result.decisions)
                counts[pair] += 1
                self.assertEqual(result.cleanup_ready, all(pair))
                self.assertTrue(result.memory_after.emergency_stop)
                self.assertFalse(result.memory_after.general_stop)
        self.assertEqual(
            counts,
            {(False, False): 8, (True, True): 8, (False, True): 4, (True, False): 4},
        )

    def test_external_change_cannot_reselect_an_already_entered_arm(self):
        result = self.run_outer(
            (GeneralStopRead(), SuppliedOuterFlagChange(47, False)) + final_writes(),
            general=True,
        )
        self.assertEqual(result.final_frame_entries, (0,))
        self.assertTrue(result.choices[0].sampled_general)

    def test_general_level_can_request_second_sequence_after_external_reassertion(self):
        first = (
            (
                GeneralStopRead(),
                EmergencyStopRead("42592"),
            )
            + final_writes()
            + (
                EmergencyStopRead("41705"),
                OuterBodyReturned("41705"),
                OuterBodyReturned("42592"),
                OuterNextIteration("42592"),
                SuppliedOuterFlagChange(47, True),
                GeneralStopRead(),
                EmergencyStopRead("42592"),
            )
        )
        pending = self.run_outer(first, general=True)
        self.assertEqual([c.sequence_uid for c in pending.choices], ["51954", "51954"])
        self.assertFalse(pending.cleanup_ready)
        finished = self.run_outer(
            first + final_writes() + (OuterBodyReturned("42592"), FinalCleanupEntry()),
            general=True,
        )
        self.assertEqual(finished.final_frame_entries, (0, 1))
        self.assertTrue(finished.cleanup_entered)

    def test_io_true_snapshot_still_requires_its_supplied_call_returns(self):
        result = self.run_outer(
            (
                EmergencyStopRead("41705"),
                GeneralStopRead(),
                EmergencyStopRead("42592"),
                OperatorArmReturned(),
                OuterBodyReturned("42592"),
            ),
            emergency=True,
        )
        self.assertEqual(result.exited_loops, ("42592",))
        self.assertEqual(result.inflight_loops, ("41705",))
        self.assertEqual(result.pending_snapshots, (("41705", 0, True),))
        self.assertFalse(result.cleanup_ready)

    def supplied_stop_io(self, *, emergency=False, error=None):
        boundary = ScriptedBoundary(
            errors={} if error is None else {CallKey(AI.name, "1269"): error}
        )
        banks = dict(STARTUP_COMMANDS)
        banks[12] = (12.7,) + banks[12][1:]
        result = record_stop_io(
            boundary,
            emergency_stop=emergency,
            analog_tasks=tuple(TaskReference(f"C{i}AI") for i in (1, 2)),
            digital_tasks=tuple(
                TaskReference(f"C{i}{direction}")
                for direction in ("DI", "DO")
                for i in (3, 4, 5)
            ),
            output_tasks=tuple(TaskReference(f"C{i}AO") for i in (6, 7, 8, 9)),
            digital_outputs=DigitalOutputBanks(tuple(banks[i] for i in (17, 15, 13))),
            analog_outputs=LogicalAoBanks(tuple(banks[i] for i in (9, 10, 11, 12))),
        )
        boundary.assert_all_fixtures_used()
        return result

    def test_faulted_runtime_stop_does_not_prevent_outer_io_requesting_prior_ht(self):
        runtime = runtime_join(False, runtime_fault("40346"), False)
        outer = self.run_outer(
            (GeneralStopRead(), OperatorArmReturned()), runtime=runtime
        )
        io = self.supplied_stop_io(emergency=outer.memory_after.emergency_stop)
        self.assertTrue(outer.memory_after.stop)
        self.assertFalse(io.sampled_should_stop)
        self.assertEqual(io.io_result.output.calls[3].args["data"][0], 6.35)
        self.assertEqual(io.io_result.calls[-1].key.node_uid, "55822")
        self.assertEqual(len(io.io_result.calls), 13)
        self.assertEqual(outer.final_frame_entries, ())
        self.assertFalse(outer.cleanup_ready)

    def test_returned_outer_io_fault_is_not_an_emergency_assignment(self):
        io = self.supplied_stop_io(error=ErrorCluster(True, -301, "supplied AI return"))
        self.assertFalse(io.sampled_should_stop)
        self.assertTrue(io.io_result.calls[-1].error_in.status)
        self.assertEqual(io.io_result.output.calls[3].args["data"][0], 6.35)
        result = self.run_outer(
            (EmergencyStopRead("41705"), OuterBodyReturned("41705"))
        )
        self.assertEqual(result.next_iteration_ready, ("41705",))
        self.assertFalse(result.memory_after.emergency_stop)

    def test_true_emergency_does_not_cancel_first_entered_io_cycle_requests(self):
        io = self.supplied_stop_io(emergency=True)
        self.assertTrue(io.sampled_should_stop)
        self.assertEqual(len(io.io_result.calls), 13)
        self.assertEqual(io.io_result.output.calls[3].args["data"][0], 6.35)
        result = self.run_outer(
            (EmergencyStopRead("41705"), OuterBodyReturned("41705")),
            emergency=True,
        )
        self.assertEqual(result.exited_loops, ("41705",))
        self.assertFalse(result.cleanup_ready)

    def test_partial_final_frame_does_not_become_complete_shutdown(self):
        prefix = (
            GeneralStopRead(),
            ControlledFinalFrameEntered(),
            ControlledFinalAssignment("18163"),
        )
        result = self.run_outer(prefix, general=True)
        self.assertTrue(result.memory_after.emergency_stop)
        self.assertTrue(result.memory_after.general_stop)
        self.assertFalse(result.cleanup_ready)
        with self.assertRaisesRegex(ValueError, "complete operator arm"):
            self.run_outer(prefix + (OperatorArmReturned(),), general=True)

    def test_exited_loop_is_absorbing_even_if_shared_emergency_clears(self):
        prefix = (
            EmergencyStopRead("41705"),
            OuterBodyReturned("41705"),
            SuppliedOuterFlagChange(46, False),
        )
        for token in (
            OuterNextIteration("41705"),
            EmergencyStopRead("41705"),
            OuterBodyReturned("41705"),
        ):
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.run_outer(prefix + (token,), emergency=True)

    def test_duplicate_or_unknown_reads_writes_and_returns_are_rejected(self):
        cases = (
            (GeneralStopRead(), GeneralStopRead()),
            (GeneralStopRead(), OperatorArmReturned(), OperatorArmReturned()),
            (GeneralStopRead(), ControlledFinalFrameEntered()),
            (EmergencyStopRead("41705"), EmergencyStopRead("41705")),
            (ControlledFinalAssignment("18163"),),
            (OuterNextIteration("41705"),),
            (EmergencyStopRead("102"),),
        )
        for schedule in cases:
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                self.run_outer(schedule)

    def test_invalid_final_frame_assignments_are_rejected(self):
        prefix = (GeneralStopRead(), ControlledFinalFrameEntered())
        for suffix in (
            (ControlledFinalAssignment("unknown"),),
            (ControlledFinalFrameEntered(),),
            (ControlledFinalAssignment("18163"), ControlledFinalAssignment("18163")),
        ):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                self.run_outer(prefix + suffix, general=True)

    def test_false_tcp_and_completed_traces_reject_further_runtime_work(self):
        with self.assertRaisesRegex(ValueError, "no entered outer loops"):
            self.run_outer((GeneralStopRead(),), runtime=runtime_join(False))
        with self.assertRaisesRegex(ValueError, "ends at cleanup entry"):
            self.run_outer(late_returning_stop() + (GeneralStopRead(),), general=True)

    def test_unmodeled_external_flags_must_be_explicit_boolean_values(self):
        for token, exception in (
            (SuppliedOuterFlagChange(45, True), ValueError),
            (SuppliedOuterFlagChange(True, True), ValueError),
            (SuppliedOuterFlagChange(46, 1), TypeError),
            (object(), TypeError),
        ):
            with self.subTest(token=token), self.assertRaises(exception):
                self.run_outer((token,))
        with self.assertRaises(TypeError):
            self.run_outer((), emergency=1)

    def test_model_has_no_network_sleep_ui_or_hardware_boundary(self):
        with (
            patch("socket.socket.connect", side_effect=AssertionError("network")),
            patch("time.sleep", side_effect=AssertionError("sleep")),
        ):
            result = self.run_outer(late_returning_stop(), general=True)
        self.assertTrue(result.cleanup_entered)


if __name__ == "__main__":
    unittest.main()
