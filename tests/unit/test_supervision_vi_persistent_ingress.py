"""Persistent VI framing on private loopback ports; no NI, XP, DB or relay."""
import socket
import struct
import threading
import time
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.protocol import encode_message, recv_message
from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import (
    BINARY_CAMERA_PREFIX, MAX_VI_BYTES, SupervisionVIServer,
    decode_vi_camera_binary, decode_vi_observation,
)
from tests.unit.test_supervision_vi_telemetry import (
    NATIVE_NOW, native_camera, observation, part,
)


MODULE = "legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry"


class ObservationStore(object):
    def __init__(self):
        self.lock = threading.RLock()
        self.messages, self.rejected, self.last_error = [], 0, ""

    def ingest_observation(self, raw, peer):
        if raw.startswith(BINARY_CAMERA_PREFIX):
            value = decode_vi_camera_binary(raw, NATIVE_NOW, 100125)
        else:
            value = decode_vi_observation(raw)
        with self.lock:
            self.messages.append(raw)
        return dict(source_sequence=value["sequence"])


class TracedServer(SupervisionVIServer):
    def __init__(self, *args):
        self.accepted_connections, self.handler_threads = 0, []
        SupervisionVIServer.__init__(self, *args)

    def get_request(self):
        result = SupervisionVIServer.get_request(self)
        self.accepted_connections += 1
        return result

    def process_request_thread(self, request, address):
        self.handler_threads.append(threading.current_thread())
        return SupervisionVIServer.process_request_thread(self, request, address)


