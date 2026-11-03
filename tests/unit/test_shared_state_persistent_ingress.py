"""VI XML reconnect boundaries and 27-bank preservation, Python 3.4, no NI."""
import socket
import struct
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.protocol import recv_message
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS, SharedStateStore
from legacy.xp_acq_control.elyse_agent.shared_state_receiver import SharedStateServer
from tests.unit.test_telemetry_reconnect import wait_until


def xml():
    rows = []
    for index, bank in enumerate(BANKS):
        rows.append('<Cluster><Name></Name><NumElts>3</NumElts>'
            '<String><Name>bank</Name><Val>{0}</Val></String>'
            '<LvVariant><Name>value</Name><DBL><Name>fixture</Name><Val>{1}</Val></DBL></LvVariant>'
            '<Cluster><Name>error</Name><NumElts>3</NumElts>'
            '<Boolean><Name>status</Name><Val>0</Val></Boolean>'
            '<I32><Name>code</Name><Val>0</Val></I32>'
            '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(bank, index + .25))
    return ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
            + ''.join(rows) + '</Array></LvVariant>').encode('ascii')


class TracedXMLServer(SharedStateServer):
    def __init__(self, *args):
        self.connections = 0
        SharedStateServer.__init__(self, *args)

    def get_request(self):
        result = SharedStateServer.get_request(self)
        self.connections += 1
        return result


class SharedStatePersistentTests(unittest.TestCase):
    def setUp(self):
        self.store, self.clients = SharedStateStore('fixture'), []
        self.server = TracedXMLServer(('127.0.0.1', 0), self.store)
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs=dict(poll_interval=.01))
        self.worker.start()

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.server.shutdown()
        self.worker.join(2)
        self.server.server_close()
        self.assertEqual(self.server._active_handlers, 0)

    def connect(self):
        client = socket.create_connection(self.server.server_address, timeout=3)
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.clients.append(client)
        return client

    def send(self, client, raw=None):
        raw = xml() if raw is None else raw
        client.sendall(struct.pack('!I', len(raw)) + raw)
        return recv_message(client, 262144)

    def test_reuses_connection_after_idle_without_losing_any_bank(self):
        client = self.connect()
        for unused in range(30):
            self.assertEqual(self.send(client)['result']['bank_count'], 27)
        time.sleep(2.1)  # Idle must not use the following frame's 2s deadline.
        self.assertTrue(self.send(client)['ok'])
        self.assertEqual(self.server.connections, 1)
        observed = self.store.outbox.peek()['packet']['data']['banks']
        self.assertEqual([row['publication'] for row in observed], list(BANKS))
        self.assertEqual([row['data'] for row in observed], [i + .25 for i in range(27)])
        self.assertEqual(self.store.snapshot()['rejected'], 0)

    def test_complete_bad_xml_does_not_destroy_next_frame_boundary(self):
        client = self.connect()
        self.assertFalse(self.send(client, b'not XML')['ok'])
        self.assertTrue(self.send(client)['ok'])
        self.assertEqual(self.server.connections, 1)
        self.assertEqual(self.store.snapshot()['bank_count'], 27)

    def test_abandoned_partial_frame_releases_slot_and_new_connection_recovers(self):
        first = self.connect()
        first.sendall(b'\x00')
        wait_until(lambda: self.server._active_handlers == 1)
        first.close()
        wait_until(lambda: self.server._active_handlers == 0)
        self.assertTrue(self.send(self.connect())['ok'])
        self.assertEqual(self.store.snapshot()['bank_count'], 27)
        self.assertEqual(self.store.snapshot()['accepted'], 1)

    def test_shutdown_joins_idle_persistent_client(self):
        client = self.connect()
        self.assertTrue(self.send(client)['ok'])
        self.server.shutdown()
        self.worker.join(2)
        started = time.monotonic()
        self.server.server_close()
        self.assertLess(time.monotonic() - started, 1.)
        self.assertEqual(self.server._active_handlers, 0)


if __name__ == '__main__':
    unittest.main()
