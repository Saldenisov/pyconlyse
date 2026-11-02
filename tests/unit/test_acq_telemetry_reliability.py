"""Python 3.4 regression tests: fake NI owner and private loopback only."""
import json
import os
import socket
import struct
import tempfile
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher

KEY = b'test-only-reliability-key-not-a-deployed-secret'


def xml():
    from legacy.xp_acq_control.elyse_agent.shared_state import BANKS
    rows = []
    for i, name in enumerate(BANKS):
        rows.append('<Cluster><Name></Name><NumElts>3</NumElts>'
          '<String><Name>bank</Name><Val>{0}</Val></String>'
          '<LvVariant><Name>value</Name><DBL><Name>fixture</Name><Val>{1}</Val></DBL></LvVariant>'
          '<Cluster><Name>error</Name><NumElts>3</NumElts>'
          '<Boolean><Name>status</Name><Val>0</Val></Boolean>'
          '<I32><Name>code</Name><Val>0</Val></I32>'
          '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(name, i + .25))
    return ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
            + ''.join(rows) + '</Array></LvVariant>').encode('ascii')


class Pair(unittest.TestCase):
    def setUp(self):
        self.factory_calls = []
        self.runtime = AcquisitionControlRuntime(lambda: self.factory_calls.append(True))
        self.now = [100.]
        self.publisher = DualModeTelemetryPublisher(self.runtime, ('127.0.0.1', 1), KEY,
                                                    clock=lambda: self.now[0])
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        self.publisher.close()
        self.assertEqual(self.factory_calls, [])


class LockTests(Pair):
    def test_xml_encoding_does_not_retain_owner_lock(self):
        entered, release, errors = threading.Event(), threading.Event(), []
        original = self.publisher._enqueue
        def slow(*args, **kwargs):
            entered.set()
            if not release.wait(3): raise AssertionError('Test encoding release missing')
            return original(*args, **kwargs)
        self.publisher._enqueue = slow
        def receive():
            try: self.publisher.ingest(xml(), '127.0.0.1')
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=receive)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            free = self.runtime._lock.acquire(False)
            if free: self.runtime._lock.release()
            self.assertTrue(free, 'XML encoding retained the NI/lifecycle lock')
        finally:
            release.set(); thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.publisher.vi_accepted, 1)

    def test_metadata_waiting_for_publisher_does_not_retain_owner_lock(self):
        entered, release, errors = threading.Event(), threading.Event(), []
        class SlowPublisher:
            def status(self):
                entered.set()
                if not release.wait(3): raise AssertionError('Test metadata release missing')
                return {'test': True}
        self.runtime.telemetry_publisher = SlowPublisher()
        def capture():
            try: self.runtime.snapshot()
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=capture)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            free = self.runtime._lock.acquire(False)
            if free: self.runtime._lock.release()
            self.assertTrue(free, 'Publisher metadata retained the NI/lifecycle lock')
        finally:
            release.set(); thread.join(3)
        self.assertEqual(errors, [])

    def test_initialize_racing_encoding_still_rejects_live_vi(self):
        entered, release, init_started = threading.Event(), threading.Event(), threading.Event()
        original, errors, results = self.publisher._enqueue, [], []
        def slow(*args, **kwargs):
            entered.set()
            if not release.wait(3): raise AssertionError('Encoding test timed out')
            return original(*args, **kwargs)
        self.publisher._enqueue = slow
        def receive():
            try: self.publisher.ingest(xml(), '127.0.0.1')
            except Exception as error: errors.append(error)
        def initialize():
            init_started.set()
            try: self.runtime.initialize(startup_confirmed=True)
            except RuntimeError as error: results.append(str(error))
        reader, command = threading.Thread(target=receive), threading.Thread(target=initialize)
        reader.start()
        try:
            self.assertTrue(entered.wait(2))
            command.start()
            self.assertTrue(init_started.wait(1))
        finally:
            release.set(); reader.join(3)
            if command.ident is not None: command.join(3)
        self.assertEqual(errors, [])
        self.assertTrue(results and 'LabVIEW telemetry is still arriving' in results[0])
        self.assertEqual(self.runtime._state, 'IDLE')


