"""Deterministic offline concurrency tests; also run on actual Python 3.4.

Only loopback sockets and injected RAM backends. No NI DLL, live receiver,
Tango database, XP process or instrument is contacted.
"""
import copy
import json
import socket
import socketserver
import tempfile
import threading
import time
import unittest
import urllib.request
from types import SimpleNamespace
from uuid import uuid4

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker
from legacy.xp_acq_control.elyse_agent.command_dispatch import CommandDispatcher
from legacy.xp_acq_control.elyse_agent.command_broker import CommandBroker
from legacy.xp_acq_control.elyse_agent.command_http import ControlHTTPServer
from legacy.xp_acq_control.elyse_agent.command_protocol import command_signature
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher, BRIDGE_SITE
from legacy.xp_acq_control.elyse_agent.standard_banks import BANKS, INPUTS, validate_standard_packet
from legacy.xp_acq_control.elyse_agent.telemetry_relay import DeadlineSocket, sign, MAX_RELAY_FRAME
from legacy.xp_acq_control.elyse_agent.protocol import recv_message, send_message
from tests.unit.test_acq_control_release import AdmissionRuntime, command

KEY = b'offline-modular-telemetry-read-key-00000000'
COMMAND_KEY = b'offline-modular-command-only-key-00000000'


def vi_xml():
    rows = []
    for bank in BANKS:
        rows.append('<Cluster><Name></Name><NumElts>3</NumElts>'
            '<String><Name>bank</Name><Val>{0}</Val></String>'
            '<LvVariant><Name>value</Name><DBL><Name>fixture</Name><Val>1.25</Val></DBL></LvVariant>'
            '<Cluster><Name>error</Name><NumElts>3</NumElts>'
            '<Boolean><Name>status</Name><Val>0</Val></Boolean>'
            '<I32><Name>code</Name><Val>0</Val></I32>'
            '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(bank))
    return ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
            + ''.join(rows) + '</Array></LvVariant>').encode('ascii')


def sample():
    banks = {}
    for unused, (name, kind, device, count, field, scalar) in INPUTS.items():
        record = dict(kind=kind, device=device, values=[False if scalar == 'Boolean' else 1.] * count)
        if scalar == 'DBL':
            record[field] = [123.] * count
        banks[name] = record
    return dict(source='python_daqmx_acquisition', simulated=False, banks=banks)


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Offline synchronization condition not reached')


def in_thread(callback):
    result = dict(value=None, error=None)
    def run():
        try:
            result['value'] = callback()
        except Exception as error:
            result['error'] = error
    worker = threading.Thread(target=run)
    worker.start()
    return worker, result


class PausedOwner(object):
    def __init__(self, runtime):
        self.entered, self.release = threading.Event(), threading.Event()
        def hold():
            with runtime._lock:
                self.entered.set()
                if not self.release.wait(5):
                    raise AssertionError('Offline owner-lock test was not released')
        self.worker = threading.Thread(target=hold)

    def __enter__(self):
        self.worker.start()
        assert self.entered.wait(3)
        return self

    def __exit__(self, *args):
        self.release.set()
        self.worker.join(3)
        assert not self.worker.is_alive()


class PausedBroker(object):
    def __init__(self, delegate=None):
        self.entered, self.release = threading.Event(), threading.Event()
        self.calls, self.delegate = [], delegate

    def submit(self, request, lease):
        self.calls.append((copy.deepcopy(request), threading.current_thread().name))
        self.entered.set()
        if not self.release.wait(5):
            raise AssertionError('Offline command test was not released')
        if self.delegate is not None:
            return self.delegate.submit(request, lease)
        return dict(outcome='QUEUED', hardware_acknowledged=False)


