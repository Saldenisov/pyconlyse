"""Initial exchange is source-distinct from runtime, with no real adapter."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNSUPPLIED,
    CallKey,
    DigitalOutputBanks,
    ErrorCluster,
    LogicalAoBanks,
    SampleClockInputs,
    ScriptedBoundary,
    TaskReference,
    record_initial_io,
    record_postinit,
)
from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import SOURCE
from DeviceServers.control.elyse_acq.vi_simulation.startup_postinit import (
    DISABLED_UI,
    RESETS,
    TPG_BRANCHES,
)
from DeviceServers.control.elyse_acq.vi_simulation.startup_publication import (
    STARTUP_COMMANDS,
)


def inputs():
    commands = dict(STARTUP_COMMANDS)
    return dict(
        analog_tasks=tuple(TaskReference(f"C{i}AI") for i in (1, 2)),
        digital_tasks=tuple(
            TaskReference(f"C{i}{kind}") for kind in ("DI", "DO") for i in (3, 4, 5)
        ),
        output_tasks=tuple(TaskReference(f"C{i}AO") for i in (6, 7, 8, 9)),
        digital_outputs=DigitalOutputBanks(tuple(commands[i] for i in (17, 15, 13))),
        analog_outputs=LogicalAoBanks(tuple(commands[i] for i in (9, 10, 11, 12))),
    )


class StartupIoTests(unittest.TestCase):
    def test_saved_order_and_terminal_handler(self):
        result = record_initial_io(ScriptedBoundary(), **inputs())
        self.assertEqual(len(result.calls), 13)
        self.assertEqual(
            tuple(c.key.node_uid for c in result.calls),
            (
                "1269",
                "269",
                "232",
                "667",
                "1028",
                "2840",
                "38",
                "742",
                "592",
                "1696",
                "1989",
                "1200",
                "16070",
            ),
        )
        self.assertEqual(result.calls[-1].diagram_uid, "25990")
        self.assertTrue(all(c.error_in == NO_ERROR for c in result.calls))
        self.assertEqual(
            tuple(i for i, _ in result.local_assignments), (19, 20, 18, 16, 14)
        )

    def test_each_fault_leaves_request_graph_and_handler_intact(self):
        baseline = record_initial_io(ScriptedBoundary(), **inputs())
        fault = ErrorCluster(True, -901, "fixture")
        for call in baseline.calls:
            result = record_initial_io(
                ScriptedBoundary(errors={call.key: fault}), **inputs()
            )
            self.assertEqual(
                tuple(c.key for c in result.calls), tuple(c.key for c in baseline.calls)
            )
            self.assertEqual(result.calls[-1].returned.error, fault)
            self.assertEqual(result.calls[1].error_in, NO_ERROR)

    def test_not_a_runtime_frame_alias_or_arbitrary_frame_executor(self):
        from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import (
            _record_io_frame,
        )

        boundary = ScriptedBoundary()
        with self.assertRaises(ValueError):
            _record_io_frame(
                boundary, frame_uid="25990", handler_uid="11701", **inputs()
            )
        self.assertFalse(boundary.calls)


class PostInitTests(unittest.TestCase):
    clock = SampleClockInputs(8123.5, 17)

    def test_25_calls_and_ungated_saved_assignments(self):
        result = record_postinit(ScriptedBoundary(), clock=self.clock)
        self.assertEqual(len(result.calls), 25)
        self.assertEqual(
            tuple(c.key.node_uid for c in result.calls[-5:]),
            ("49978", "126853", "10951", "123241", "73977"),
        )
        self.assertEqual(result.local_assignments[-4:], RESETS)
        self.assertIs(dict(result.local_assignments)[52], UNSUPPLIED)
        self.assertIs(dict(result.local_assignments)[51], UNSUPPLIED)
        self.assertEqual(
            result.ui_assignments,
            tuple((uid, "DisabledEnum", 2) for uid in DISABLED_UI),
        )
        for uid, resource, _, _ in TPG_BRANCHES:
            c = next(c for c in result.calls if c.key.node_uid == uid)
            self.assertEqual(c.args, {"resource": resource, "baud_selector": 4})

    def test_each_fault_preserves_independent_resets_and_other_branch_inputs(self):
        baseline = record_postinit(ScriptedBoundary(), clock=self.clock)
        fault = ErrorCluster(True, -902, "fixture")
        for call in baseline.calls:
            result = record_postinit(
                ScriptedBoundary(errors={call.key: fault}), clock=self.clock
            )
            self.assertEqual(
                tuple(c.key for c in result.calls), tuple(c.key for c in baseline.calls)
            )
            self.assertEqual(result.local_assignments[-4:], RESETS)
            self.assertEqual(result.ui_assignments, baseline.ui_assignments)
            for uid in ("126853", "123241"):
                c = next(c for c in result.calls if c.key.node_uid == uid)
                self.assertEqual(c.error_in.value, "unwired")
                self.assertEqual(
                    c.returned.error, fault if c.key == call.key else NO_ERROR
                )

    def test_session_tokens_and_faults_are_fixtures_not_readiness(self):
        fault = ErrorCluster(True, -903)
        key = CallKey(SOURCE.name, "126853")
        boundary = ScriptedBoundary(
            tasks={key: TaskReference("COM1 fixture")}, errors={key: fault}
        )
        result = record_postinit(boundary, clock=self.clock)
        boundary.assert_all_fixtures_used()
        self.assertEqual(
            dict(result.local_assignments)[52], TaskReference("COM1 fixture")
        )
        self.assertEqual(result.branch_errors[1], fault)
        self.assertEqual(result.calls[-3].error_in, fault)
        self.assertEqual(result.local_assignments[-4:], RESETS)

    def test_missing_clock_or_real_boundary_rejected_before_requests(self):
        boundary = ScriptedBoundary()
        with self.assertRaises(TypeError):
            record_postinit(boundary, clock=None)
        self.assertFalse(boundary.calls)
        with self.assertRaises(TypeError):
            record_postinit(object(), clock=self.clock)


if __name__ == "__main__":
    unittest.main()