class IngressTests(Pair):
    def test_actual_loopback_reports_complete_frames_and_rejects_bad_framing(self):
        from legacy.xp_acq_control.elyse_agent.protocol import recv_message
        publisher = self.publisher
        class NoNetworkRelay:
            _thread = None
            def start(self): pass
            def close(self): pass
            def status(self): return dict(publisher.outbox.status(), last_error='')
        publisher.relay = NoNetworkRelay()
        publisher.ingress_address = ('127.0.0.1', 0)
        publisher.publish_once = lambda: False  # Isolate ingestion from poll contention.
        publisher.start()
        raw = xml()
        with socket.create_connection(publisher.server.server_address, timeout=2) as conn:
            conn.sendall(struct.pack('!I', len(raw)) + raw)
            answer = recv_message(conn, 1048576)
        self.assertTrue(answer['ok'])
        self.assertEqual(answer['result']['bank_count'], 27)
        with socket.create_connection(publisher.server.server_address, timeout=2) as conn:
            conn.sendall(b'\x00\x00\x00\x00')
            answer = recv_message(conn, 1048576)
        self.assertFalse(answer['ok'])
        stats = publisher.status()['ingress_statistics']
        self.assertEqual(stats['connections_seen'], 2)
        self.assertEqual(stats['xml_frames_seen'], 1)
        self.assertEqual(stats['xml_bytes_seen'], len(raw))
        self.assertEqual(stats['accepted_frames'], 1)
        self.assertEqual(stats['rejected_frames'], 1)

    def test_slow_encoding_does_not_refresh_an_old_xml_receipt(self):
        from legacy.xp_acq_control.elyse_agent import dual_mode_telemetry as module
        original = module.validate_snapshot_packet
        def slow(packet):
            self.now[0] += 3
            return original(packet)
        module.validate_snapshot_packet = slow
        try:
            self.publisher.ingest(xml(), '127.0.0.1')
        finally:
            module.validate_snapshot_packet = original
        self.assertGreaterEqual(self.publisher.outbox.peek()['age_seconds_on_xp'], 3)
        self.assertEqual(self.publisher.last_vi_receipt, 100.)
        self.assertEqual(self.publisher.status()['transport_health'], 'VI_SOURCE_SILENT')

    def test_listener_exception_retries_same_server_without_starting_a_process(self):
        parent = self
        class Server:
            calls = 0
            def handle_request(self):
                self.calls += 1
                if self.calls == 1: raise OSError('synthetic accept failure')
                parent.publisher.stop_event.set()
        server = Server()
        self.publisher.server = server
        try:
            self.publisher._ingress_loop()
            self.assertEqual(server.calls, 2)
            self.assertEqual(self.publisher.ingress_loop_failures, 1)
            self.assertIn('synthetic accept failure', self.publisher.ingress_loop_error)
        finally:
            self.publisher.server = None

    def test_source_silence_is_distinct_from_admission_failure(self):
        self.assertEqual(self.publisher.status()['transport_health'], 'WAITING_FOR_VI')
        self.publisher.ingest(xml(), '127.0.0.1')
        self.assertEqual(self.publisher.status()['transport_health'], 'RECEIVING_VI')
        sequence = self.publisher.sequence
        self.now[0] += 3
        self.assertEqual(self.publisher.status()['transport_health'], 'VI_SOURCE_SILENT')
        self.assertEqual(self.publisher.sequence, sequence)

    def test_fresh_valid_vi_blocks_initialize_even_when_owner_lock_was_busy(self):
        held, release = threading.Event(), threading.Event()
        def hold():
            with self.runtime._lock:
                held.set(); release.wait(3)
        thread = threading.Thread(target=hold)
        thread.start()
        try:
            self.assertTrue(held.wait(2))
            with self.assertRaises(ValueError): self.publisher.ingest(xml(), '127.0.0.1')
            self.assertEqual(self.publisher.status()['transport_health'], 'VI_ADMISSION_BLOCKED')
        finally:
            release.set(); thread.join(3)
        with self.assertRaises(RuntimeError): self.runtime.initialize(startup_confirmed=True)


