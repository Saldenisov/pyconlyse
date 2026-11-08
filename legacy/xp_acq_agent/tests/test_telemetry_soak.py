import socket
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elyse_agent.protocol import recv_message, send_message
from elyse_agent.telemetry_soak import SESSION, SoakServer, SoakStore


def packet(sequence=0, producer='fixture'):
    return dict(id='soak-{0}'.format(sequence), command='ingest_labview_telemetry',
                params=dict(session_id=SESSION, publication='C1NI6071E', sequence=sequence,
                            source_seconds_1904=0, producer_kind=producer,
                            data=[sequence, 1.5, -0.2], error=dict(status=False, code=0, source='')))


class SoakTests(unittest.TestCase):
    def test_latest_duplicate_and_real_producer_rejection(self):
        store = SoakStore()
        self.assertTrue(store.dispatch(packet(), '127.0.0.1:1')['ok'])
        self.assertTrue(store.dispatch(packet(), '127.0.0.1:1')['result']['duplicate'])
        self.assertFalse(store.dispatch(packet(1, 'copied_acquisition'), '127.0.0.1:1')['ok'])
        self.assertTrue(store.dispatch(packet(2), '127.0.0.1:1')['ok'])
        snapshot = store.snapshot()
        self.assertEqual(snapshot['soak']['accepted'], 2)
        self.assertEqual(snapshot['soak']['duplicates'], 1)
        self.assertEqual(snapshot['soak']['sequence_gaps'], 1)
        self.assertEqual(snapshot['soak']['rejected'], 1)
        self.assertEqual(len(snapshot['publications']), 1)
        self.assertEqual(snapshot['publications']['C1NI6071E']['data'], [2, 1.5, -0.2])

    def test_control_commands_and_remote_ingestion_are_rejected(self):
        store = SoakStore()
        request = packet()
        request['command'] = 'initialize'
        self.assertFalse(store.dispatch(request, '127.0.0.1:1')['ok'])
        self.assertFalse(store.dispatch(packet(), '10.20.30.2:1')['ok'])
        self.assertEqual(store.telemetry.outbox.status()['pending'], 0)
        with self.assertRaises(ValueError):
            SoakServer(('0.0.0.0', 0), store)

    def test_native_length_prefixed_tcp_request(self):
        store = SoakStore()
        server = SoakServer(('127.0.0.1', 0), store)
        thread = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=0.01))
        thread.start()
        try:
            with socket.create_connection(server.server_address, timeout=2) as connection:
                send_message(connection, packet(4), 262144)
                reply = recv_message(connection, 262144)
            self.assertEqual(reply['id'], 'soak-4')
            self.assertTrue(reply['ok'])
            self.assertTrue(reply['result']['accepted'])
            self.assertEqual(store.telemetry.outbox.status()['pending'], 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == '__main__':
    unittest.main()
