"""Business-level HT request/stop traces; only explicit entered-frame fixtures.

No success, permission, physical voltage or implicit cross-loop sampling is
inferred. These compose independently source-checked VI projections.
"""

import math
import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    ErrorCluster,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import (
    project_ht_ramp_iteration,
    project_outer_tcp_decision,
    project_stop_operator_iteration,
)
from DeviceServers.control.elyse_acq.vi_simulation.procedure_sequences import (
    plan_procedure,
)
from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import record_runtime_io
from DeviceServers.control.elyse_acq.vi_simulation.rw_dio96 import DigitalOutputBanks
from DeviceServers.control.elyse_acq.vi_simulation.startup_publication import (
    STARTUP_COMMANDS,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    NextIteration,
    replay_runtime,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_schedule import (
    RUNTIME_LOOPS,
    BodyCompleted,
    ErrorArmEntry,
    LocalAssignment,
    OuterTcpRead,
    StopLocalRead,
)
from DeviceServers.control.elyse_acq.vi_simulation.timeout_cooling import (
    cooling_guard,
    trip_frame,
)
from DeviceServers.control.elyse_acq.vi_simulation.timeout_reads import (
    SITES,
    PspReturn,
    read_frame,
)
from DeviceServers.control.elyse_acq.vi_simulation.write_ni6703 import LogicalAoBanks


def c9_with_ht(value):
    initial = dict(STARTUP_COMMANDS)[12]
    return (value,) + initial[1:]


def receive(c9, *, eps=None, c9_error=NO_ERROR, final_error=NO_ERROR):
    """One returning Timeout frame; boundary values are supplied, not fetched."""
    startup = dict(STARTUP_COMMANDS)
    prior, returned = {}, {}
    for uid, _, bank, size, kind in SITES:
        prior[uid] = startup.get(bank, (False if kind is bool else 0.0,) * size)
        data = c9 if bank == 12 else prior[uid]
        if bank == 44 and eps is not None:
            data = eps
        error = c9_error if bank == 12 else final_error if uid == "22840" else NO_ERROR
        returned[uid] = PspReturn(data, error)
    return read_frame(
        default_snapshots=prior,
        returned_snapshots=returned,
        stop_before=True,
        tcp_ed_before=True,
    )


def sample_io(c9, *, boundary=None):
    """Explicit entered I/O frame and chosen AO local-read snapshots."""
    banks = dict(STARTUP_COMMANDS)
    banks[12] = c9
    return record_runtime_io(
        boundary if boundary is not None else ScriptedBoundary(),
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


class HtCommandBusinessTraceTests(unittest.TestCase):
    def test_startup_retains_nonzero_ht_command_not_output_zeroing(self):
        c9 = dict(STARTUP_COMMANDS)[12]
        result = sample_io(c9)
        self.assertEqual(c9[0], 6.5)
        self.assertEqual(result.output.requested_voltages[3][0], 3.25)
        self.assertEqual(result.output.calls[3].key.node_uid, "1200")
        self.assertEqual(result.output.calls[3].args["data"][0], 3.25)

    def test_explicit_receive_then_sample_maps_12_7_to_6_35_request(self):
        incoming = c9_with_ht(12.7)
        frame = receive(incoming)
        sampled = dict(frame.data_assignments)[12]
        self.assertEqual(sampled, incoming)
        result = sample_io(sampled)
        self.assertEqual(result.output.requested_voltages[3][0], 6.35)
        self.assertEqual(result.output.calls[3].task_in.token, "C9AO")

    def test_independent_io_read_can_still_sample_prior_command(self):
        frame = receive(c9_with_ht(12.7))
        prior_result = sample_io(dict(STARTUP_COMMANDS)[12])
        later_result = sample_io(dict(frame.data_assignments)[12])
        self.assertEqual(prior_result.output.requested_voltages[3][0], 3.25)
        self.assertEqual(later_result.output.requested_voltages[3][0], 6.35)
        # This is two supplied read schedules, not a guaranteed update deadline.

    def test_c9_read_error_does_not_gate_its_supplied_data_assignment(self):
        fault = ErrorCluster(True, -100, "supplied C9 reader error")
        frame = receive(c9_with_ht(12.7), c9_error=fault)
        self.assertEqual(frame.calls[4].error_in, fault)
        self.assertEqual(frame.fault_assignments, ())  # Later supplied clear.
        self.assertEqual(
            sample_io(dict(frame.data_assignments)[12]).output.requested_voltages[3][0],
            6.35,
        )

    def test_final_read_fault_clears_stop_flags_without_clearing_ht_command(self):
        frame = receive(c9_with_ht(12.7), final_error=ErrorCluster(True, -101))
        self.assertEqual(frame.fault_assignments, ((30, False), (45, False)))
        self.assertEqual(dict(frame.data_assignments)[12][0], 12.7)

    def test_eps_status_changes_are_not_a_gate_on_the_traced_command_copy(self):
        for state in (False, True):
            with self.subTest(all_eps=state):
                frame = receive(c9_with_ht(12.7), eps=(state,) * 77)
                sampled = sample_io(dict(frame.data_assignments)[12])
                self.assertEqual(sampled.output.requested_voltages[3][0], 6.35)

    def test_conditionally_entered_cooling_trip_does_not_reset_c9(self):
        c4 = (False,) * 19 + (True,) + (False,) * 44
        self.assertTrue(
            cooling_guard(enabled_arm=True, c4_snapshot=c4, c3_snapshot=(False,) * 56)
        )
        state = dict(STARTUP_COMMANDS)
        state.update({12: c9_with_ht(12.7), 44: (True,) * 77, 36: (True,) * 29})
        local_reads = {
            0: {"10431": 17},
            1: {"13466": 17},
            2: {},
            3: {"22661": 17},
            4: {"30986": 17},
            5: {"39289": 44, "39313": 36},
            6: {"39444": 36},
        }
        for index in range(7):
            effects = trip_frame(
                index,
                snapshots={
                    uid: state[bank] for uid, bank in local_reads[index].items()
                },
            )
            self.assertNotIn(12, {w.bank for w in effects.writes})
            state.update({w.bank: w.data for w in effects.writes})
        self.assertFalse(state[44][2])
        self.assertTrue(state[44][45])
        self.assertEqual(sample_io(state[12]).output.requested_voltages[3][0], 6.35)

    def test_supply_start_stop_reset_and_normal_modulator_stop_do_not_zero_c9(self):
        def writes(phases):
            for _, effects in phases:
                for effect in effects:
                    if effect[0] == "write":
                        yield effect[1]
                    elif effect[0] == "subsequence":
                        yield from writes(effect[1])

        for event in (6, 20, 21, 22):
            with self.subTest(event=event):
                self.assertNotIn(12, set(writes(plan_procedure(event, True))))
                self.assertEqual(plan_procedure(event, False), ())

    def test_returned_card_fault_does_not_invent_a_zero_request(self):
        result = sample_io(c9_with_ht(12.7))
        boundary = ScriptedBoundary(
            errors={result.output.calls[3].key: ErrorCluster(True, -102)}
        )
        faulted = sample_io(c9_with_ht(12.7), boundary=boundary)
        self.assertTrue(faulted.output.error_out.status)
        self.assertEqual(faulted.output.calls[3].args["data"][0], 6.35)
        # Visiting the call site is not evidence that a physical write occurred.

    def test_outer_ramp_requires_runtime_join_and_cannot_resume_receiver(self):
        partial = (StopLocalRead("102"), BodyCompleted("102"), OuterTcpRead())
        with self.assertRaisesRegex(ValueError, "all five runtime loops"):
            replay_runtime(partial, stop_before=True, tcp_before=True)
        closed = tuple(
            token
            for loop in RUNTIME_LOOPS
            for token in (StopLocalRead(loop), BodyCompleted(loop))
        ) + (OuterTcpRead(),)
        trace = replay_runtime(closed, stop_before=True, tcp_before=True)
        self.assertTrue(trace.outer_tcp_snapshot)
        self.assertEqual(trace.exited_loops, RUNTIME_LOOPS)
        with self.assertRaisesRegex(ValueError, "ends at the outer TCP read"):
            replay_runtime(
                closed + (NextIteration("102"),), stop_before=True, tcp_before=True
            )

    def test_returning_closed_phase_ramp_reaches_threshold_not_zero(self):
        c9 = c9_with_ht(12.7)
        decrements, exit_writes = [], None
        for _ in range(100):  # Test bound only; no such limit exists in the VI.
            result = project_ht_ramp_iteration(c9, c9)
            if result.should_stop:
                exit_writes = dict(result.local_writes)
                break
            c9 = dict(result.local_writes)[12]
            decrements.append(c9[0])
        self.assertIsNotNone(exit_writes)
        self.assertEqual(len(decrements), 62)
        self.assertTrue(math.isclose(c9[0], 6.5, abs_tol=1e-12))
        self.assertNotIn(12, exit_writes)
        self.assertEqual(sample_io(c9).output.requested_voltages[3][0], c9[0] * 0.5)
        self.assertEqual(c9[1:], dict(STARTUP_COMMANDS)[12][1:])

    def test_outer_stop_entry_and_operator_request_are_distinct_gates(self):
        self.assertEqual(project_outer_tcp_decision(False), ())
        self.assertEqual(project_outer_tcp_decision(True), ("41705", "42592"))
        for general in (False, True):
            for emergency in (False, True):
                with self.subTest(general=general, emergency=emergency):
                    result = project_stop_operator_iteration(general, emergency)
                    self.assertEqual(bool(result.sequence_requests), general)
                    self.assertEqual(result.sampled_should_stop, emergency)
        # True emergency condition does not cancel an already entered sequence.

    def test_returning_publication_fault_does_not_itself_request_the_ht_ramp(self):
        schedule = (
            (
                ErrorArmEntry("40346"),
                LocalAssignment("50011"),
                LocalAssignment("50019"),
            )
            + tuple(
                token
                for loop in RUNTIME_LOOPS
                for token in (StopLocalRead(loop), BodyCompleted(loop))
            )
            + (OuterTcpRead(),)
        )
        trace = replay_runtime(schedule, stop_before=False, tcp_before=False)
        self.assertTrue(trace.outer_tcp_snapshot)
        self.assertEqual(
            project_outer_tcp_decision(trace.outer_tcp_snapshot), ("41705", "42592")
        )
        operator = project_stop_operator_iteration(False, False)
        self.assertEqual(operator.sequence_requests, ())
        # Explicitly False general-stop snapshot; no hidden request is invented.


if __name__ == "__main__":
    unittest.main()
