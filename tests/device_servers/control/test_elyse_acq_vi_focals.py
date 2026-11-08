"""Focal request schedules and supplied-error behavior, no serial operation."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNWIRED,
    CallKey,
    ErrorCluster,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.focal_helpers import (
    NODES,
    SOURCES,
    VALUES,
    record_focal_commands,
)


class FocalSimulationTests(unittest.TestCase):
    def run_helper(self, enabled=True, **kwargs):
        return record_focal_commands(
            enabled=enabled, resources=("COM10", "COM11", "COM12"), **kwargs
        )

    def test_on_and_off_all_18_calls_and_exact_settings(self):
        for enabled in (True, False):
            result = self.run_helper(enabled, boundary=ScriptedBoundary())
            self.assertEqual(len(result.calls), 18)
            self.assertEqual(result.error_out, NO_ERROR)
            for index, focal in enumerate((3, 2, 1)):
                calls = result.calls[index * 6 : (index + 1) * 6]
                self.assertEqual(
                    tuple(c.key.node_uid for c in calls), NODES[enabled][focal]
                )
                self.assertEqual(
                    calls[0].args,
                    {
                        "resource": "COM" + str(13 - focal),
                        "id_query": False,
                        "reset": True,
                    },
                )
                self.assertIs(calls[0].error_in, UNWIRED)
                voltage, slew, current = VALUES[focal]
                self.assertEqual(
                    [c.args for c in calls[1:]],
                    [
                        {"voltage": voltage},
                        {"current_slew": slew},
                        {"current": current},
                        {"enabled": enabled},
                        {},
                    ],
                )
                self.assertNotIn("baud", calls[0].args)

    def test_all_36_fault_sites_keep_chain_requests_and_other_branches_independent(
        self,
    ):
        for enabled in (True, False):
            for focal, uids in NODES[enabled].items():
                for uid in uids:
                    fault = ErrorCluster(True, -1, uid)
                    boundary = ScriptedBoundary(
                        errors={CallKey(SOURCES[enabled].name, uid): fault}
                    )
                    result = self.run_helper(enabled, boundary=boundary)
                    boundary.assert_all_fixtures_used()
                    self.assertEqual(result.error_out, fault)
                    self.assertEqual(len(result.calls), 18)
                    self.assertEqual(dict(result.branch_errors)[focal], fault)
                    self.assertTrue(
                        all(
                            e == NO_ERROR for f, e in result.branch_errors if f != focal
                        )
                    )

    def test_sessions_returned_by_initialize_flow_to_later_calls(self):
        tasks = {
            CallKey(SOURCES[False].name, uids[0]): TaskReference("supplied-F" + str(f))
            for f, uids in NODES[False].items()
        }
        boundary = ScriptedBoundary(tasks=tasks)
        result = self.run_helper(False, boundary=boundary)
        boundary.assert_all_fixtures_used()
        for index, focal in enumerate((3, 2, 1)):
            calls = result.calls[6 * index : 6 * (index + 1)]
            for call in calls[1:]:
                self.assertEqual(call.task_in, TaskReference("supplied-F" + str(focal)))

    def test_parallel_schedule_does_not_change_error_merge_priority(self):
        faults = {
            CallKey(SOURCES[True].name, NODES[True][f][-1]): ErrorCluster(True, -f)
            for f in (3, 2, 1)
        }
        for schedule in ((1, 2, 3), (2, 3, 1), (3, 2, 1)):
            result = self.run_helper(
                boundary=ScriptedBoundary(errors=faults), branch_order=schedule
            )
            self.assertEqual(result.error_out.code, -3)
            self.assertEqual(result.calls[0].key.node_uid, NODES[True][schedule[0]][0])

    def test_error_takes_priority_over_earlier_warning(self):
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCES[False].name, "594"): ErrorCluster(False, 12),
                CallKey(SOURCES[False].name, "2560"): ErrorCluster(True, -9),
            }
        )
        self.assertEqual(self.run_helper(False, boundary=boundary).error_out.code, -9)

    def test_downstream_success_can_mask_fault_without_controller_override(self):
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCES[False].name, "670"): ErrorCluster(True, -1),
                CallKey(SOURCES[False].name, "594"): NO_ERROR,
            }
        )
        result = self.run_helper(False, boundary=boundary)
        self.assertEqual(result.error_out, NO_ERROR)
        output = next(c for c in result.calls if c.key.node_uid == "790")
        self.assertTrue(output.error_in.status)
        self.assertEqual(output.args, {"enabled": False})

    def test_invalid_schedule_or_adapter_rejected_before_commands(self):
        for bad in ((), (1, 2, 2), (True, 2, 3), [1, 2, 3]):
            boundary = ScriptedBoundary()
            with self.assertRaises(ValueError):
                self.run_helper(boundary=boundary, branch_order=bad)
            self.assertEqual(boundary.calls, ())
        with self.assertRaisesRegex(TypeError, "in-memory ScriptedBoundary"):
            self.run_helper(boundary=object())


if __name__ == "__main__":
    unittest.main()
