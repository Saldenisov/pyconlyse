"""Explicit repeated fault/stop fixtures; no hardware or liveness guarantee."""

import itertools
import unittest
from collections import Counter
from unittest.mock import patch

from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import (
    project_outer_tcp_decision,
    project_stop_operator_iteration,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    NextIteration,
    StopMemory,
    SuppliedStopChange,
    project_stop_reset,
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
    replay,
)


def complete_all():
    return tuple(StopLocalRead(loop) for loop in RUNTIME_LOOPS) + tuple(
        BodyCompleted(loop) for loop in RUNTIME_LOOPS
    )


def fault(case):
    return (ErrorArmEntry(case),) + tuple(
        LocalAssignment(node) for node, _, _ in ERROR_SITES[case][1]
    )


class MultiIterationStopTests(unittest.TestCase):
    def test_all720_writer_orders_retain_four_distinct_final_flag_pairs(self):
        counts = Counter()
        entries = tuple(ErrorArmEntry(case) for case in ERROR_SITES)
        writers = tuple(
            LocalAssignment(node)
            for _, writes in ERROR_SITES.values()
            for node, _, _ in writes
        )
        for order in itertools.permutations(writers):
            schedule = entries + order + complete_all()
            result = replay_runtime(schedule, stop_before=False, tcp_before=False)
            old = replay(schedule, stop_before=False, tcp_before=False)
            self.assertEqual(
                (result.stop_after, result.tcp_after), (old.stop_after, old.tcp_after)
            )
            self.assertEqual(
                tuple(d.sampled_stop for d in result.decisions),
                tuple(dict(old.completed).values()),
            )
            counts[(result.stop_after, result.tcp_after)] += 1
            if result.stop_after:
                joined = replay_runtime(
                    schedule + (OuterTcpRead(),), stop_before=False, tcp_before=False
                )
                self.assertIs(joined.outer_tcp_snapshot, result.tcp_after)
            else:
                with self.assertRaises(ValueError):
                    replay_runtime(
                        schedule + (OuterTcpRead(),),
                        stop_before=False,
                        tcp_before=False,
                    )
        self.assertEqual(
            counts,
            {
                (True, True): 320,
                (True, False): 160,
                (False, True): 160,
                (False, False): 80,
            },
        )

    def test_repeated_read_fault_can_leave_one_runtime_loop_continuing(self):
        others = tuple(loop for loop in RUNTIME_LOOPS if loop != "102")
        schedule = fault("40346") + tuple(StopLocalRead(loop) for loop in others)
        schedule += fault("40205") + (StopLocalRead("102"), BodyCompleted("102"))
        schedule += tuple(BodyCompleted(loop) for loop in others)
        for _ in range(32):
            schedule += (NextIteration("102"),) + fault("40205")
            schedule += (StopLocalRead("102"), BodyCompleted("102"))
        result = replay_runtime(schedule, stop_before=False, tcp_before=False)
        self.assertEqual(result.exited_loops, others)
        self.assertEqual(result.next_iteration_ready, ("102",))
        self.assertEqual(result.decisions[-1].iteration, 32)
        self.assertIsNone(result.outer_tcp_snapshot)
        with self.assertRaises(ValueError):
            replay_runtime(
                schedule + (OuterTcpRead(),), stop_before=False, tcp_before=False
            )
        recovered = replay_runtime(
            schedule
            + (
                NextIteration("102"),
                SuppliedStopChange(True),
                StopLocalRead("102"),
                BodyCompleted("102"),
                OuterTcpRead(),
            ),
            stop_before=False,
            tcp_before=False,
        )
        self.assertEqual(recovered.exited_loops, RUNTIME_LOOPS)
        self.assertIs(recovered.outer_tcp_snapshot, False)
        self.assertEqual(project_outer_tcp_decision(False), ())

    def test_same_error_arm_can_recur_but_only_in_a_new_owner_iteration(self):
        schedule = fault("40205") + (StopLocalRead("102"), BodyCompleted("102"))
        result = replay_runtime(
            schedule
            + (NextIteration("102"),)
            + fault("40205")
            + (StopLocalRead("102"), BodyCompleted("102")),
            stop_before=True,
            tcp_before=True,
        )
        self.assertEqual([d.iteration for d in result.decisions], [0, 1])
        self.assertFalse(any(d.sampled_stop for d in result.decisions))
        with self.assertRaises(ValueError):
            replay_runtime(schedule + fault("40205"), stop_before=True, tcp_before=True)

    def test_true_completed_loop_cannot_restart_when_shared_stop_clears(self):
        prefix = (StopLocalRead("47483"), BodyCompleted("47483")) + fault("40205")
        result = replay_runtime(prefix, stop_before=True, tcp_before=True)
        self.assertFalse(result.stop_after)
        self.assertEqual(result.exited_loops, ("47483",))
        for token in (
            NextIteration("47483"),
            StopLocalRead("47483"),
            BodyCompleted("47483"),
        ):
            with self.subTest(token=token), self.assertRaises(ValueError):
                replay_runtime(prefix + (token,), stop_before=True, tcp_before=True)

    def test_external_stop_does_not_retroactively_change_pending_snapshots(self):
        result = replay_runtime(
            (
                StopLocalRead("47483"),
                SuppliedStopChange(True),
                BodyCompleted("47483"),
                NextIteration("47483"),
                StopLocalRead("47483"),
            ),
            stop_before=False,
            tcp_before=False,
        )
        self.assertFalse(result.decisions[0].sampled_stop)
        self.assertEqual(result.pending_snapshots, (("47483", 1, True),))
        self.assertEqual(result.exited_loops, ())

    def test_error_arm_pair_must_complete_in_every_owner_iteration(self):
        schedule = fault("40205") + (
            StopLocalRead("102"),
            BodyCompleted("102"),
            NextIteration("102"),
            ErrorArmEntry("40205"),
            LocalAssignment("85095"),
            StopLocalRead("102"),
        )
        with self.assertRaises(ValueError):
            replay_runtime(
                schedule + (BodyCompleted("102"),), stop_before=True, tcp_before=True
            )

    def test_outer_join_is_terminal_and_cannot_be_read_twice(self):
        prefix = complete_all() + (OuterTcpRead(),)
        for token in (OuterTcpRead(), NextIteration("102"), SuppliedStopChange(False)):
            with self.subTest(token=token), self.assertRaises(ValueError):
                replay_runtime(prefix + (token,), stop_before=True, tcp_before=False)

    def test_initial_true_stop_still_needs_each_supplied_first_body_completion(self):
        with self.assertRaises(ValueError):
            replay_runtime((OuterTcpRead(),), stop_before=True, tcp_before=False)
        result = replay_runtime(
            complete_all() + (OuterTcpRead(),), stop_before=True, tcp_before=False
        )
        self.assertEqual(result.exited_loops, RUNTIME_LOOPS)
        self.assertTrue(all(d.iteration == 0 for d in result.decisions))

    def test_non_boolean_external_values_and_unknown_tokens_are_rejected(self):
        for schedule, exception in [
            ((SuppliedStopChange(1),), TypeError),
            ((object(),), TypeError),
            ((StopLocalRead("unknown"),), ValueError),
            ((NextIteration("102"),), ValueError),
            ((LocalAssignment("50011"),), ValueError),
        ]:
            with self.subTest(schedule=schedule), self.assertRaises(exception):
                replay_runtime(schedule, stop_before=False, tcp_before=False)

    def test_runtime_entry_flags_and_no_io_are_explicit(self):
        for value in (0, None, "False"):
            with self.assertRaises(TypeError):
                replay_runtime((), stop_before=value, tcp_before=False)
        with (
            patch("socket.socket.connect", side_effect=AssertionError("network")),
            patch("time.sleep", side_effect=AssertionError("sleep")),
        ):
            result = replay_runtime(complete_all(), stop_before=False, tcp_before=False)
        self.assertEqual(result.next_iteration_ready, RUNTIME_LOOPS)


