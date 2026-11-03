"""Persistent signed telemetry and outage recovery; real sockets, no NI/VI."""
import copy
import hashlib
import json
import select
import socket
import socketserver
import sys
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.protocol import recv_message, send_message
from legacy.xp_acq_control.elyse_agent.shared_state import LatestSnapshotOutbox
from legacy.xp_acq_control.elyse_agent.telemetry_relay import (
    MAX_RELAY_FRAME, TelemetryRelay, canonical, sign,
)

KEY = b'telemetry-reconnect-fixture-not-a-production-key'


def packet(sequence):
    return dict(session_id='fixture-session', publication='C1NI6071E', sequence=sequence,
                source_seconds_1904=3870000000.25, producer_kind='fixture', data=[1.5],
                error=dict(status=False, code=0, source=''))


def wait_until(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Timed out waiting for transport fixture')


class FixtureHandler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        with server.lock:
            server.connections += 1
            server.active.add(self.request)
        try:
            self.request.settimeout(.5)
            while not server.stopping.is_set():
                if not select.select([self.request], [], [], .05)[0]:
                    continue
                request = recv_message(self.request, MAX_RELAY_FRAME)
                body = request['body']
                signed = dict(body=body, nonce=request['nonce'])
                if request['signature'] != sign(KEY, 'ACQ-TELEMETRY-REQUEST-1', signed):
                    raise ValueError('Fixture authentication failed')
                identity = dict(body)
                identity.pop('age_seconds_on_xp')
                digest = hashlib.sha256(canonical(identity)).hexdigest()
                key = body['relay_id'], body['message_id']
                with server.lock:
                    if key in server.seen:
                        if server.seen[key] != digest:
                            raise ValueError('Retry changed immutable packet')
                        server.duplicates += 1
                    else:
                        server.seen[key] = digest
                        server.delivered.append(copy.deepcopy(body))
                    lose_ack = server.lose_ack
                    server.lose_ack = False
                    silent = server.silent
                    server.silent = False
                if lose_ack:
                    return
                if silent:
                    server.stopping.wait(.2)
                    return
                ack = dict(body=dict(accepted=True, relay_id=body['relay_id'], message_id=body['message_id']),
                           nonce=request['nonce'])
                if server.bad_ack:
                    ack['nonce'] = '0' * 32
                send_message(self.request, dict(ack, signature=sign(KEY, 'ACQ-TELEMETRY-ACK-1', ack)),
                             MAX_RELAY_FRAME)
                if server.one_shot:
                    return
        except (EOFError, OSError):
            pass
        except Exception as error:
            server.errors.append(str(error))
        finally:
            with server.lock:
                server.active.discard(self.request)


class FixtureServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address=('127.0.0.1', 0), handler=FixtureHandler):
        self.lock, self.stopping = threading.Lock(), threading.Event()
        self.active, self.seen, self.delivered, self.errors = set(), {}, [], []
        self.connections = self.duplicates = 0
        self.lose_ack = self.silent = self.bad_ack = self.one_shot = False
        socketserver.TCPServer.__init__(self, address, handler)
        self.worker = threading.Thread(target=self.serve_forever, kwargs=dict(poll_interval=.01))
        self.worker.daemon = True
        self.worker.start()

    def stop(self):
        self.stopping.set()
        self.shutdown()
        with self.lock:
            active = tuple(self.active)
        for connection in active:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.worker.join(2)
        self.server_close()
        wait_until(lambda: not self.active)


