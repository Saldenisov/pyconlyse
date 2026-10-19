"""All five outer states, supplied faults and mutable-local snapshots."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import NO_ERROR, ErrorCluster
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_startup import (
    TpgStartupState as State,
)
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_startup import (
    transition,
)

FAULT = ErrorCluster(True, -91, "fixture")


def step(state, **overrides):
    args = dict(
        requested_selector=4,
        current_selector=4,
        default_selector_snapshot=4,
        max_selector_snapshot=4,
        serial_return=NO_ERROR,
        command_return=NO_ERROR,
    )
    args.update(overrides)
    return transition(state, **args)


class TpgTransitionTests(unittest.TestCase):
    def test_serial_error_skips_probe_then_errorbox_replaces_original_fault(self):
        result = step(State.INIT_TEST, serial_return=FAULT)
        self.assertEqual(result.next_state, State.ERROR_BOX)
        self.assertEqual(result.requested_operations, (("SerialInit", 4),))
        self.assertEqual(result.returned_error, FAULT)
        final = step(result.next_state)
        self.assertFalse(final.keep_running)
        self.assertEqual(final.returned_error, ErrorCluster(True, 0, "Init Error"))

    def test_probe_fault_moves_to_next_rate_and_wraps_4_to_0(self):
        self.assertEqual(
            step(State.INIT_TEST, command_return=FAULT).next_state, State.NEXT_BAUD
        )
        result = step(State.NEXT_BAUD)
        self.assertEqual(
            (result.current_selector, result.next_state), (0, State.INIT_TEST)
        )
        self.assertIsNone(result.returned_error)

    def test_cyclic_search_stops_when_incremented_selector_matches_snapshot(self):
        for current in range(5):
            result = step(State.NEXT_BAUD, current_selector=current)
            expected = State.ERROR_BOX if current == 3 else State.INIT_TEST
            self.assertEqual(result.next_state, expected)
        # A stale Def.Value=1 changes search termination; no scheduler is inferred.
        self.assertEqual(
            step(
                State.NEXT_BAUD, current_selector=0, default_selector_snapshot=1
            ).next_state,
            State.ERROR_BOX,
        )

    def test_success_same_rate_skips_bau_different_rate_selects_bau(self):
        for current in range(5):
            result = step(State.INIT_TEST, current_selector=current)
            self.assertEqual(
                result.next_state,
                State.COMMUNICATION_OK if current == 4 else State.SET_DEFAULT,
            )
            self.assertEqual(result.requested_operations[-1], ("PNR timeout_ms", 700))

    def test_all_five_bau_codes_and_fault_not_gating_next_state(self):
        for selector, code in enumerate(("3", "1", "2", "4", "9")):
            result = step(
                State.SET_DEFAULT,
                default_selector_snapshot=selector,
                command_return=FAULT,
            )
            self.assertEqual(
                result.requested_operations, (("BAU command", "BAU," + code),)
            )
            self.assertEqual(result.next_state, State.COMMUNICATION_OK)
            self.assertEqual(result.returned_error, FAULT)

    def test_final_probe_exits_even_on_serial_or_probe_error(self):
        result = step(
            State.COMMUNICATION_OK,
            current_selector=2,
            serial_return=FAULT,
            command_return=FAULT,
        )
        self.assertFalse(result.keep_running)
        self.assertEqual(result.current_selector, 4)
        self.assertEqual(result.returned_error, FAULT)
        self.assertEqual(
            result.requested_operations, (("SerialInit", 4), ("PNR timeout_ms", 700))
        )

    def test_projection_requires_explicit_returns_and_rejects_unproved_selectors(self):
        with self.assertRaises(TypeError):
            step(State.INIT_TEST, serial_return=None)
        with self.assertRaises(TypeError):
            step(State.COMMUNICATION_OK, command_return=None)
        with self.assertRaises(ValueError):
            step(State.NEXT_BAUD, max_selector_snapshot=6)
        with self.assertRaises(ValueError):
            step(State.INIT_TEST, current_selector=5)


if __name__ == "__main__":
    unittest.main()