class DiagnosticsTests(unittest.TestCase):
    def test_gui_explains_source_silence_without_adding_a_button(self):
        from legacy.xp_acq_control.elyse_agent.acquisition_control_gui import telemetry_route_text, BUTTON_LABELS
        text = telemetry_route_text(dict(transport_health='VI_SOURCE_SILENT', vi_accepted=5,
                                         vi_rejected=1, vi_seen_age_seconds=12.5))
        self.assertIn('VI_SOURCE_SILENT', text)
        self.assertIn('last valid XML: 12.5s ago', text)
        self.assertEqual(BUTTON_LABELS, ('Initialize', 'Deinitialize', 'Stop server'))

    def test_diagnostic_thread_start_failure_does_not_block_telemetry(self):
        from legacy.xp_acq_control.elyse_agent import telemetry_diagnostics as module
        original = module.threading.Thread
        class BrokenThread:
            def __init__(self, **kwargs): pass
            def start(self): raise RuntimeError('synthetic diagnostic thread unavailable')
        module.threading.Thread = BrokenThread
        try:
            d = module.TelemetryDiagnostics(path='unused-test-path')
            d.start()
            self.assertIn('synthetic diagnostic thread unavailable', d.snapshot()['last_write_error'])
            self.assertFalse(d.snapshot()['required_for_telemetry'])
            d.close()
        finally:
            module.threading.Thread = original

    def test_memory_events_have_growing_ids_and_bounded_history(self):
        from legacy.xp_acq_control.elyse_agent.telemetry_diagnostics import TelemetryDiagnostics
        d = TelemetryDiagnostics()
        for i in range(50): d.emit('TEST', count=i)
        s = d.snapshot()
        self.assertEqual(s['event_sequence'], 50)
        self.assertEqual(len(s['recent_events']), 16)
        self.assertEqual(s['recent_events'][-1]['event_sequence'], 50)
        self.assertFalse(s['required_for_telemetry'])

    def test_stuck_filesystem_cannot_block_emit_or_shutdown(self):
        from legacy.xp_acq_control.elyse_agent.telemetry_diagnostics import TelemetryDiagnostics
        d = TelemetryDiagnostics(path='unused-test-path', capacity=1)
        entered, release = threading.Event(), threading.Event()
        def stalled(row):
            entered.set(); release.wait(3)
        d._write = stalled
        d.start()
        try:
            d.emit('FIRST')
            self.assertTrue(entered.wait(1))
            d.emit('SECOND'); d.emit('OVERFLOW')
            self.assertEqual(d.snapshot()['dropped'], 1)
            began = time.monotonic()
            d.close(timeout=.01)
            self.assertLess(time.monotonic() - began, .2)
            self.assertTrue(d.snapshot()['writer_alive'])
        finally:
            release.set(); d.close(timeout=1)

    def test_write_error_is_reported_without_becoming_a_launch_gate(self):
        from legacy.xp_acq_control.elyse_agent.telemetry_diagnostics import TelemetryDiagnostics
        d = TelemetryDiagnostics(path='unused-test-path')
        def failed(row): raise OSError('synthetic disk unavailable')
        d._write = failed
        d.start(); d.emit('TEST')
        try:
            until = time.monotonic() + 2
            while d.snapshot()['dropped'] == 0 and time.monotonic() < until: time.sleep(.01)
            self.assertEqual(d.snapshot()['dropped'], 1)
            self.assertIn('synthetic disk unavailable', d.snapshot()['last_write_error'])
            self.assertFalse(d.snapshot()['required_for_telemetry'])
        finally:
            d.close()

    def test_log_rotation_retains_only_current_and_one_backup(self):
        from legacy.xp_acq_control.elyse_agent.telemetry_diagnostics import TelemetryDiagnostics
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'events.jsonl')
            with open(path, 'wb') as stream: stream.write(b'x' * (2 * 1024 * 1024))
            d = TelemetryDiagnostics(path=path)
            d.start(); d.emit('AFTER_ROTATION')
            d.close(timeout=2)
            self.assertTrue(os.path.isfile(path + '.1'))
            with open(path) as stream: self.assertEqual(json.load(stream)['kind'], 'AFTER_ROTATION')


if __name__ == '__main__':
    unittest.main()