class LoopbackSink(object):
    def __init__(self, pause_ack=False):
        self.entered, self.release = threading.Event(), threading.Event()
        self.received, self.errors = [], []
        if not pause_ack:
            self.release.set()
        owner = self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    connection = DeadlineSocket(self.request, time.monotonic() + 3)
                    request = recv_message(connection, MAX_RELAY_FRAME)
                    signed = dict(body=request['body'], nonce=request['nonce'])
                    assert request['signature'] == sign(KEY, 'ACQ-TELEMETRY-REQUEST-1', signed)
                    packet = request['body']['packet']
                    assert len(packet['data']['banks']) == 27
                    if packet['producer_kind'] == 'python_acquisition':
                        validate_standard_packet(packet)
                    owner.received.append(copy.deepcopy(packet))
                    owner.entered.set()
                    assert owner.release.wait(3)
                    body = request['body']
                    response = dict(body=dict(accepted=True, duplicate=False, relay_id=body['relay_id'],
                        message_id=body['message_id'], storage_mode='ram_latest', durable=False), nonce=request['nonce'])
                    response['signature'] = sign(KEY, 'ACQ-TELEMETRY-ACK-1', response)
                    send_message(connection, response, MAX_RELAY_FRAME)
                except Exception as error:
                    owner.errors.append(error)
        self.server = socketserver.TCPServer(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.02))
        self.worker.start()

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)


