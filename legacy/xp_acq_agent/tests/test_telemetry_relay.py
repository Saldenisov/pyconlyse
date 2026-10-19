"""Python 3.4 FIFO/transport tests; sockets are loopback fixtures only."""
import json
import socket
import unittest
from unittest.mock import patch

from elyse_agent.errors import CommandError
from elyse_agent.labview_telemetry import ALL_PUBLICATIONS, LabviewTelemetryStore
from elyse_agent.telemetry_relay import DeadlineSocket, TelemetryOutbox, TelemetryRelay, sign
from tests.test_labview_telemetry import packet


KEY = b"fixture-key-not-a-production-secret-0123456789"


class OutboxTests(unittest.TestCase):
    def test_1000_limit_preserves_oldest_and_dequeues_in_order(self):
        box = TelemetryOutbox()
        for number in range(1000):
            box.enqueue(json.dumps(dict(number=number)), "fixture UTC")
        with self.assertRaises(ValueError):
            box.enqueue('{}', "fixture UTC")
        self.assertEqual(box.status()['pending'], 1000)
        self.assertEqual(box.status()['rejected_new'], 1)
        for number in range(1000):
            head = box.peek()
            self.assertEqual(head['packet']['number'], number)
            box.acknowledge(head['relay_id'], head['message_id'])
        self.assertIsNone(box.peek())
        self.assertEqual(box.status()['pending_bytes'], 0)
        self.assertEqual(box.status()['everest_acknowledged'], 1000)

    def test_byte_limit_and_wrong_ack_leave_head_unchanged(self):
        box = TelemetryOutbox(max_bytes=2)
        box.enqueue('{}', 'fixture UTC')
        with self.assertRaises(ValueError):
            box.enqueue('{}', 'fixture UTC')
        with self.assertRaises(ValueError):
            box.acknowledge(box.relay_id, 2)
        with self.assertRaises(ValueError):
            box.acknowledge('other', 1)
        self.assertEqual(box.status()['pending'], 1)

    def test_backlog_age_increases_without_altering_message_identity(self):
        now = [10.0]
        box = TelemetryOutbox(clock=lambda: now[0])
        box.enqueue('{}', 'fixture UTC')
        first = box.peek()
        now[0] += 5
        second = box.peek()
        self.assertEqual(second['age_seconds_on_xp'], 5)
        self.assertEqual(first['message_id'], second['message_id'])

    def test_store_overflow_does_not_commit_latest_or_sequence(self):
        box = TelemetryOutbox(capacity=1)
        store = LabviewTelemetryStore('test-session', outbox=box)
        store.ingest(packet(), '127.0.0.1:1')
        self.assertTrue(store.ingest(packet(), '127.0.0.1:1')['duplicate'])
        self.assertEqual(box.status()['pending'], 1)
        with self.assertRaises(CommandError):
            store.ingest(packet(1), '127.0.0.1:1')
        self.assertEqual(store.snapshot()['publications']['C1NI6071E']['sequence'], 0)
        box.acknowledge(box.relay_id, 1)
        store.ingest(packet(1), '127.0.0.1:1')
        self.assertEqual(box.peek()['message_id'], 2)

    def test_all_19_families_require_explicit_opt_in(self):
        self.assertEqual(len(ALL_PUBLICATIONS), 19)
        normal = LabviewTelemetryStore('test-session')
        expanded = LabviewTelemetryStore('test-session', include_all_publications=True)
        for name in ALL_PUBLICATIONS:
            value = dict(packet(), publication=name, source_site='uid-1')
            expanded.ingest(value, '127.0.0.1:1')
        self.assertFalse(expanded.snapshot()['missing_publications'])
        with self.assertRaises(CommandError):
            normal.ingest(dict(packet(), publication='C6NI6703'), '127.0.0.1:1')


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.box = TelemetryOutbox()
        self.box.enqueue(json.dumps(packet()), 'fixture UTC')
        self.relay = TelemetryRelay(self.box, ('127.0.0.1', 8767), KEY)

    def test_connection_failure_retains_head(self):
        with patch('elyse_agent.telemetry_relay.socket.create_connection', side_effect=socket.error('fixture')):
            with self.assertRaises(socket.error):
                self.relay.send_once()
        self.assertEqual(self.box.status()['pending'], 1)

    def test_thread_start_failure_can_be_closed_without_orphan(self):
        with patch('elyse_agent.telemetry_relay.threading.Thread.start',
                   side_effect=RuntimeError('fixture start failure')):
            with self.assertRaises(RuntimeError):
                self.relay.start()
        self.assertIsNone(self.relay._thread)
        self.relay.close()
        self.assertEqual(self.box.status()['pending'], 1)

    def test_bad_unsigned_or_wrong_id_ack_retains_head(self):
        for reply in ({}, dict(body={}, nonce='x', signature='wrong')):
            with patch('elyse_agent.telemetry_relay.socket.create_connection'), \
                    patch('elyse_agent.telemetry_relay.send_message'), \
                    patch('elyse_agent.telemetry_relay.recv_message', return_value=reply):
                with self.assertRaises(ValueError):
                    self.relay.send_once()
            self.assertEqual(self.box.status()['pending'], 1)

    def test_matching_authenticated_ack_removes_one_head(self):
        captured = []
        def acknowledge(connection, limit):
            request = captured[0]
            body = dict(accepted=True, relay_id=self.box.relay_id, message_id=1, duplicate=False)
            signed = dict(body=body, nonce=request['nonce'])
            return dict(signed, signature=sign(KEY, 'ACQ-TELEMETRY-ACK-1', signed))
        with patch('elyse_agent.telemetry_relay.socket.create_connection'), \
                patch('elyse_agent.telemetry_relay.send_message', side_effect=lambda c, r, m: captured.append(r)), \
                patch('elyse_agent.telemetry_relay.recv_message', side_effect=acknowledge):
            self.assertTrue(self.relay.send_once())
        self.assertEqual(self.box.status()['pending'], 0)

    def test_absolute_deadline_is_not_reset_by_partial_receive(self):
        now = [1.0]
        class Connection(object):
            def settimeout(self, value):
                self.timeout = value
            def recv(self, size):
                return b'x'
        connection = Connection()
        bounded = DeadlineSocket(connection, 2.0, clock=lambda: now[0])
        self.assertEqual(bounded.recv(1), b'x')
        self.assertEqual(connection.timeout, 1.0)
        now[0] = 1.75
        bounded.recv(1)
        self.assertEqual(connection.timeout, 0.25)
        now[0] = 2.0
        with self.assertRaises(socket.timeout):
            bounded.recv(1)


if __name__ == '__main__':
    unittest.main()