class StopMemoryTests(unittest.TestCase):
    def test_all48_completed_frame_postconditions_preserve_untargeted_flags(self):
        for flags in itertools.product((False, True), repeat=4):
            before = StopMemory(*flags)
            for stage, expected in [
                ("post_init", StopMemory(flags[0], False, False, flags[3])),
                ("controlled_complete", StopMemory(flags[0], flags[1], True, False)),
                ("final_cleanup", StopMemory(False, flags[1], flags[2], flags[3])),
            ]:
                with self.subTest(flags=flags, stage=stage):
                    self.assertEqual(project_stop_reset(stage, before).after, expected)
                    self.assertEqual(before, StopMemory(*flags))

    def test_supplied_stale_stop_is_not_reset_by_the_initializer_gref_writes(self):
        initialized = project_stop_reset(
            "post_init", StopMemory(True, True, True, True)
        )
        self.assertEqual(initialized.after, StopMemory(True, False, False, True))
        result = replay_runtime(
            complete_all() + (OuterTcpRead(),),
            stop_before=initialized.after.stop,
            tcp_before=initialized.after.tcp_ed,
        )
        self.assertIs(result.outer_tcp_snapshot, False)
        self.assertEqual(project_outer_tcp_decision(result.outer_tcp_snapshot), ())
        final = project_stop_reset("final_cleanup", initialized.after)
        self.assertEqual(final.after, StopMemory(False, False, False, True))

    def test_initialization_clears_emergency_but_does_not_create_general_stop(self):
        initialized = project_stop_reset(
            "post_init", StopMemory(False, True, True, False)
        )
        entered = project_stop_operator_iteration(
            initialized.after.general_stop, initialized.after.emergency_stop
        )
        self.assertEqual(entered.sequence_requests, ())
        self.assertFalse(entered.sampled_should_stop)
        self.assertEqual(len(entered.enabled_property_requests), 5)

    def test_completion_and_cleanup_have_different_stop_flag_ownership(self):
        completed = project_stop_reset(
            "controlled_complete", StopMemory(True, True, False, True)
        )
        self.assertEqual(completed.independent_assignments, ((46, True), (47, False)))
        self.assertEqual(completed.after, StopMemory(True, True, True, False))
        cleaned = project_stop_reset("final_cleanup", completed.after)
        self.assertEqual(cleaned.independent_assignments, ((30, False),))
        self.assertEqual(cleaned.after, StopMemory(False, True, True, False))

    def test_missing_defaults_or_unknown_stage_are_not_synthesized(self):
        with self.assertRaises(TypeError):
            StopMemory()
        with self.assertRaises(TypeError):
            StopMemory(False, False, False, 0)
        with self.assertRaises(ValueError):
            project_stop_reset("restart", StopMemory(False, False, False, False))
        with self.assertRaises(TypeError):
            project_stop_reset("post_init", {})


if __name__ == "__main__":
    unittest.main()