class TelemetryIsolationTests(unittest.TestCase):
    def setUp(self):
        self.calls, self.clock = [], [100.]
        self.runtime = AcquisitionControlRuntime(lambda: self.calls.append(True), clock=lambda: self.clock[0])
        self.publisher = DualModeTelemetryPublisher(self.runtime, ('127.0.0.1', 1), KEY,
            ingress_address=('127.0.0.1', 0), clock=lambda: self.clock[0])
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        self.publisher.close()
        self.assertEqual(self.calls, [])

    def take_packet(self):
        body = self.publisher.outbox.peek()
        packet = copy.deepcopy(body['packet'])
        self.publisher.outbox.acknowledge(body['relay_id'], body['message_id'])
        return packet

    def native_memory(self):
        # A RUNNING label alone is not evidence of a current NI owner.
        self.runtime._backend = SimpleNamespace(resource_count=21)
        self.runtime._state, self.runtime._state_revision = 'RUNNING', 1
        self.runtime._latest, self.runtime._received_at = sample(), self.clock[0]

    def test_projection_and_vi_ingress_never_enter_metadata_disk_or_command_ledger(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('Telemetry entered a command/metadata/filesystem path')
        self.runtime.snapshot = forbidden
        self.runtime._recovery_snapshot = forbidden
        self.runtime.broker.snapshot = self.runtime.cooling.snapshot = forbidden
        self.assertTrue(self.publisher.publish_once())
        self.take_packet()
        self.assertTrue(self.publisher.ingest(vi_xml(), '127.0.0.1')['accepted'])
        self.assertEqual(self.take_packet()['data']['banks'][0]['data'], 1.25)
        self.native_memory()
        self.assertTrue(self.publisher.publish_once())
        self.assertEqual(self.take_packet()['data']['banks'][0]['data'], [123.] * 64)

    def test_command_owner_lock_contention_publishes_null_without_wait_or_freshness_reset(self):
        self.native_memory()
        self.publisher.publish_once(); self.take_packet()
        with PausedOwner(self.runtime):
            self.clock[0] += 3
            started = time.monotonic()
            self.assertTrue(self.publisher.publish_once())
            self.assertLess(time.monotonic() - started, .5)
            self.assertTrue(all(row['data'] is None for row in self.take_packet()['data']['banks']))
            view = self.publisher.view.snapshot()
            self.assertEqual(view['age_seconds'], 3)
            self.assertFalse(view['telemetry_view_current'])
            self.assertFalse(self.publisher.status()['telemetry_view']['owner_lock_waiting'])
        self.assertTrue(self.publisher.publish_once())
        self.assertTrue(all(row['data'] is None for row in self.take_packet()['data']['banks']))
        self.runtime._received_at, self.runtime._sequence = self.clock[0], 1
        self.assertTrue(self.publisher.publish_once())
        self.assertEqual(self.take_packet()['data']['banks'][0]['data'], [123.] * 64)

    def test_cold_contended_capture_never_invents_measurements_or_initializes(self):
        with PausedOwner(self.runtime):
            self.assertTrue(self.publisher.publish_once())
            self.assertTrue(all(row['data'] is None for row in self.take_packet()['data']['banks']))
            self.assertFalse(self.publisher.status()['owner_state_current'])
        self.assertEqual(self.runtime.try_telemetry_snapshot()['state'], 'IDLE')

    def test_recent_vi_is_not_erased_or_retimestamped_by_a_contended_idle_poll(self):
        self.publisher.outbox._clock = lambda: self.clock[0]
        self.publisher.ingest(vi_xml(), '127.0.0.1')
        before = copy.deepcopy(self.publisher.outbox.peek())
        before_age = before.pop('age_seconds_on_xp')
        with PausedOwner(self.runtime):
            self.clock[0] += .2
            started = time.monotonic()
            self.assertFalse(self.publisher.publish_once())
            self.assertLess(time.monotonic() - started, .5)
            self.assertFalse(self.publisher.status()['owner_state_current'])
            retained = self.publisher.outbox.peek()
            self.assertGreater(retained.pop('age_seconds_on_xp'), before_age)
            self.assertEqual(retained, before)
        self.assertFalse(self.publisher.publish_once())
        retained = self.publisher.outbox.peek()
        self.assertGreater(retained.pop('age_seconds_on_xp'), before_age)
        self.assertEqual(retained, before)
        self.assertTrue(self.publisher.status()['owner_state_current'])
        self.assertEqual(self.publisher.vi_accepted, 1)
        with self.assertRaisesRegex(RuntimeError, 'LabVIEW telemetry is still arriving'):
            self.runtime.initialize(startup_confirmed=True)

    def test_bridge_contention_suppression_expires_at_the_initialize_quiet_boundary(self):
        self.publisher.ingest(vi_xml(), '127.0.0.1'); self.take_packet()
        with PausedOwner(self.runtime):
            self.clock[0] += 2
            self.assertTrue(self.publisher.publish_once())
            rows = self.take_packet()['data']['banks']
            self.assertTrue(all(row['data'] is None for row in rows))
            self.assertTrue(all(row['error']['source'] == 'OWNER_STATE_BUSY' for row in rows))
        self.assertTrue(self.publisher.publish_once())
        rows = self.take_packet()['data']['banks']
        self.assertTrue(all(row['data'] is None for row in rows))
        self.assertIsNone(self.publisher.last_vi_receipt)
        self.assertFalse(self.publisher.publish_once())

    def test_confirmed_non_idle_epoch_is_not_hidden_by_recent_vi_receipt(self):
        self.publisher.ingest(vi_xml(), '127.0.0.1'); self.take_packet()
        self.native_memory()
        self.assertTrue(self.publisher.publish_once())
        self.assertEqual(self.take_packet()['producer_kind'], 'python_acquisition')
        with PausedOwner(self.runtime):
            self.assertTrue(self.publisher.publish_once())
            self.assertTrue(all(row['data'] is None for row in self.take_packet()['data']['banks']))

    def test_out_of_order_capture_cannot_roll_back_cached_source_epoch(self):
        old = self.runtime.try_telemetry_snapshot()
        new = dict(old, state_revision=2, sequence=5, telemetry_bridge_mode=False)
        captures = [new, old, None]
        self.runtime.try_telemetry_snapshot = lambda: captures.pop(0)
        self.publisher.view.snapshot()
        self.publisher.view.snapshot()  # Older concurrent capture arrives late.
        busy = self.publisher.view.snapshot()
        self.assertEqual(busy['state_revision'], 2)
        self.assertFalse(busy['telemetry_bridge_mode'])
        self.assertFalse(busy['telemetry_view_current'])

    def test_contended_vi_ingress_rejects_fast_but_seen_traffic_still_fences_initialize(self):
        with PausedOwner(self.runtime):
            started = time.monotonic()
            with self.assertRaisesRegex(ValueError, 'OWNER_STATE_BUSY_VI_NOT_ADMITTED'):
                self.publisher.ingest(vi_xml(), '127.0.0.1')
            self.assertLess(time.monotonic() - started, .5)
        with self.assertRaisesRegex(RuntimeError, 'LabVIEW telemetry is still arriving'):
            self.runtime.initialize(startup_confirmed=True)
        self.assertEqual(self.publisher.vi_accepted, 0)

    def test_old_native_poll_cannot_overwrite_new_vi_image_after_deinitialization(self):
        self.native_memory()
        self.publisher.publish_once(); self.take_packet()
        original, entered, release = self.publisher.view.snapshot, threading.Event(), threading.Event()
        first = [True]
        def delayed():
            value = original()
            if first[0]:
                first[0] = False
                entered.set()
                assert release.wait(3)
            return value
        self.publisher.view.snapshot = delayed
        worker, result = in_thread(self.publisher.publish_once)
        try:
            self.assertTrue(entered.wait(3))
            with self.runtime._lock:
                self.runtime._state, self.runtime._state_revision = 'IDLE', 2
                self.runtime._backend = None
            self.publisher.ingest(vi_xml(), '127.0.0.1')
        finally:
            release.set(); worker.join(3)
        self.assertIsNone(result['error'])
        self.assertFalse(result['value'])
        packet = self.take_packet()
        self.assertEqual(packet['source_site'], BRIDGE_SITE)
        self.assertEqual(packet['data']['banks'][0]['data'], 1.25)
        self.assertFalse(self.publisher.publish_once())

    def test_signed_telemetry_keeps_acknowledging_while_http_admission_holds_owner_lock(self):
        sink = LoopbackSink()
        self.runtime.broker.enabled = True
        original, entered, release = self.runtime.broker.submit, threading.Event(), threading.Event()
        def paused(request, lease):
            with self.runtime._lock:
                entered.set()
                assert release.wait(3)
                return original(request, lease)
        self.runtime.broker.submit = paused
        server = ControlHTTPServer(('127.0.0.1', 0), self.runtime, KEY, COMMAND_KEY)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02))
        worker.start()
        self.publisher.relay.address = sink.server.server_address
        self.publisher.start()
        request = command()
        request.update(session_id=self.runtime._identity['session_id'], expected_revision=0)
        body = json.dumps(dict(request=request, lease=self.runtime.broker.snapshot(True)['lease'])).encode('utf-8')
        nonce = uuid4().hex
        http = urllib.request.Request('http://127.0.0.1:{0}/commands'.format(server.server_port), data=body,
            headers={'X-ACQ-Nonce': nonce, 'X-ACQ-Signature': command_signature(COMMAND_KEY, nonce, body),
                     'Content-Type': 'application/json'})
        def post():
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            response = opener.open(http, timeout=2)
            try:
                return json.loads(response.read().decode('utf-8'))
            finally:
                response.close()
        caller = None
        try:
            wait_until(lambda: self.publisher.status()['everest_acknowledged'] >= 1)
            caller, result = in_thread(post)
            self.assertTrue(entered.wait(3))
            wait_until(lambda: self.publisher.status()['everest_acknowledged'] >= 2)
            self.assertFalse(self.publisher.status()['owner_state_current'])
            self.assertTrue(all(row['data'] is None for row in sink.received[-1]['data']['banks']))
            self.assertFalse(sink.errors)
        finally:
            release.set()
            if caller is not None: caller.join(3)
            server.shutdown(); server.server_close(); worker.join(3)
            self.publisher.close(); sink.close()
        self.assertIsNone(result['error'])
        self.assertEqual(result['value']['outcome'], 'REJECTED')  # IDLE never authorizes a stage.

    def test_waiting_for_network_ack_cannot_block_command_worker(self):
        sink = LoopbackSink(pause_ack=True)
        owner = AdmissionRuntime()
        broker = CommandBroker(owner, enabled=True)
        dispatcher = CommandDispatcher(broker)
        dispatcher.start()
        self.publisher.relay.address = sink.server.server_address
        self.publisher.start()
        try:
            self.assertTrue(sink.entered.wait(3))
            lease = broker.snapshot(True)['lease']
            self.assertEqual(dispatcher.submit(command(), lease)['outcome'], 'QUEUED')
            self.assertEqual(len(owner.calls), 1)
            self.assertFalse(sink.release.is_set())
            sink.release.set()
            wait_until(lambda: self.publisher.status()['everest_acknowledged'] >= 1)
        finally:
            sink.release.set(); dispatcher.close(); self.publisher.close(); sink.close()


