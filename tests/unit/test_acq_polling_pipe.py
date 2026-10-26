"""Private pipe regression: no idle read locks, no NI/XP/device operations."""
import os
import sys
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.isolated_wire import (
    PollingPipeReader, windows_polling_pipe, read_frame, encode_frame,
)


class PollingPipeTests(unittest.TestCase):
    def test_waits_without_reading_empty_pipe_then_reads_only_available_bytes(self):
        counts, reads, waits = iter((0, 0, 2)), [], []
        def read(count):
            reads.append(count)
            return b"ab"
        reader = PollingPipeReader(lambda: next(counts), read, wait=waits.append)
        self.assertEqual(reader.read(10), b"ab")
        self.assertEqual(reads, [2])
        self.assertEqual(waits, [.02, .02])

    def test_fragmented_frame_preserves_protocol_and_bounds_every_native_read(self):
        frame = bytearray(encode_frame(dict(kind="cancel", id=9)))
        calls = []
        def available():
            return min(3, len(frame))
        def read(count):
            calls.append(count)
            data = bytes(frame[:count])
            del frame[:count]
            return data
        reader = PollingPipeReader(available, read)
        self.assertEqual(read_frame(reader), dict(kind="cancel", id=9))
        self.assertTrue(all(0 < count <= 3 for count in calls))

    def test_broken_pipe_is_eof_and_does_not_read(self):
        def broken():
            error = OSError("fixture disconnected")
            error.winerror = 109
            raise error
        def no_read(count):
            self.fail("No read after broken pipe")
        with self.assertRaises(EOFError):
            read_frame(PollingPipeReader(broken, no_read))

    def test_cancellation_of_reader_does_not_call_native_read(self):
        stopped = threading.Event()
        stopped.set()
        def forbidden(*args):
            self.fail("No calls after stop")
        self.assertEqual(PollingPipeReader(forbidden, forbidden, stopped).read(1), b"")

    @unittest.skipUnless(sys.platform == "win32", "Native Windows pipe contract")
    def test_actual_windows_pipe_handles_partial_header_and_eof(self):
        read_fd, write_fd = os.pipe()
        source = os.fdopen(read_fd, "rb", buffering=0)
        try:
            frame = encode_frame(dict(kind="cancel", id=7))
            os.write(write_fd, frame[:2])
            def writer():
                threading.Event().wait(.05)
                os.write(write_fd, frame[2:])
                os.close(write_fd)
            thread = threading.Thread(target=writer)
            thread.start()
            reader = windows_polling_pipe(source)
            self.assertEqual(read_frame(reader), dict(kind="cancel", id=7))
            with self.assertRaises(EOFError):
                read_frame(reader)
            thread.join(2)
            self.assertFalse(thread.is_alive())
        finally:
            source.close()
