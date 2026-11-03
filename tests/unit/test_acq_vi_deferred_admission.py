"""Real Python 3.4 compatible, driver-free VI/lifecycle contention regressions."""
import copy
import socket
import struct
import threading
import time
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.protocol import recv_message
from tests.unit.test_acq_modular_server import KEY, PausedOwner, vi_xml, wait_until


class DeferredAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.calls, self.clock = [], [100.]
        self.runtime = AcquisitionControlRuntime(lambda: self.calls.append('NI'), clock=lambda: self.clock[0])
        self.publisher = DualModeTelemetryPublisher(self.runtime, ('127.0.0.1', 1), KEY,
            ingress_address=('127.0.0.1', 0), clock=lambda: self.clock[0])
        self.runtime.telemetry_publisher = self.publisher
        self.publisher.outbox._clock = lambda: self.clock[0]

    def tearDown(self):
        self.publisher.close()
        self.assertEqual(self.calls, [])

    def stage(self, raw=None):
        with PausedOwner(self.runtime):
            result = self.publisher.ingest(raw or vi_xml(), '127.0.0.1')
            self.assertTrue(result['admission_pending'])
            self.assertFalse(self.publisher._drain_deferred_once())
        return result

    def test_metadata_lock_contention_defers_then_publishes_all_27_banks(self):
        self.stage()
        self.assertEqual(self.publisher.vi_accepted, 0)
        self.assertEqual(self.publisher.outbox.status()['pending'], 0)
        self.assertTrue(self.publisher._drain_deferred_once())
        body = self.publisher.outbox.peek()
        self.assertEqual(len(body['packet']['data']['banks']), 27)
        self.assertTrue(all(row['data'] == 1.25 for row in body['packet']['data']['banks']))
        self.assertEqual(self.publisher.vi_accepted, 1)
        self.assertEqual(self.publisher.rejected, 0)
        self.assertEqual(self.publisher.last_error, '')

    def test_staging_is_one_latest_slot_under_a_long_owner_pause(self):
        with PausedOwner(self.runtime):
            for index in range(30):
                raw = vi_xml().replace(b'1.25', str(index + .25).encode('ascii'))
                self.publisher.ingest(raw, '127.0.0.1')
            status = self.publisher.status()
            self.assertEqual(status['vi_deferred_capacity'], 1)
            self.assertEqual(status['vi_deferred_pending'], 1)
            self.assertEqual(status['vi_deferred_replaced'], 29)
        self.publisher._drain_deferred_once()
        self.assertEqual(self.publisher.outbox.peek()['packet']['data']['banks'][0]['data'], 29.25)

    def test_deferred_source_age_and_timestamp_are_not_renewed(self):
        self.stage()
        original_stamp = self.publisher._pending_vi[3].timestamp() + 2082844800
        self.clock[0] += .7
        self.publisher._drain_deferred_once()
        body = self.publisher.outbox.peek()
        self.assertAlmostEqual(body['age_seconds_on_xp'], .7)
        self.assertEqual(body['packet']['source_seconds_1904'], original_stamp)
        self.assertEqual(self.publisher.last_vi_receipt, 100.)
        self.clock[0] += .5
        self.assertAlmostEqual(self.publisher.outbox.peek()['age_seconds_on_xp'], 1.2)

    def test_expired_observation_is_rejected_without_publishing(self):
        self.stage()
        self.clock[0] += 2
        self.publisher._drain_deferred_once()
        self.assertEqual(self.publisher.outbox.status()['pending'], 0)
        self.assertEqual(self.publisher.last_error, 'VI_DEFERRED_SOURCE_EXPIRED')
        self.assertEqual(self.publisher.status()['vi_deferred_rejected'], 1)

    def test_staged_frame_cannot_cross_a_complete_native_owner_epoch(self):
        self.stage()
        # Even an eventual IDLE cannot authorize a pre-transition observation.
        self.runtime._state_revision += 2
        self.publisher._drain_deferred_once()
        self.assertEqual(self.publisher.outbox.status()['pending'], 0)
        self.assertEqual(self.publisher.last_error, 'VI_INGRESS_OWNER_EPOCH_CHANGED')

    def test_unknown_contended_state_never_becomes_native_admission(self):
        self.runtime._state = 'INITIALIZING'
        self.stage()
        self.publisher._drain_deferred_once()
        self.assertEqual(self.publisher.vi_accepted, 0)
        self.assertIn('INGRESS_DISABLED', self.publisher.last_error)

    def test_latest_seen_vi_blocks_initialize_even_if_nothing_was_published(self):
        self.stage()
        with self.assertRaisesRegex(RuntimeError, 'LabVIEW telemetry is still arriving'):
            self.runtime.initialize(startup_confirmed=True)
        self.assertEqual(self.runtime._state, 'IDLE')
        self.assertIsNone(self.runtime._backend)

    def test_new_fast_frame_supersedes_pending_old_frame(self):
        self.stage()
        self.publisher.ingest(vi_xml().replace(b'1.25', b'9.25'), '127.0.0.1')
        self.assertEqual(self.publisher.status()['vi_deferred_pending'], 0)
        self.publisher._drain_deferred_once()
        self.assertEqual(self.publisher.outbox.peek()['packet']['data']['banks'][0]['data'], 9.25)

    def test_slow_old_xml_parse_cannot_overtake_new_admitted_frame(self):
        from legacy.xp_acq_control.elyse_agent import dual_mode_telemetry as module
        original = module.decode_snapshot_xml
        entered, release, replies = threading.Event(), threading.Event(), []
        def decode(raw, encoding):
            result = original(raw, encoding)
            if b'1.25' in raw:
                entered.set()
                self.assertTrue(release.wait(3))
            return result
        with mock.patch.object(module, 'decode_snapshot_xml', decode):
            worker = threading.Thread(target=lambda: replies.append(
                self.publisher.ingest(vi_xml(), '127.0.0.1')))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.publisher.ingest(vi_xml().replace(b'1.25', b'8.25'), '127.0.0.1')
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(replies[0]['superseded'])
        self.assertEqual(self.publisher.outbox.peek()['packet']['data']['banks'][0]['data'], 8.25)

    def test_malformed_or_nonloopback_input_is_not_staged_or_seen(self):
        with self.assertRaises(ValueError):
            self.publisher.ingest(b'<broken>', '127.0.0.1')
        with self.assertRaises(ValueError):
            self.publisher.ingest(vi_xml(), '10.20.30.202')
        self.assertIsNone(self.publisher.last_vi_seen)
        self.assertEqual(self.publisher.status()['vi_deferred_pending'], 0)

    def test_real_ingress_ack_reports_staging_and_worker_drains_on_release(self):
        # Only loopback sockets. Relay is intentionally not started.
        from legacy.xp_acq_control.elyse_agent.shared_state_receiver import SharedStateServer
        self.publisher.server = SharedStateServer(('127.0.0.1', 0), self.publisher)
        self.publisher.ingress_worker = threading.Thread(target=lambda:
            self.publisher.server.serve_forever(poll_interval=.01))
        self.publisher.vi_admission_worker = threading.Thread(target=self.publisher._vi_admission_loop)
        self.publisher.ingress_worker.start()
        self.publisher.vi_admission_worker.start()
        with PausedOwner(self.runtime):
            with socket.create_connection(self.publisher.server.server_address, timeout=2) as connection:
                raw = vi_xml()
                connection.sendall(struct.pack('!I', len(raw)) + raw)
                reply = recv_message(connection, 1048576)
                self.assertTrue(reply['ok'])
                self.assertTrue(reply['result']['admission_pending'])
                self.assertIsNone(reply['result']['sequence'])
            self.assertEqual(self.publisher.vi_accepted, 0)
        wait_until(lambda: self.publisher.vi_accepted == 1)
        self.assertEqual(self.publisher.rejected, 0)

    def test_shutdown_does_not_wait_for_busy_native_owner_or_create_backend(self):
        self.publisher.vi_admission_worker = threading.Thread(target=self.publisher._vi_admission_loop)
        self.publisher.vi_admission_worker.start()
        with PausedOwner(self.runtime):
            self.publisher.ingest(vi_xml(), '127.0.0.1')
            started = time.monotonic()
            self.publisher.close()
            self.assertLess(time.monotonic() - started, .5)
            self.assertFalse(self.publisher.vi_admission_worker.is_alive())
        self.assertEqual(self.publisher.vi_accepted, 0)


if __name__ == '__main__':
    unittest.main()
