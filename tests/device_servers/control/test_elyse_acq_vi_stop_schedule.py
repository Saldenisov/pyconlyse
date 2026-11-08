"""Supplied interleavings retain saved write/read polarity and body join order."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.stop_schedule import (
    RUNTIME_LOOPS,
    BodyCompleted,
    ErrorArmEntry,
    LocalAssignment,
    OuterTcpRead,
    StopLocalRead,
    replay,
)


class StopScheduleTests(unittest.TestCase):
    def test_all_snapshots_can_precede_fault_then_clear_and_all_continue(self):
        schedule = (
            tuple(StopLocalRead(loop) for loop in RUNTIME_LOOPS)
            + (
                ErrorArmEntry("40346"),
                LocalAssignment("50011"),
                LocalAssignment("50019"),
                ErrorArmEntry("40205"),
                LocalAssignment("85095"),
                LocalAssignment("68231"),
            )
            + tuple(BodyCompleted(loop) for loop in RUNTIME_LOOPS)
        )
        result = replay(schedule, stop_before=False, tcp_before=False)
        self.assertFalse(result.stop_after)
        self.assertFalse(result.tcp_after)
        self.assertFalse(any(dict(result.completed).values()))

    def test_true_snapshot_survives_later_false_assignment(self):
        schedule = (
            ErrorArmEntry("40346"),
            LocalAssignment("50011"),
            LocalAssignment("50019"),
            StopLocalRead("47483"),
            ErrorArmEntry("40205"),
            LocalAssignment("85095"),
            LocalAssignment("68231"),
            BodyCompleted("47483"),
            StopLocalRead("203"),
            BodyCompleted("203"),
        )
        result = replay(schedule, stop_before=False, tcp_before=False)
        self.assertTrue(dict(result.completed)["47483"])
        self.assertFalse(dict(result.completed)["203"])
        self.assertFalse(result.stop_after)

    def test_all_loop_exit_snapshots_can_be_true_but_outer_tcp_false(self):
        schedule = (
            (ErrorArmEntry("40346"), LocalAssignment("50011"), LocalAssignment("50019"))
            + tuple(StopLocalRead(loop) for loop in RUNTIME_LOOPS)
            + (
                ErrorArmEntry("40205"),
                LocalAssignment("85095"),
                LocalAssignment("68231"),
            )
            + tuple(BodyCompleted(loop) for loop in RUNTIME_LOOPS)
            + (OuterTcpRead(),)
        )
        result = replay(schedule, stop_before=False, tcp_before=False)
        self.assertTrue(all(dict(result.completed).values()))
        self.assertIs(result.outer_tcp_snapshot, False)

    def test_local_pair_is_not_atomic(self):
        result = replay(
            (ErrorArmEntry("40346"), LocalAssignment("50011"), StopLocalRead("47483")),
            stop_before=False,
            tcp_before=False,
        )
        self.assertTrue(result.stop_after)
        self.assertFalse(result.tcp_after)
        self.assertTrue(dict(result.snapshots)["47483"])

    def test_outer_read_requires_join_of_all_five_exits(self):
        with self.assertRaises(ValueError):
            replay(
                (StopLocalRead("47483"), BodyCompleted("47483"), OuterTcpRead()),
                stop_before=True,
                tcp_before=True,
            )

    def test_body_cannot_complete_without_its_entered_error_assignments(self):
        with self.assertRaises(ValueError):
            replay(
                (
                    StopLocalRead("203"),
                    ErrorArmEntry("40346"),
                    LocalAssignment("50011"),
                    BodyCompleted("203"),
                ),
                stop_before=False,
                tcp_before=False,
            )

    def test_unentered_assignment_or_duplicate_condition_rejected(self):
        with self.assertRaises(ValueError):
            replay((LocalAssignment("50011"),), stop_before=False, tcp_before=False)
        with self.assertRaises(ValueError):
            replay(
                (StopLocalRead("203"), StopLocalRead("203")),
                stop_before=False,
                tcp_before=False,
            )


if __name__ == "__main__":
    unittest.main()