class RelayReconnectTests(unittest.TestCase):
    def setUp(self):
        self.servers, self.relays = [], []

    def tearDown(self):
        for relay in self.relays:
            relay.close()
        for server in reversed(self.servers):
            if not server.stopping.is_set():
                server.stop()
            self.assertEqual(server.errors, [])

    def receiver(self, address=('127.0.0.1', 0)):
        server = FixtureServer(address)
        self.servers.append(server)
        return server

    def relay(self, address, clock=None):
        relay = TelemetryRelay(LatestSnapshotOutbox(clock=clock), address, KEY, timeout=.1, retry_seconds=.02)
        self.relays.append(relay)
        return relay

    def enqueue(self, relay, sequence):
        relay.outbox.enqueue(json.dumps(packet(sequence)), 'fixture UTC')

    def test_thousand_packets_reuse_one_connection_including_idle_gap(self):
        server = self.receiver()
        relay = self.relay(server.server_address)
        for sequence in range(1000):
            self.enqueue(relay, sequence)
            self.assertTrue(relay.send_once())
        time.sleep(.15)
        self.enqueue(relay, 1000)
        self.assertTrue(relay.send_once())
        self.assertEqual(server.connections, 1)
        self.assertEqual(len(server.delivered), 1001)
        self.assertEqual(relay.status()['connections_opened'], 1)
        self.assertEqual(relay.status()['failed_attempts'], 0)

    def test_background_worker_recovers_when_receiver_starts_later(self):
        reserve = socket.socket()
        reserve.bind(('127.0.0.1', 0))
        address = reserve.getsockname()
        reserve.close()
        relay = self.relay(address)
        self.enqueue(relay, 1)
        relay.start()
        wait_until(lambda: relay.status()['failed_attempts'] >= 2)
        self.assertTrue(relay.status()['worker_alive'])
        self.assertEqual(relay.status()['pending'], 1)
        server = self.receiver(address)
        wait_until(lambda: relay.status()['everest_acknowledged'] == 1)
        self.assertEqual(len(server.delivered), 1)
        self.assertEqual(relay.status()['last_error'], '')

    def test_receiver_restart_reconnects_without_producer_restart_or_sequence_reset(self):
        first = self.receiver()
        address = first.server_address
        relay = self.relay(address)
        self.enqueue(relay, 1)
        relay.start()
        wait_until(lambda: relay.status()['everest_acknowledged'] == 1)
        first.stop()
        self.enqueue(relay, 2)
        wait_until(lambda: relay.status()['failed_attempts'] >= 1)
        second = self.receiver(address)
        wait_until(lambda: relay.status()['everest_acknowledged'] == 2)
        self.assertEqual(second.delivered[0]['message_id'], 2)
        self.assertEqual(second.delivered[0]['packet']['sequence'], 2)
        self.assertGreaterEqual(relay.status()['connections_opened'], 2)

    def test_lost_ack_retries_same_head_without_freshening_source_then_sends_latest(self):
        server = self.receiver()
        now = [10.]
        relay = self.relay(server.server_address, lambda: now[0])
        self.enqueue(relay, 1)
        server.lose_ack = True
        with self.assertRaises(EOFError):
            relay.send_once()
        now[0] = 15.
        self.enqueue(relay, 2)
        self.enqueue(relay, 3)
        self.assertEqual(relay.outbox.peek()['age_seconds_on_xp'], 5.)
        self.assertTrue(relay.send_once())
        self.assertTrue(relay.send_once())
        self.assertEqual(server.duplicates, 1)
        self.assertEqual([body['packet']['sequence'] for body in server.delivered], [1, 3])
        self.assertEqual([body['message_id'] for body in server.delivered], [1, 2])

    def test_silent_receiver_times_out_and_background_worker_retries(self):
        server = self.receiver()
        server.silent = True
        relay = self.relay(server.server_address)
        self.enqueue(relay, 1)
        relay.start()
        wait_until(lambda: relay.status()['everest_acknowledged'] == 1)
        self.assertGreaterEqual(relay.status()['failed_attempts'], 1)
        self.assertEqual(server.duplicates, 1)

    def test_authenticated_wrong_ack_cannot_drop_pending_packet(self):
        server = self.receiver()
        server.bad_ack = True
        relay = self.relay(server.server_address)
        self.enqueue(relay, 1)
        with self.assertRaises(ValueError):
            relay.send_once()
        self.assertFalse(relay.status()['connected'])
        self.assertEqual(relay.status()['pending'], 1)
        server.bad_ack = False
        self.assertTrue(relay.send_once())
        self.assertEqual(len(server.delivered), 1)

    def test_legacy_one_shot_receiver_remains_compatible_via_retry(self):
        server = self.receiver()
        server.one_shot = True
        relay = self.relay(server.server_address)
        relay.start()
        for sequence in range(3):
            self.enqueue(relay, sequence)
            wait_until(lambda: relay.status()['everest_acknowledged'] == sequence + 1)
        self.assertEqual(len(server.delivered), 3)
        self.assertEqual(server.connections, 3)

    def test_close_releases_idle_connection_and_cannot_restart_closed_worker(self):
        server = self.receiver()
        relay = self.relay(server.server_address)
        relay.start()
        self.enqueue(relay, 1)
        wait_until(lambda: relay.status()['everest_acknowledged'] == 1)
        relay.close()
        wait_until(lambda: not server.active)
        self.assertFalse(relay.status()['worker_alive'])
        self.assertFalse(relay.status()['connected'])
        with self.assertRaises(RuntimeError):
            relay.start()

    def test_camera_worker_recovers_from_initial_outage_and_receiver_restart(self):
        from legacy.xp_acq_control.elyse_agent.camera_latest import LatestCameraFrameQueue
        from legacy.xp_acq_control.elyse_agent.camera_stream import CameraFrameReceiver, CameraFrameSender
        from tests.unit.test_camera_stream import metadata

        class CameraHandler(socketserver.BaseRequestHandler):
            def handle(self):
                server = self.server
                with server.lock:
                    server.connections += 1
                    server.active.add(self.request)
                try:
                    self.request.settimeout(.5)
                    while not server.stopping.is_set():
                        if select.select([self.request], [], [], .05)[0]:
                            server.camera_receiver.receive_once(self.request)
                except (EOFError, OSError):
                    pass
                except Exception as error:
                    server.errors.append(str(error))
                finally:
                    with server.lock:
                        server.active.discard(self.request)

        def camera_receiver(address):
            server = FixtureServer(address, CameraHandler)
            server.camera_receiver = CameraFrameReceiver(KEY,
                lambda meta, raw: server.delivered.append(meta['sequence']))
            self.servers.append(server)
            return server

        reserve = socket.socket()
        reserve.bind(('127.0.0.1', 0))
        address = reserve.getsockname()
        reserve.close()
        queue = LatestCameraFrameQueue(capacity=1)
        queue.enqueue(metadata(1), b'abcd')
        sender = CameraFrameSender(queue, address, KEY, timeout=.1, retry_seconds=.02)
        self.relays.append(sender)
        sender.start()
        wait_until(lambda: sender.status()['failed_attempts'] >= 2)
        self.assertTrue(sender.status()['worker_alive'])
        first = camera_receiver(address)
        wait_until(lambda: queue.status()['acknowledged'] == 1)
        first.stop()
        failures = sender.status()['failed_attempts']
        queue.enqueue(metadata(2), b'efgh')
        wait_until(lambda: sender.status()['failed_attempts'] > failures)
        queue.enqueue(metadata(3), b'ijkl')
        second = camera_receiver(address)
        wait_until(lambda: queue.status()['acknowledged'] == 3)
        self.assertEqual(first.delivered, [1])
        self.assertEqual(second.delivered, [2, 3])
        self.assertEqual(second.connections, 1)
        self.assertEqual(sender.receiver_changes, 1)
        self.assertEqual(sender.status()['last_error'], '')