class CommandWorkerTests(unittest.TestCase):
    def test_admission_timeout_has_unknown_outcome_no_retry_and_same_id_is_at_most_once(self):
        owner = AdmissionRuntime()
        ledger = CommandBroker(owner, enabled=True)
        broker = PausedBroker(ledger)
        dispatcher = CommandDispatcher(broker, reply_timeout=.05)
        dispatcher.start()
        try:
            lease = ledger.snapshot(True)['lease']
            with self.assertRaisesRegex(RuntimeError, 'OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY'):
                dispatcher.submit(command(), lease)
            self.assertEqual(len(broker.calls), 1)
            broker.release.set()
            wait_until(lambda: not dispatcher.status()['active'])
            self.assertEqual(len(owner.calls), 1)
            receipt = dispatcher.submit(command(), None)
            self.assertTrue(receipt['duplicate'])
            self.assertEqual(len(owner.calls), 1)
            self.assertTrue(all(name == 'ACQ-command-admission' for unused, name in broker.calls))
        finally:
            broker.release.set(); dispatcher.close()

    def test_expired_pending_command_is_removed_not_executed_later(self):
        broker = PausedBroker()
        dispatcher = CommandDispatcher(broker, reply_timeout=.15)
        dispatcher.start()
        worker, result = in_thread(lambda: dispatcher.submit(command(), None))
        try:
            self.assertTrue(broker.entered.wait(3))
            other = command(); other['command_id'] = uuid4().hex
            with self.assertRaisesRegex(RuntimeError, 'EXPIRED_NOT_SUBMITTED'):
                dispatcher.submit(other, None)
            self.assertEqual(dispatcher.status()['pending'], 0)
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertIn('OUTCOME_UNKNOWN', str(result['error']))
            broker.release.set(); worker.join(3)
            wait_until(lambda: not dispatcher.status()['active'])
            self.assertEqual(len(broker.calls), 1)
        finally:
            broker.release.set(); worker.join(3); dispatcher.close()

    def test_queue_bound_close_cancels_pending_but_never_replaces_blocked_worker(self):
        broker = PausedBroker()
        dispatcher = CommandDispatcher(broker, reply_timeout=1.5)
        dispatcher.start()
        first, first_result = in_thread(lambda: dispatcher.submit(command(), None))
        second = None
        try:
            self.assertTrue(broker.entered.wait(3))
            other = command(); other['command_id'] = uuid4().hex
            second, second_result = in_thread(lambda: dispatcher.submit(other, None))
            wait_until(lambda: dispatcher.status()['pending'] == 1)
            with self.assertRaisesRegex(RuntimeError, 'BUSY_NOT_SUBMITTED'):
                dispatcher.submit(command(), None)
            with self.assertRaisesRegex(RuntimeError, 'still owned; replacement refused'):
                dispatcher.close(timeout=.01)
            second.join(3)
            self.assertIn('CLOSED_NOT_SUBMITTED', str(second_result['error']))
            with self.assertRaisesRegex(RuntimeError, 'cannot start twice'):
                dispatcher.start()
            with self.assertRaisesRegex(RuntimeError, 'COMMAND_ADMISSION_CLOSED'):
                dispatcher.submit(command(), None)
        finally:
            broker.release.set(); first.join(3)
            if second is not None: second.join(3)
            dispatcher.close()
        self.assertEqual(len(broker.calls), 1)
        self.assertFalse(first.is_alive())
        self.assertIsNone(first_result['error'])

    def test_invalid_request_never_reaches_worker_or_broker(self):
        broker = PausedBroker(); broker.release.set()
        dispatcher = CommandDispatcher(broker)
        dispatcher.start()
        try:
            invalid = command(); invalid['operation'] = 'raw.write'
            self.assertRaises(ValueError, dispatcher.submit, invalid, None)
            self.assertEqual(broker.calls, [])
        finally:
            dispatcher.close()

    def test_http_socket_remains_owned_until_active_admission_has_returned(self):
        runtime = AcquisitionControlRuntime(lambda: None)
        broker = PausedBroker()
        broker.enabled = False
        runtime.broker = broker
        server = ControlHTTPServer(('127.0.0.1', 0), runtime, KEY)
        close = server.dispatcher.close
        server.dispatcher.close = lambda: close(timeout=.01)
        worker, result = in_thread(lambda: server.dispatcher.submit(command(), None))
        try:
            self.assertTrue(broker.entered.wait(3))
            with self.assertRaisesRegex(RuntimeError, 'still owned; replacement refused'):
                server.server_close()
            probe = socket.socket()
            try:
                self.assertRaises(OSError, probe.bind, server.server_address)
            finally:
                probe.close()
        finally:
            broker.release.set(); worker.join(3); server.server_close()
        self.assertFalse(server.dispatcher.status()['worker_alive'])
        self.assertIsNone(result['error'])