class PersistentSupervisionIngressTests(unittest.TestCase):
    def setUp(self):
        self.store = ObservationStore()
        self.server = TracedServer(("127.0.0.1", 0), self.store)
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01))
        self.worker.daemon = True
        self.worker.start()
        self.clients = []

    def tearDown(self):
        for connection in self.clients:
            connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(2.)
        self.assertFalse(self.worker.is_alive())
        self.assertEqual(self.server._active_handlers, 0)
        self.assertTrue(all(not worker.is_alive() for worker in self.server.handler_threads))

    def connect(self):
        connection = socket.create_connection(self.server.server_address, timeout=2.)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.clients.append(connection)
        return connection

    def wait_until(self, predicate, timeout=2.):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail("Private ingress fixture did not settle")
            time.sleep(.005)

    def send_json(self, connection, sequence=1):
        connection.sendall(encode_message(observation(sequence, counter=part()), MAX_VI_BYTES))
        reply = recv_message(connection, 16384)
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["result"]["source_sequence"], sequence)
        return reply

    def assert_closed(self, connection):
        try:
            remaining = connection.recv(1)
        except socket.timeout:
            self.fail("Private ingress connection did not close within client deadline")
        except OSError:  # Windows can reset a rejected connection with unread bytes.
            remaining = b""
        self.assertEqual(remaining, b"")

    def test_mixed_native_and_json_frames_share_one_connection_and_ordered_acks(self):
        connection = self.connect()
        self.send_json(connection, 1)
        for count in (7, 8):
            raw = native_camera(frame_count=count)
            connection.sendall(struct.pack("!I", len(raw)) + raw)
            reply = recv_message(connection, 16384)
            self.assertTrue(reply["ok"])
            self.assertEqual(reply["result"]["source_sequence"], count + 1)
        self.send_json(connection, 2)
        self.assertEqual(len(self.store.messages), 4)
        self.assertEqual(self.server.accepted_connections, 1)
        self.assertEqual(self.store.rejected, 0)

    def test_fragmented_writes_and_coalesced_frames_preserve_message_boundaries(self):
        connection = self.connect()
        first = encode_message(observation(1, counter=part()), MAX_VI_BYTES)
        second = encode_message(observation(2, counter=part()), MAX_VI_BYTES)
        for fragment in (first[:1], first[1:3], first[3:13], first[13:] + second):
            connection.sendall(fragment)
        replies = [recv_message(connection, 16384) for unused in range(2)]
        self.assertEqual([reply["result"]["source_sequence"] for reply in replies], [1, 2])
        self.assertEqual(self.store.messages, [first[4:], second[4:]])
        self.assertEqual(self.store.rejected, 0)

    def test_old_one_frame_client_can_close_without_recording_a_lost_snapshot(self):
        connection = self.connect()
        self.send_json(connection)
        connection.close()
        self.wait_until(lambda: self.server._active_handlers == 0)
        self.assertEqual(self.store.rejected, 0)
        self.send_json(self.connect(), 2)
        self.assertEqual(self.server.accepted_connections, 2)

    def test_connection_lifetime_can_exceed_the_two_second_frame_deadline(self):
        connection = self.connect()
        for sequence in range(1, 5):
            if sequence > 1:
                time.sleep(.75)
            self.send_json(connection, sequence)
        self.assertEqual(self.server.accepted_connections, 1)
        self.assertEqual(self.store.rejected, 0)

    def test_idle_after_ack_closes_cleanly_and_releases_handler_slot(self):
        with patch(MODULE + ".VI_IDLE_TIMEOUT_SECONDS", .1):
            connection = self.connect()
            self.send_json(connection)
            self.assert_closed(connection)
            self.wait_until(lambda: self.server._active_handlers == 0)
        self.assertEqual(self.store.rejected, 0)
        self.assertEqual(len(self.store.messages), 1)

    def test_partial_frame_times_out_once_without_admitting_payload(self):
        with patch(MODULE + ".VI_FRAME_TIMEOUT_SECONDS", .1):
            connection = self.connect()
            connection.sendall(struct.pack("!I", 100) + b"{")
            self.assert_closed(connection)
            self.wait_until(lambda: self.server._active_handlers == 0)
        self.assertEqual(self.store.rejected, 1)
        self.assertEqual(self.store.messages, [])

    def test_trickling_bytes_cannot_extend_one_frames_absolute_deadline(self):
        connection = self.connect()
        connection.settimeout(.7)
        stop = threading.Event()
        def trickle():
            for unused in range(30):
                if stop.wait(.03):
                    return
                try:
                    connection.sendall(b" ")
                except OSError:
                    return
        sender = threading.Thread(target=trickle)
        with patch(MODULE + ".VI_FRAME_TIMEOUT_SECONDS", .12):
            connection.sendall(struct.pack("!I", 100) + b"{")
            sender.start()
            try:
                self.assert_closed(connection)
                self.wait_until(lambda: self.server._active_handlers == 0)
            finally:
                stop.set()
                sender.join(1.)
        self.assertFalse(sender.is_alive())
        self.assertEqual(self.store.rejected, 1)
        self.assertEqual(self.store.messages, [])

    def test_eof_in_submitted_payload_is_rejected_without_waiting_for_idle_timeout(self):
        connection = self.connect()
        connection.sendall(struct.pack("!I", 100) + b"{")
        connection.shutdown(socket.SHUT_WR)
        reply = recv_message(connection, 16384)
        self.assertFalse(reply["ok"])
        self.assert_closed(connection)
        self.wait_until(lambda: self.server._active_handlers == 0)
        self.assertEqual(self.store.rejected, 1)
        self.assertEqual(self.store.messages, [])

    def test_complete_rejected_observation_keeps_next_frame_boundary(self):
        connection = self.connect()
        connection.sendall(encode_message(dict(invalid=True), MAX_VI_BYTES)
                           + encode_message(observation(2, counter=part()), MAX_VI_BYTES))
        refusal = recv_message(connection, 16384)
        accepted = recv_message(connection, 16384)
        self.assertFalse(refusal["ok"])
        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["result"]["source_sequence"], 2)
        self.assertEqual(self.store.rejected, 1)
        self.assertEqual(len(self.store.messages), 1)

    def test_bad_length_closes_without_interpreting_trailing_payload_as_new_frame(self):
        connection = self.connect()
        connection.sendall(struct.pack("!I", 0)
                           + encode_message(observation(1, counter=part()), MAX_VI_BYTES))
        refusal = recv_message(connection, 16384)
        self.assertFalse(refusal["ok"])
        self.assert_closed(connection)
        self.wait_until(lambda: self.server._active_handlers == 0)
        self.assertEqual(self.store.messages, [])
        self.assertEqual(self.store.rejected, 1)
        self.send_json(self.connect(), 2)

    def test_persistent_clients_keep_existing_four_handler_bound(self):
        occupied = [self.connect() for unused in range(4)]
        for sequence, connection in enumerate(occupied, 1):
            self.send_json(connection, sequence)
        extra = self.connect()
        self.assert_closed(extra)
        self.assertEqual(self.server.handler_limit_rejections, 1)
        for connection in occupied:
            connection.close()
        self.wait_until(lambda: self.server._active_handlers == 0)
        self.send_json(self.connect(), 5)

    def test_shutdown_joins_partial_frame_handler(self):
        with patch(MODULE + ".VI_FRAME_TIMEOUT_SECONDS", .1):
            connection = self.connect()
            connection.sendall(b"\x00")
            self.wait_until(lambda: self.server._active_handlers == 1)
            self.server.shutdown()
            self.server.server_close()
        self.assertEqual(self.server._active_handlers, 0)
        self.assertTrue(all(not worker.is_alive() for worker in self.server.handler_threads))
        self.assertEqual(self.store.messages, [])


if __name__ == "__main__":
    unittest.main()
