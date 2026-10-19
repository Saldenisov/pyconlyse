"""Pure startup projections; no PSP/NI transport and no hardware permission."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    UNWIRED,
    CallKey,
    ErrorCluster,
    ScriptedBoundary,
)
from DeviceServers.control.elyse_acq.vi_simulation.startup_publication import (
    COMMAND_PUBLICATIONS,
    SOURCE,
    STARTUP_COMMANDS,
    STATUS_PUBLICATIONS,
    publish_commands,
    publish_status,
)


def snapshots():
    return {
        36: (False,) * 29,
        44: (False,) * 77,
        7: tuple(i % 2 == 0 for i in range(80)),
    }


class StartupProjectionTests(unittest.TestCase):
    def test_command_values_order_and_unwired_first_error(self):
        boundary = ScriptedBoundary()
        result = publish_commands(boundary)
        self.assertEqual(result.local_assignments, STARTUP_COMMANDS)
        self.assertEqual(len(result.calls), 8)
        self.assertIs(result.calls[0].error_in, UNWIRED)
        self.assertEqual(
            [c.key.node_uid for c in result.calls[:-1]],
            [r[0] for r in COMMAND_PUBLICATIONS],
        )
        for call, (index, values) in zip(result.calls, STARTUP_COMMANDS):
            self.assertEqual(call.args["local_index"], index)
            self.assertEqual(call.args["data"], values)
        self.assertEqual(result.calls[-1].operation, "simple_error_handler")
        self.assertEqual(result.calls[-1].args["mode_connection"], "unwired")

    def test_fault_at_all_seven_command_writes_and_handler(self):
        for uid in [r[0] for r in COMMAND_PUBLICATIONS] + ["26161"]:
            fault = ErrorCluster(True, 71, uid)
            boundary = ScriptedBoundary(errors={CallKey(SOURCE.name, uid): fault})
            result = publish_commands(boundary)
            self.assertEqual(len(result.calls), 8)
            self.assertEqual(result.local_assignments, STARTUP_COMMANDS)
            self.assertEqual(result.final_error, NO_ERROR if uid == "26161" else fault)
            boundary.assert_all_fixtures_used()

    def test_raw_read_error_keeps_pilot_false_despite_successful_publications(self):
        boundary = ScriptedBoundary()
        before = snapshots()
        result = publish_status(
            boundary,
            raw_pilot_error=ErrorCluster(True, -200284),
            local_snapshots=before,
        )
        updated = result.local_assignments[0][1]
        self.assertFalse(updated[0])
        self.assertEqual(updated[1:], before[7][1:])
        self.assertEqual(result.final_error, NO_ERROR)
        self.assertTrue(before[7][0])  # Snapshot itself was not mutated.
        self.assertEqual(result.independent_wait_ms, 100)

    def test_no_error_and_warning_set_pilot_true_without_looking_at_code(self):
        for error in (
            NO_ERROR,
            ErrorCluster(False, 17, "warning"),
            ErrorCluster(False, -200284, "synthetic"),
        ):
            result = publish_status(
                ScriptedBoundary(), raw_pilot_error=error, local_snapshots=snapshots()
            )
            self.assertTrue(result.local_assignments[0][1][0])

    def test_three_status_write_faults_do_not_change_pilot_calculation(self):
        for uid, *_ in STATUS_PUBLICATIONS:
            fault = ErrorCluster(True, 99, uid)
            boundary = ScriptedBoundary(errors={CallKey(SOURCE.name, uid): fault})
            result = publish_status(
                boundary, raw_pilot_error=NO_ERROR, local_snapshots=snapshots()
            )
            self.assertEqual(result.final_error, fault)
            self.assertEqual(len(result.calls), 3)
            self.assertEqual([i for i, _ in result.local_assignments], [7])
            self.assertTrue(result.local_assignments[0][1][0])
            self.assertIs(result.calls[0].error_in, UNWIRED)
            self.assertEqual(
                [c.key.node_uid for c in result.calls],
                [r[0] for r in STATUS_PUBLICATIONS],
            )
            boundary.assert_all_fixtures_used()

    def test_successful_later_boundary_can_clear_psp_error_not_raw_pilot_error(self):
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCE.name, "34463"): ErrorCluster(True, 3),
                CallKey(SOURCE.name, "34480"): NO_ERROR,
            }
        )
        result = publish_status(
            boundary, raw_pilot_error=ErrorCluster(True, 9), local_snapshots=snapshots()
        )
        self.assertEqual(result.final_error, NO_ERROR)
        self.assertFalse(result.local_assignments[0][1][0])
        self.assertTrue(result.calls[1].error_in.status)
        boundary.assert_all_fixtures_used()

    def test_command_error_not_connected_to_final_status_publication(self):
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCE.name, "16580"): ErrorCluster(True, 10),
            }
        )
        commands = publish_commands(boundary)
        status = publish_status(
            boundary, raw_pilot_error=NO_ERROR, local_snapshots=snapshots()
        )
        self.assertTrue(commands.final_error.status)
        self.assertIs(status.calls[0].error_in, UNWIRED)
        self.assertEqual(status.final_error, NO_ERROR)
        self.assertTrue(status.local_assignments[0][1][0])
        self.assertEqual(len(boundary.calls), 11)
        boundary.assert_all_fixtures_used()

    def test_reject_adapter_wrong_shapes_and_nonboolean_values_before_calls(self):
        class Adapter(ScriptedBoundary):
            pass

        with self.assertRaises(TypeError):
            publish_commands(Adapter())
        for field in (36, 44, 7):
            for value in ((), [False], (0,) * len(snapshots()[field])):
                values = snapshots()
                values[field] = value
                boundary = ScriptedBoundary()
                with self.assertRaises(ValueError):
                    publish_status(
                        boundary, raw_pilot_error=NO_ERROR, local_snapshots=values
                    )
                self.assertEqual(boundary.calls, ())
        with self.assertRaises(TypeError):
            publish_status(
                ScriptedBoundary(), raw_pilot_error=UNWIRED, local_snapshots=snapshots()
            )


if __name__ == "__main__":
    unittest.main()