@unittest.skipIf(sys.version_info < (3, 8), 'Everest receiver requires modern Python')
class EverestPersistentTests(unittest.TestCase):
    def test_sink_rejects_extra_connection_and_close_interrupts_partial_frame(self):
        from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkServer, TelemetrySinkStore
        store = TelemetrySinkStore(KEY)
        server = TelemetrySinkServer(('127.0.0.1', 0), store,
                                     permitted_peers=('127.0.0.1',), max_clients=1)
        worker = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=.01))
        worker.start()
        first = socket.create_connection(server.server_address, timeout=1)
        second = None
        try:
            first.sendall(b'\x00')  # Stalled partial length header, not a valid publication.
            wait_until(lambda: server.status()['active_connections'] == 1)
            second = socket.create_connection(server.server_address, timeout=1)
            wait_until(lambda: server.status()['rejected_busy'] == 1)
            self.assertEqual(store.snapshot()['received_this_process'], 0)
            self.assertEqual(server.status()['connections_opened'], 1)
            server.shutdown()
            worker.join(2)
            started = time.monotonic()
            server.server_close()
            # Winsock may retain a blocking recv until its 2s transaction
            # deadline despite shutdown; ownership must still end within 3s.
            self.assertLess(time.monotonic() - started, 2.8)
            self.assertEqual(server.status()['active_connections'], 0)
        finally:
            first.close()
            if second is not None:
                second.close()
            if worker.is_alive():
                server.shutdown()
                worker.join(2)
            server.server_close()
            store.close()

    def test_actual_sink_keeps_connection_and_close_wakes_idle_handler(self):
        from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkServer, TelemetrySinkStore
        store = TelemetrySinkStore(KEY)
        server = TelemetrySinkServer(('127.0.0.1', 0), store, permitted_peers=('127.0.0.1',))
        worker = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=.01))
        worker.start()
        relay = TelemetryRelay(LatestSnapshotOutbox(), server.server_address, KEY)
        try:
            for sequence in range(20):
                relay.outbox.enqueue(json.dumps(packet(sequence)), 'fixture UTC')
                self.assertTrue(relay.send_once())
            self.assertEqual(server.status()['connections_opened'], 1)
            self.assertEqual(server.status()['active_connections'], 1)
            self.assertEqual(store.snapshot()['received_this_process'], 20)
            server.shutdown()
            worker.join(2)
            started = time.monotonic()
            server.server_close()
            self.assertLess(time.monotonic() - started, 1.)
            self.assertEqual(server.status()['active_connections'], 0)
        finally:
            relay.close()
            if worker.is_alive():
                server.shutdown()
                worker.join(2)
            server.server_close()
            store.close()


if __name__ == '__main__':
    unittest.main()
