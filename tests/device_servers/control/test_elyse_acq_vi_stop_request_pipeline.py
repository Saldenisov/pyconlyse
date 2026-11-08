"""Compose reviewed request facets with explicit event/frame fixture delivery.

No event queue is implemented. Applying a projected local write to the next
fixture snapshot represents a supplied single-writer ordering, not an atomic
global state or a promise that PSP, LabVIEW or hardware returned.
"""

import unittest
from unittest.mock import patch

from DeviceServers.control.elyse_acq.vi_simulation.boundary import UNWIRED
from DeviceServers.control.elyse_acq.vi_simulation.event_envelope import procedure_entry
from DeviceServers.control.elyse_acq.vi_simulation.procedure_sequences import (
    PROCEDURES,
    plan_procedure,
    project_frame,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    StopMemory,
    project_stop_reset,
)
from DeviceServers.control.elyse_acq.vi_simulation.timeout_dispatch import (
    TARGETS,
    procedure_dispatch,
)


def request(*fields):
    return tuple(index in fields for index in range(29))


def general_stop_snapshots():
    return {
        15: tuple(bool(i % 2) for i in range(32)),
        36: request(3),
        44: (True,) * 77,
    }


class StopRequestPipelineTests(unittest.TestCase):
    def test_all23_registered_requests_require_a_separately_supplied_event(self):
        events = []
        for field, (ddo, event) in enumerate(TARGETS):
            dispatched = procedure_dispatch(request(field))
            self.assertEqual(dispatched.property_intent.target_ddo, ddo)
            self.assertEqual(
                dispatched.property_intent.assignments,
                (("Value", True), ("Val(Sgnl)", True)),
            )
            self.assertEqual(dispatched.property_intent.registered_event, event)
            if event is None:
                continue
            events.append(event)
            self.assertTrue(procedure_entry(event, new_value=True).enters_sequence)
            self.assertEqual(plan_procedure(event, True), PROCEDURES[event])
            self.assertFalse(procedure_entry(event, new_value=False).enters_sequence)
            self.assertEqual(plan_procedure(event, False), ())
        self.assertEqual(sorted(events), list(range(3, 26)))

    def test_dps3_general_stop_keeps_all17_frames_and_focal_off_description(self):
        snapshots = general_stop_snapshots()
        dispatched = procedure_dispatch(snapshots[36])
        self.assertEqual(dispatched.first_true_index, 3)
        self.assertEqual(dispatched.case_selector, 4)
        self.assertEqual(dispatched.property_intent.registered_event, 6)
        phases = plan_procedure(6, True)  # Explicitly supplied event delivery.
        self.assertEqual(len(phases), 17)
        pulses = []
        publications = []
        all_writes = []
        for uid, _ in phases:
            projected = project_frame(uid, snapshots)
            if uid == "26598":
                self.assertEqual(
                    [cell[0] for cell in projected.subsequence_requests[0]],
                    ["53835", "53932"],
                )
                self.assertEqual(
                    project_frame("53835", {}).call_requests,
                    (("call_clear_error", "1_Focales OFF.vi"),),
                )
                self.assertEqual(project_frame("53932", {}).wait_requests_ms, (500,))
            for bank, values in projected.local_writes:
                all_writes.append(bank)
                if bank == 15:
                    changed = [
                        (index, value)
                        for index, value in enumerate(values)
                        if value is not snapshots[bank][index]
                    ]
                    # Some requested writes equal the supplied old value;
                    # use the independently stored plan to keep those requests.
                    effects = dict(phases)[uid]
                    requested = next(e[2] for e in effects if e[:2] == ("write", 15))
                    self.assertTrue(set(changed) <= set(requested))
                    pulses.extend(requested)
                snapshots[bank] = values
            publications.extend(projected.publication_payloads)
        self.assertEqual(
            pulses,
            [(field, value) for field in (8, 17, 6, 4, 1) for value in (False, True)],
        )
        self.assertFalse(snapshots[36][3])
        self.assertTrue(all(snapshots[15][field] for field in (8, 17, 6, 4, 1)))
        self.assertTrue(all(not snapshots[44][i] for i in (8, 9, 14, 20, 26, 32)))
        self.assertTrue(all(snapshots[44][i] for i in (11, 17, 23, 29, 35)))
        self.assertEqual(publications, [(("DPS", 36, snapshots[36]),)])
        self.assertFalse(set(all_writes) & {30, 45, 46, 47})

    def test_lower_dps_field_precedes_general_stop_but_does_not_clear_it(self):
        simultaneous = request(0, 3)
        first = procedure_dispatch(simultaneous)
        self.assertEqual(first.property_intent.registered_event, 3)
        self.assertNotEqual(first.property_intent.registered_event, 6)
        completion = project_frame("24540", {36: simultaneous, 44: (False,) * 77})
        dps_after = dict(completion.local_writes)[36]
        self.assertFalse(dps_after[0])
        self.assertTrue(dps_after[3])
        self.assertEqual(
            procedure_dispatch(dps_after).property_intent.registered_event, 6
        )
        # Re-supplying the old remote snapshot selects cooling start again.
        self.assertEqual(
            procedure_dispatch(simultaneous).property_intent.registered_event, 3
        )

    def test_publication_is_a_fresh_snapshot_not_guaranteed_reset_acknowledgment(self):
        old = general_stop_snapshots()
        completion = project_frame("28661", old)
        reset_dps = dict(completion.local_writes)[36]
        self.assertFalse(reset_dps[3])
        published = project_frame("35146", {36: old[36]})
        self.assertTrue(published.publication_payloads[0][0][2][3])
        self.assertEqual(published.wait_requests_ms, (100,))
        self.assertEqual(published.local_writes, ())

    def test_procedure_completion_is_not_program_stop_or_final_cleanup(self):
        normal_writers = {
            effect[1]
            for _, effects in PROCEDURES[6]
            for effect in effects
            if effect[0] == "write"
        }
        self.assertEqual(normal_writers, {15, 35, 36, 44})
        supplied = StopMemory(True, True, False, True)
        controlled = project_stop_reset("controlled_complete", supplied)
        self.assertEqual(controlled.independent_assignments, ((46, True), (47, False)))
        self.assertTrue(controlled.after.stop)
        self.assertTrue(controlled.after.tcp_ed)
        cleanup = project_stop_reset("final_cleanup", controlled.after)
        self.assertEqual(cleanup.independent_assignments, ((30, False),))
        self.assertFalse(cleanup.after.stop)
        self.assertTrue(cleanup.after.tcp_ed)
        self.assertTrue(cleanup.after.emergency_stop)

    def test_unregistered_target_and_saved_default_tail_do_not_invent_event_delivery(self):
        self.assertIsNone(
            procedure_dispatch(request(22)).property_intent.registered_event
        )
        with self.assertRaises(ValueError):
            procedure_entry(None, new_value=True)
        for field in range(24, 29):
            result = procedure_dispatch(request(field))
            self.assertIs(result.property_intent, UNWIRED)
            self.assertIs(result.action_assignment, False)
            self.assertEqual(result.case_selector, field + 1)

    def test_composition_remains_inert(self):
        with (
            patch(
                "socket.socket.connect", side_effect=AssertionError("network forbidden")
            ),
            patch("time.sleep", side_effect=AssertionError("sleep forbidden")),
        ):
            self.test_dps3_general_stop_keeps_all17_frames_and_focal_off_description()


if __name__ == "__main__":
    unittest.main()
