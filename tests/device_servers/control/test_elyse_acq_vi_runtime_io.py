"""Supplied root I/O snapshots, returned errors and unresolved array tails."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNSUPPLIED,
    UNWIRED,
    CallKey,
    DigitalOutputBanks,
    ErrorCluster,
    LogicalAoBanks,
    SampleMatrix,
    ScriptedBoundary,
    TaskReference,
    record_runtime_io,
    record_runtime_publication,
)
from DeviceServers.control.elyse_acq.vi_simulation.read_ni6071e import SOURCE as AI
from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import (
    SOURCE as ROOT,
)
from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import (
    project_readback_cluster,
)
from DeviceServers.control.elyse_acq.vi_simulation.rw_dio96 import SOURCE as DIO


def run(boundary, **overrides):
    options = dict(
        analog_tasks=tuple(TaskReference(f"C{i}AI") for i in (1, 2)),
        digital_tasks=tuple(
            TaskReference(f"C{i}{direction}")
            for direction in ("DI", "DO")
            for i in (3, 4, 5)
        ),
        output_tasks=tuple(TaskReference(f"C{i}AO") for i in (6, 7, 8, 9)),
        digital_outputs=DigitalOutputBanks(tuple((True,) * n for n in (40, 32, 40))),
        analog_outputs=LogicalAoBanks(((0.0,) * 10,) * 4),
    )
    options.update(overrides)
    return record_runtime_io(boundary, **options)


class RuntimeIoGoldenTests(unittest.TestCase):
    def test_saved_helper_order_tasks_and_error_handler(self):
        result = run(ScriptedBoundary())
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
                "11701",
            ),
        )
        self.assertEqual(
            tuple(c.task_in.token for c in result.calls[:12]),
            (
                "C1AI",
                "C2AI",
                "C3DI",
                "C4DI",
                "C5DI",
                "C3DO",
                "C4DO",
                "C5DO",
                "C6AO",
                "C7AO",
                "C8AO",
                "C9AO",
            ),
        )
        self.assertEqual(result.calls[-1].key, CallKey(ROOT.name, "11701"))
        self.assertEqual(result.calls[-1].args["mode_connection"], "unwired")
        self.assertTrue(all(c.error_in == NO_ERROR for c in result.calls))
        self.assertEqual(
            tuple(len(bank) for bank in result.digital.do_banks.values), (40, 32, 40)
        )

    def test_all_thirteen_fault_sites_preserve_request_graph(self):
        baseline = run(ScriptedBoundary())
        fault = ErrorCluster(True, -99, "supplied return")
        for position, call in enumerate(baseline.calls):
            result = run(ScriptedBoundary(errors={call.key: fault}))
            self.assertEqual(
                tuple(c.key for c in result.calls), tuple(c.key for c in baseline.calls)
            )
            self.assertEqual(result.calls[position].returned.error, fault)
            self.assertEqual(result.calls[-1].returned.error, fault)
            # AI branches have no error wire between them.
            self.assertEqual(result.calls[1].error_in, NO_ERROR)
            if position < 2:
                self.assertEqual(result.calls[2].error_in, fault)
            elif position < 12:
                self.assertEqual(result.calls[position + 1].error_in, fault)

    def test_supplied_late_success_can_replace_prior_error(self):
        baseline = run(ScriptedBoundary())
        result = run(
            ScriptedBoundary(
                errors={
                    baseline.calls[2].key: ErrorCluster(True, -98),
                    baseline.calls[11].key: NO_ERROR,
                }
            )
        )
        self.assertEqual(result.calls[11].error_in.status, True)
        self.assertEqual(result.calls[-1].error_in, NO_ERROR)
        self.assertEqual(result.output.error_out, NO_ERROR)

    def test_complete_readbacks_have_saved_sizes_and_local_targets(self):
        boundary = ScriptedBoundary(
            data={
                CallKey(AI.name, "1269"): SampleMatrix(((2.0,),) * 64),
                CallKey(AI.name, "269"): SampleMatrix(((3.0,),) * 64),
                CallKey(DIO.name, "232"): (True,) * 64,
                CallKey(DIO.name, "667"): (False,) * 64,
                CallKey(DIO.name, "1028"): (True,) * 64,
            }
        )
        result = run(boundary)
        boundary.assert_all_fixtures_used()
        assignments = dict(result.local_assignments)
        self.assertEqual(tuple(assignments), (19, 20, 18, 16, 14))
        self.assertEqual(
            tuple(len(c.values) for c in assignments.values()), (64, 64, 56, 64, 56)
        )
        self.assertEqual(assignments[19].values[0], 20.0)
        self.assertTrue(all(c.complete for c in assignments.values()))

    def test_short_empty_and_unsupplied_arrays_do_not_fabricate_tail(self):
        for incoming, expected in (
            (UNSUPPLIED, UNSUPPLIED),
            ((), ()),
            ((True,), (True,)),
        ):
            projection = project_readback_cluster(incoming, 56)
            self.assertEqual(projection.known_prefix, expected)
            self.assertFalse(projection.complete)
            self.assertIs(projection.values, UNSUPPLIED)
        result = run(
            ScriptedBoundary(data={CallKey(AI.name, "1269"): SampleMatrix(())})
        )
        self.assertEqual(dict(result.local_assignments)[19].known_prefix, ())
        self.assertTrue(
            all(c.values is UNSUPPLIED for _, c in result.local_assignments)
        )

    def test_data_projection_is_not_fault_gated(self):
        result = run(
            ScriptedBoundary(
                errors={CallKey(DIO.name, "232"): ErrorCluster(True, -1)},
                data={CallKey(DIO.name, "232"): (True,) * 56},
            )
        )
        self.assertEqual(dict(result.local_assignments)[18].values, (True,) * 56)
        self.assertTrue(result.output.error_out.status)

    def test_card_fault_is_not_wired_to_next_frame_psp_stop_case(self):
        boundary = ScriptedBoundary(
            errors={CallKey(DIO.name, "232"): ErrorCluster(True, -1)},
            data={
                CallKey(AI.name, "1269"): SampleMatrix(((0.0,),) * 64),
                CallKey(AI.name, "269"): SampleMatrix(((0.0,),) * 64),
                CallKey(DIO.name, "232"): (False,) * 56,
                CallKey(DIO.name, "667"): (False,) * 64,
                CallKey(DIO.name, "1028"): (False,) * 56,
            },
        )
        io_result = run(boundary)
        self.assertTrue(io_result.calls[-1].error_in.status)
        snapshots = {
            field: cluster.values for field, cluster in io_result.local_assignments
        }
        snapshots.update({44: (False,), 38: (False,), 2: (0.0,)})
        published = record_runtime_publication(boundary, local_snapshots=snapshots)
        self.assertIs(published.calls[0].error_in, UNWIRED)
        self.assertEqual(published.final_error, NO_ERROR)
        self.assertEqual(published.assignments, ())
        self.assertEqual(len(boundary.calls), 21)

    def test_invalid_snapshot_and_adapter_rejected_without_calls(self):
        boundary = ScriptedBoundary()
        with self.assertRaises(ValueError):
            run(boundary, digital_outputs=DigitalOutputBanks(((False,) * 64,) * 3))
        with self.assertRaises(TypeError):
            run(boundary, output_tasks=())
        self.assertEqual(boundary.calls, ())
        with self.assertRaises(TypeError):
            run(object())


if __name__ == "__main__":
    unittest.main()
