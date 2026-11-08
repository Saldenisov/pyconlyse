"""In-memory request order, supplied PSP errors and literal local assignments."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNWIRED,
    CallKey,
    ErrorCluster,
    ScriptedBoundary,
)
from DeviceServers.control.elyse_acq.vi_simulation.runtime_publication import (
    PUBLICATIONS,
    SOURCE,
    URI_PREFIX,
    publish,
)


class PublicationSimulationTests(unittest.TestCase):
    def snapshots(self):
        return {index: (index, name, True) for _, index, name in PUBLICATIONS}

    def test_all_requests_use_explicit_snapshots_and_have_no_transport(self):
        snapshots = self.snapshots()
        result = publish(ScriptedBoundary(), local_snapshots=snapshots)
        self.assertEqual(len(result.calls), 8)
        self.assertEqual(result.assignments, ())
        self.assertEqual(result.final_error, NO_ERROR)
        for call, (uid, index, name) in zip(result.calls, PUBLICATIONS):
            self.assertEqual(call.key, CallKey(SOURCE.name, uid))
            self.assertEqual(
                call.args,
                {
                    "uri": URI_PREFIX + name,
                    "local_index": index,
                    "data": snapshots[index],
                },
            )
            self.assertIs(call.task_in, UNWIRED)
        self.assertIs(result.calls[0].error_in, UNWIRED)

    def test_each_fault_is_forwarded_but_all_graph_requests_remain(self):
        for uid, _, _ in PUBLICATIONS:
            fault = ErrorCluster(True, -42, uid)
            boundary = ScriptedBoundary(errors={CallKey(SOURCE.name, uid): fault})
            result = publish(boundary, local_snapshots=self.snapshots())
            boundary.assert_all_fixtures_used()
            self.assertEqual(result.assignments, ((30, True), (45, True)))
            self.assertEqual(result.final_error, fault)
            self.assertEqual(len(result.calls), 8)
            observed = False
            for call in result.calls:
                if observed:
                    self.assertEqual(call.error_in, fault)
                observed |= call.key.node_uid == uid

    def test_final_success_can_mask_earlier_fault_if_boundary_supplies_it(self):
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCE.name, "2182"): ErrorCluster(True, -1),
                CallKey(SOURCE.name, "7486"): NO_ERROR,
            }
        )
        result = publish(boundary, local_snapshots=self.snapshots())
        boundary.assert_all_fixtures_used()
        self.assertEqual(result.assignments, ())

    def test_warning_is_not_a_stop_and_false_does_not_clear_prior_locals(self):
        warning = ErrorCluster(False, 7, "supplied warning")
        boundary = ScriptedBoundary(errors={CallKey(SOURCE.name, "7486"): warning})
        result = publish(boundary, local_snapshots=self.snapshots())
        self.assertEqual(result.final_error, warning)
        self.assertEqual(result.assignments, ())
        previous = {30: True, 45: True}
        previous.update(result.assignments)
        self.assertEqual(previous, {30: True, 45: True})

    def test_bad_or_missing_snapshot_rejected_before_requests(self):
        snapshots = self.snapshots()
        snapshots.pop(44)
        for bad in (
            snapshots,
            {**self.snapshots(), 44: [False]},
            {**self.snapshots(), 44: (object(),)},
        ):
            boundary = ScriptedBoundary()
            with self.assertRaisesRegex(ValueError, "Python-only guard"):
                publish(boundary, local_snapshots=bad)
            self.assertEqual(boundary.calls, ())

    def test_adapter_and_boundary_subclass_rejected_before_invoke(self):
        class Override(ScriptedBoundary):
            def invoke(self, *args, **kwargs):
                raise AssertionError("not allowed to invoke an executable override")

        for boundary in (object(), Override()):
            with self.assertRaisesRegex(TypeError, "in-memory ScriptedBoundary"):
                publish(boundary, local_snapshots=self.snapshots())


if __name__ == "__main__":
    unittest.main()