class SingleNIOwnerTests(unittest.TestCase):
    def test_long_fake_native_command_keeps_one_owner_and_telemetry_becomes_unavailable(self):
        entered, release, calls = threading.Event(), threading.Event(), []
        class FakeBackend(object):
            resource_count, stage_controls_verified, control_profile = 0, True, 'legacy_full'
            def record(self, name): calls.append((name, threading.current_thread().ident))
            def initialize(self, cancel, startup_confirmed=False):
                self.record('initialize'); self.resource_count = 1
            def read_snapshot(self, cancel):
                self.record('read'); return sample()
            def execute_stage(self, operation, cancel, operator_confirmed=False):
                self.record(operation); entered.set(); assert release.wait(3)
            def close(self):
                self.record('close'); self.resource_count = 0
        backend = FakeBackend()
        runtime = AcquisitionControlRuntime(lambda: backend, remote_enabled=True, period=.02)
        publisher = DualModeTelemetryPublisher(runtime, ('127.0.0.1', 1), KEY)
        runtime.telemetry_publisher = publisher
        dispatcher = CommandDispatcher(runtime.broker)
        with tempfile.TemporaryDirectory() as folder:
            runtime._recovery_guard = OwnershipMarker(folder + '/offline.ownership',
                runtime._identity['session_id'], runtime._identity['build_id'])
            runtime.start(); dispatcher.start()
            try:
                runtime.initialize(startup_confirmed=True)
                wait_until(lambda: (runtime.try_telemetry_snapshot() or {}).get('sequence', 0) >= 1)
                publisher.publish_once()
                before = publisher.outbox.peek(); publisher.outbox.acknowledge(before['relay_id'], before['message_id'])
                request = command('chauffage.stop')
                request.update(session_id=runtime._identity['session_id'], expected_revision=runtime._state_revision)
                lease = runtime.broker.snapshot(True)['lease']
                self.assertEqual(dispatcher.submit(request, lease)['outcome'], 'QUEUED')
                self.assertTrue(entered.wait(3))
                reads = sum(name == 'read' for name, unused in calls)
                self.assertTrue(publisher.publish_once())
                self.assertTrue(all(row['data'] is None for row in publisher.outbox.peek()['packet']['data']['banks']))
                self.assertEqual(sum(name == 'read' for name, unused in calls), reads)
                self.assertEqual(runtime.try_telemetry_snapshot()['state'], 'EXECUTING')
                release.set()
                wait_until(lambda: (runtime.try_telemetry_snapshot() or {}).get('state') == 'RUNNING')
                self.assertEqual(runtime.broker.snapshot()['results'][0]['outcome'], 'COMPLETED')
            finally:
                release.set(); dispatcher.close(); publisher.close()
                runtime.request_shutdown(electrical_off_confirmed=True)
                self.assertTrue(runtime.join(3))
        self.assertEqual(len(set(ident for unused, ident in calls)), 1)
        self.assertNotEqual(calls[0][1], threading.current_thread().ident)
        self.assertEqual(calls[-1][0], 'close')


if __name__ == '__main__':
    unittest.main()
