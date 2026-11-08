"""Golden byte snapshots, no timers, serial ports or device adapters."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    ErrorCluster,
)
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_protocol import (
    ByteLoopState,
    byte_loop_step,
    framed_command,
    phase_one_error_bypass,
    response_phase_enabled,
)


class ProtocolProjectionTests(unittest.TestCase):
    def step(self, **overrides):
        values = dict(
            phase="ack",
            state=ByteLoopState(),
            bytes_available=0,
            read_bytes=None,
            elapsed_ms=0,
            timeout_ms=600,
            returned_error=NO_ERROR,
        )
        values.update(overrides)
        return byte_loop_step(**values)

    def test_command_mode_and_short_empty_byte_strings(self):
        self.assertEqual(framed_command(b"BAU,9", write_read=True), b"BAU,9\r")
        self.assertEqual(framed_command(b"BAU,9", write_read=False), b"BAU\r")
        for command in (b"", b"P", b"PN"):
            self.assertEqual(framed_command(command, write_read=False), command + b"\r")

    def test_no_data_timeout_and_poll_wait_in_both_phases(self):
        for phase in ("ack", "response"):
            for elapsed, keep, wait in (
                (599, True, 50),
                (600, False, 0),
                (601, False, 0),
            ):
                result = self.step(phase=phase, elapsed_ms=elapsed)
                self.assertEqual(
                    (
                        result.keep_running,
                        result.flag_a,
                        result.flag_b,
                        result.requested_wait_ms,
                    ),
                    (keep, not keep, True, wait),
                )

    def test_ack_prefix_discarded_and_only_after_ack_preserved(self):
        result = self.step(bytes_available=8, read_bytes=b"echo\x06abc")
        self.assertEqual(result.state, ByteLoopState(b"abc", 5))
        self.assertTrue(result.keep_running)
        self.assertFalse(result.flag_a or result.flag_b)

    def test_ack_without_cr_and_next_chunk_cr(self):
        first = self.step(bytes_available=1, read_bytes=b"\x06")
        self.assertEqual(first.state, ByteLoopState(b"", 1))
        second = self.step(state=first.state, bytes_available=5, read_bytes=b"ok\rxx")
        self.assertEqual(second.state, ByteLoopState(b"ok", 1))
        self.assertFalse(second.keep_running or second.flag_a or second.flag_b)

    def test_no_ack_discards_chunk_even_if_it_contains_cr(self):
        result = self.step(bytes_available=6, read_bytes=b"noise\r", elapsed_ms=900)
        self.assertEqual(result.state, ByteLoopState())
        self.assertTrue(result.keep_running)
        self.assertFalse(result.flag_a or result.flag_b)

    def test_nak_ends_first_recognition_branch(self):
        for chunk in (b"\x15", b"\x06data\x15", b"\x15\x06\r"):
            result = self.step(bytes_available=len(chunk), read_bytes=chunk)
            self.assertFalse(result.keep_running)
            self.assertTrue(result.flag_a and result.flag_b)

    def test_nak_after_ack_is_payload_not_new_recognition(self):
        result = self.step(
            state=ByteLoopState(b"x", 1), bytes_available=2, read_bytes=b"\x15\r"
        )
        self.assertEqual(result.state.buffer, b"x\x15")
        self.assertFalse(result.keep_running or result.flag_a or result.flag_b)

    def test_response_subcases_both_append_and_use_constant_offset_one(self):
        for offset in (-1, 1, 4):
            result = self.step(
                phase="response",
                state=ByteLoopState(b"12", offset),
                bytes_available=5,
                read_bytes=b".3\rLF",
            )
            self.assertEqual(result.state, ByteLoopState(b"12.3", 1))
            self.assertFalse(result.keep_running or result.flag_a or result.flag_b)

    def test_nonempty_read_branches_can_continue_after_nominal_deadline(self):
        for phase, state, chunk in (
            ("ack", ByteLoopState(), b"\x06x"),
            ("ack", ByteLoopState(b"", 1), b"x"),
            ("response", ByteLoopState(), b"x"),
        ):
            result = self.step(
                phase=phase,
                state=state,
                bytes_available=len(chunk),
                read_bytes=chunk,
                elapsed_ms=10000,
            )
            self.assertTrue(result.keep_running)
            self.assertEqual(result.requested_wait_ms, 0)

    def test_returned_error_is_not_implicitly_a_continue_guard(self):
        fault = ErrorCluster(True, -1, "supplied failed read")
        result = self.step(
            phase="response", bytes_available=2, read_bytes=b"", returned_error=fault
        )
        self.assertTrue(result.keep_running)
        self.assertEqual(result.returned_error, fault)

    def test_error_wrapper_and_phase_two_truth_table(self):
        fault = ErrorCluster(True, -9, "property")
        result = phase_one_error_bypass(fault)
        self.assertEqual(
            (result.flag_a, result.flag_b, result.returned_error), (True, False, fault)
        )
        for a in (False, True):
            for b in (False, True):
                self.assertEqual(
                    response_phase_enabled(flag_a=a, flag_b=b), not (a or b)
                )

    def test_recognized_but_no_bytes_after_timeout_has_distinct_flags(self):
        for phase in ("ack", "response"):
            result = self.step(
                phase=phase, state=ByteLoopState(b"partial", 1), elapsed_ms=600
            )
            self.assertEqual((result.flag_a, result.flag_b), (True, False))

    def test_python_only_snapshot_validation(self):
        with self.assertRaises(ValueError):
            self.step(elapsed_ms=-1)
        with self.assertRaises(ValueError):
            self.step(read_bytes=b"")
        with self.assertRaises(TypeError):
            self.step(bytes_available=1)
        with self.assertRaises(TypeError):
            framed_command("PNR", write_read=False)
        with self.assertRaises(ValueError):
            phase_one_error_bypass(NO_ERROR)


if __name__ == "__main__":
    unittest.main()
