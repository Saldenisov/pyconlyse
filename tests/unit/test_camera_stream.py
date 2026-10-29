"""Independent camera transport: CPython3.4, fixtures/loopback only, no NI."""
import copy
import hashlib
import hmac
import io
import socket
import struct
import threading
import time
import unittest
import zlib
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.camera_stream import (
    CameraFrameQueue, CameraFrameSender, CameraFrameReceiver, MAX_RAW,
    encode_frame, receive_frame, MAGIC)
from legacy.xp_acq_control.elyse_agent.telemetry_relay import DeadlineSocket, sign
from legacy.xp_acq_control.elyse_agent.protocol import send_message

KEY = b'camera-stream-test-only-key-00000000000000'


def metadata(sequence=1, width=2, height=2):
    return dict(capture_session_id='a' * 32, sequence=sequence,
                observed_utc='2026-10-29T08:00:00.000001+00:00', width=width,
                height=height, channel=2, source_age_seconds=.001)


class BytesSocket(object):
    def __init__(self, value):
        self.stream = io.BytesIO(value)

    def recv(self, count):
        return self.stream.read(count)


class CameraStreamTests(unittest.TestCase):
    def test_lossless_full_geometry_compressed_binary_roundtrip(self):
        pixels = bytes(bytearray((i * 17) % 256 for i in range(768 * 576)))
        raw = encode_frame(metadata(width=768, height=576), pixels, 'b' * 32, 1, 'c' * 32, KEY)
        header, result = receive_frame(BytesSocket(raw), KEY)
        self.assertEqual(result, pixels)
        self.assertEqual(header['frame']['width'], 768)
        self.assertLess(len(raw), len(pixels))

    def test_authentication_and_bounds_precede_decompression(self):
        raw = encode_frame(metadata(), b'abcd', 'b' * 32, 1, 'c' * 32, KEY)
        corrupt = bytearray(raw)
        corrupt[-1] ^= 1
        with patch('legacy.xp_acq_control.elyse_agent.camera_stream.zlib.decompressobj') as unpack:
            with self.assertRaisesRegex(ValueError, 'authentication'):
                receive_frame(BytesSocket(bytes(corrupt)), KEY)
            with self.assertRaisesRegex(ValueError, 'bounded'):
                receive_frame(BytesSocket(MAGIC + struct.pack('!II', 5000, 1)), KEY)
            self.assertEqual(unpack.call_count, 0)

    def test_authenticated_compression_cannot_expand_past_raw_limit(self):
        raw = encode_frame(metadata(), b'abcd', 'b' * 32, 1, 'c' * 32, KEY)
        header_size, unused = struct.unpack('!II', raw[len(MAGIC):len(MAGIC) + 8])
        header = raw[len(MAGIC) + 8:len(MAGIC) + 8 + header_size]
        payload = zlib.compress(b'x' * (MAX_RAW + 1), 1)
        value = MAGIC + struct.pack('!II', len(header), len(payload)) + header + payload
        signed = value + hmac.new(KEY, value, hashlib.sha256).digest()
        with self.assertRaisesRegex(ValueError, 'compression'):
            receive_frame(BytesSocket(signed), KEY)

    def test_geometry_mutability_and_invalid_observation_rejected(self):
        q = CameraFrameQueue()
        for changed, pixels in ((dict(metadata(), width=True), b'abcd'),
                                (metadata(), bytearray(b'abcd')),
                                (dict(metadata(), observed_utc='bad+00:00'), b'abcd'),
                                (dict(metadata(), source_age_seconds=float('inf')), b'abcd'),
                                (dict(metadata(), width=MAX_RAW, height=2), b'abcd')):
            with self.assertRaises(ValueError):
                q.enqueue(changed, pixels)

    def test_fifo_never_replaces_frames_reports_capacity_and_retains_age(self):
        clock = [2.]
        q = CameraFrameQueue(capacity=2, max_bytes=8, clock=lambda: clock[0])
        m = metadata()
        self.assertTrue(q.enqueue(m, b'abcd'))
        m['channel'] = 7
        self.assertTrue(q.enqueue(metadata(2), b'efgh'))
        self.assertFalse(q.enqueue(metadata(3), b'ijkl'))
        clock[0] = 4.
        self.assertEqual(q.peek()[1]['channel'], 2)
        self.assertEqual(q.peek()[1]['source_age_seconds'], 2.001)
        with self.assertRaises(ValueError):
            q.acknowledge(2)
        q.acknowledge(1)
        self.assertEqual(q.peek()[2], b'efgh')
        self.assertTrue(q.enqueue(metadata(4), b'ijkl'))
        self.assertEqual(q.status()['rejected_new'], 1)

    def test_byte_limit_applies_independently_of_frame_count(self):
        q = CameraFrameQueue(capacity=20, max_bytes=4)
        self.assertTrue(q.enqueue(metadata(), b'abcd'))
        self.assertFalse(q.enqueue(metadata(2), b'abcd'))
        self.assertEqual(q.status()['pending'], 1)

    def _listener(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(2)
        listener.settimeout(3)
        self.addCleanup(listener.close)
        return listener

    def test_persistent_channel_delivers_every_frame_in_order(self):
        listener = self._listener()
        seen, failures = [], []
        receiver = CameraFrameReceiver(KEY, lambda meta, pixels: seen.append((meta['sequence'], pixels)))
        q = CameraFrameQueue(capacity=100)
        for seq in range(1, 101):
            self.assertTrue(q.enqueue(metadata(seq), bytes(bytearray([seq % 256] * 4))))
        def receive():
            try:
                with listener.accept()[0] as connection:
                    for unused in range(100):
                        receiver.receive_once(DeadlineSocket(connection, time.monotonic() + 3))
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=receive)
        worker.start()
        sender = CameraFrameSender(q, listener.getsockname(), KEY)
        try:
            for unused in range(100):
                self.assertTrue(sender.send_once())
            self.assertFalse(sender.send_once())
        finally:
            sender.disconnect()
            worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual([row[0] for row in seen], list(range(1, 101)))
        self.assertEqual(q.status()['acknowledged'], 100)

    def test_lost_ack_retries_head_without_duplicate_consume(self):
        listener = self._listener()
        seen, failures = [], []
        receiver = CameraFrameReceiver(KEY, lambda meta, pixels: seen.append(pixels))
        q = CameraFrameQueue()
        q.enqueue(metadata(), b'abcd')
        class LostAckSocket(object):
            def __init__(self, connection):
                self.connection = connection
            def recv(self, count):
                return self.connection.recv(count)
            def sendall(self, value):
                pass  # Simulated accepted frame whose ACK vanished.
        def receive():
            try:
                with listener.accept()[0] as connection:
                    receiver.receive_once(LostAckSocket(connection))
                with listener.accept()[0] as connection:
                    receiver.receive_once(connection)
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=receive)
        worker.start()
        sender = CameraFrameSender(q, listener.getsockname(), KEY)
        try:
            with self.assertRaises(EOFError):
                sender.send_once()
            self.assertEqual(q.status()['pending'], 1)
            self.assertTrue(sender.send_once())
        finally:
            sender.disconnect()
            worker.join(4)
        self.assertEqual(failures, [])
        self.assertEqual(seen, [b'abcd'])
        self.assertEqual(receiver.duplicates, 1)

    def test_authenticated_wrong_nonce_and_boolean_id_cannot_dequeue_head(self):
        for field, value in (('nonce', '0' * 32), ('message_id', True)):
            listener = self._listener()
            q = CameraFrameQueue()
            q.enqueue(metadata(), b'abcd')
            failures = []
            def receive():
                try:
                    with listener.accept()[0] as connection:
                        header, pixels = receive_frame(connection, KEY)
                        reply = dict(stream_id=header['stream_id'], message_id=header['message_id'],
                                     nonce=header['nonce'], accepted=True, receiver_id='d' * 32)
                        reply[field] = value
                        send_message(connection, dict(body=reply,
                            signature=sign(KEY, 'ELYSE-CAMERA-ACK-2', reply)))
                except Exception as error:
                    failures.append(error)
            worker = threading.Thread(target=receive)
            worker.start()
            sender = CameraFrameSender(q, listener.getsockname(), KEY)
            try:
                with self.assertRaisesRegex(ValueError, 'ACK'):
                    sender.send_once()
                self.assertEqual(q.status()['pending'], 1)
            finally:
                sender.disconnect()
                worker.join(4)
            self.assertEqual(failures, [])

    def test_receiver_restart_resumes_pending_head_and_reports_unknown_ack_history(self):
        listener = self._listener()
        seen, failures = [], []
        first = CameraFrameReceiver(KEY, lambda meta, raw: seen.append(meta['sequence']))
        second = CameraFrameReceiver(KEY, lambda meta, raw: seen.append(meta['sequence']))
        q = CameraFrameQueue()
        q.enqueue(metadata(1), b'abcd')
        q.enqueue(metadata(2), b'efgh')
        def receive():
            try:
                for receiver in (first, second):
                    with listener.accept()[0] as connection:
                        receiver.receive_once(connection)
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=receive)
        worker.start()
        sender = CameraFrameSender(q, listener.getsockname(), KEY)
        try:
            self.assertTrue(sender.send_once())
            sender.disconnect()
            self.assertTrue(sender.send_once())
            self.assertEqual(sender.receiver_changes, 1)
        finally:
            sender.disconnect()
            worker.join(4)
        self.assertEqual(failures, [])
        self.assertEqual(seen, [1, 2])
        self.assertEqual(second.unknown_prefix_streams, 1)
        self.assertEqual(q.status()['acknowledged'], 2)

    def test_blocked_receiver_does_not_hold_producer_lock(self):
        listener = self._listener()
        entered, release = threading.Event(), threading.Event()
        failures = []
        def slow(meta, pixels):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('fixture timeout')
        receiver = CameraFrameReceiver(KEY, slow)
        def receive():
            try:
                with listener.accept()[0] as connection:
                    receiver.receive_once(connection)
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=receive)
        worker.start()
        q = CameraFrameQueue(capacity=2)
        q.enqueue(metadata(), b'abcd')
        sender = CameraFrameSender(q, listener.getsockname(), KEY)
        sender.start()
        try:
            self.assertTrue(entered.wait(2))
            started = time.monotonic()
            self.assertTrue(q.enqueue(metadata(2), b'efgh'))
            self.assertFalse(q.enqueue(metadata(3), b'ijkl'))
            self.assertLess(time.monotonic() - started, .1)
        finally:
            release.set()
            sender.close()
            worker.join(4)
        self.assertEqual(failures, [])


if __name__ == '__main__':
    unittest.main()
