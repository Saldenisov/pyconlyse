"""Everest receiver proof: authenticated, bounded RAM, telemetry-only loopback."""
import copy
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkServer, TelemetrySinkStore
from legacy.xp_acq_agent.elyse_agent.labview_telemetry import LabviewTelemetryStore
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import TelemetryOutbox, TelemetryRelay, sign

KEY = b'fixture-key-not-a-production-secret-0123456789'


def packet(sequence=0):
    return dict(session_id='fixture-session', publication='C1NI6071E', sequence=sequence,
                source_seconds_1904=3870000000.25, producer_kind='fixture', data=[1.5, None, -0.2],
                error=dict(status=False, code=0, source=''))


def request(body, key=KEY):
    signed = dict(body=body, nonce='a' * 32)
    return dict(signed, signature=sign(key, 'ACQ-TELEMETRY-REQUEST-1', signed))


class SinkTests(unittest.TestCase):
    def test_receive_only_restart_shows_old_failed_countdown_as_history(self):
        from legacy.xp_acq_control.elyse_agent.cooling_safety import CoolingSafety, AlarmJournal, utc
        old = AlarmJournal(str(self.path), 'receiver')
        old.begin_session()
        state = dict(incidents=dict(SECTION=dict(circuit='SECTION',
            started_utc=utc(1000.), deadline_utc=utc(1120.), deadline_epoch=1120.,
            causes=[dict(signal='flow', raw=True)])),
            stop_state='FAILED', stop_error='previous experiment stop failure')
        old.append(state, dict(kind='SHUTDOWN_FAILED'))
        old.end_session(True)
        old.close()
        self.store.close()
        alarm = CoolingSafety.with_journal(str(self.path), 'receiver')
        self.store = TelemetrySinkStore(KEY, cooling=alarm)
        deadline = time.monotonic() + 3
        while not alarm.snapshot()['journal_ready'] and time.monotonic() < deadline:
            time.sleep(.005)
        observed = self.store.snapshot()['cooling_safety']
        self.assertTrue(observed['receive_only'])
        self.assertFalse(observed['active'])
        self.assertEqual(observed['stop_state'], 'NONE')
        self.assertIsNone(observed['remaining_seconds'])
        self.assertEqual(observed['historical_incidents'][0]['prior_stop_error'],
                         'previous experiment stop failure')
        self.assertFalse(observed['automatic_stop_available'])

    def test_receive_only_observer_has_no_shutdown_countdown_authority(self):
        observed = self.store.snapshot()['cooling_safety']
        self.assertTrue(observed['receive_only'])
        self.assertFalse(observed['active'])
        self.assertFalse(observed['countdown_required'])
        self.assertFalse(observed['automatic_stop_available'])

    def test_fixture_only_filter_rejects_real_producer_claim_before_acceptance(self):
        store = TelemetrySinkStore(KEY, permitted_producer_kind='fixture')
        body = self.box.peek()
        body['packet']['producer_kind'] = 'copied_acquisition'
        with self.assertRaisesRegex(ValueError, 'producer kind'):
            store.accept(request(body))
        self.assertEqual(store.snapshot()['received_this_process'], 0)
        self.assertEqual(store.snapshot()['publications'], {})
        body['packet']['producer_kind'] = 'fixture'
        self.assertTrue(store.accept(request(body))['body']['accepted'])
        self.assertEqual(store.snapshot()['permitted_producer_kind'], 'fixture')
        store.close()
        with self.assertRaises(ValueError):
            TelemetrySinkStore(KEY, permitted_producer_kind='hardware')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'fixture.sqlite'
        self.now = [10.0]
        self.store = TelemetrySinkStore(KEY, clock=lambda: self.now[0])
        self.box = TelemetryOutbox(clock=lambda: self.now[0])
        self.box.enqueue(json.dumps(packet()), '2026-10-12T10:00:00Z')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_ack_lost_retry_is_ram_duplicate_and_never_refreshes_age(self):
        first = self.store.accept(request(self.box.peek()))
        self.assertFalse(first['body']['duplicate'])
        self.assertFalse(first['body']['durable'])
        self.assertEqual(first['body']['storage_mode'], 'ram_latest')
        self.now[0] += 5
        second = self.store.accept(request(self.box.peek()))
        self.assertTrue(second['body']['duplicate'])
        snapshot = self.store.snapshot()['publications']['C1NI6071E']
        self.assertEqual(snapshot['age_seconds'], 5)
        self.assertTrue(snapshot['stale'])
        self.store.close()
        self.store = TelemetrySinkStore(KEY)
        self.assertEqual(self.store.snapshot()['publications'], {})
        self.assertFalse(self.store.accept(request(self.box.peek()))['body']['duplicate'])
        self.assertFalse(self.path.exists())

    def test_wrong_key_malformed_packet_changed_content_and_out_of_order_rejected(self):
        original = self.box.peek()
        with self.assertRaises(ValueError):
            self.store.accept(request(original, b'wrong-key-not-a-production-secret-0123456789'))
        for mutate in (lambda b: b.update(schema_version=True),
                       lambda b: b['packet'].update(sequence=True),
                       lambda b: b['packet'].update(extra='write')):
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(Exception):
                self.store.accept(request(value))
        self.store.accept(request(original))
        out_of_order = copy.deepcopy(original)
        out_of_order['message_id'] = 3
        with self.assertRaisesRegex(ValueError, 'out of order'):
            self.store.accept(request(out_of_order))
        changed = copy.deepcopy(original)
        changed['packet']['data'] = [99]
        with self.assertRaises(ValueError):
            self.store.accept(request(changed))
        self.assertEqual(self.store.snapshot()['received_this_process'], 1)

    def test_backlog_is_stale_at_receipt_not_mislabeled_fresh(self):
        self.now[0] += 6
        self.store.accept(request(self.box.peek()))
        value = self.store.snapshot()['publications']['C1NI6071E']
        self.assertTrue(value['stale'])
        self.assertEqual(value['age_seconds'], 6)

    def test_all_19_observed_publications_and_source_site_preserved(self):
        self.box = TelemetryOutbox()
        value = dict(packet(), publication='C6NI6703', data=[0.5], source_site='uid-16580')
        self.box.enqueue(json.dumps(value), 'fixture UTC')
        self.store.accept(request(self.box.peek()))
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot['publications']['C6NI6703']['source_site'], 'uid-16580')
        self.assertFalse(snapshot['hardware_writes'])
        self.assertFalse(snapshot['physical_measurements_verified'])

    def test_loopback_xp_store_fifo_relay_everest_ram_full_path(self):
        server = TelemetrySinkServer(('127.0.0.1', 0), self.store, permitted_peers=('127.0.0.1',))
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
        thread.start()
        try:
            xp_store = LabviewTelemetryStore('fixture-session')
            relay = TelemetryRelay(xp_store.outbox, server.server_address, KEY)
            for sequence in range(3):
                xp_store.ingest(packet(sequence), '127.0.0.1:1')
            for sequence in range(3):
                self.assertTrue(relay.send_once())
                self.assertEqual(self.store.snapshot()['publications']['C1NI6071E']['sequence'], sequence)
            self.assertEqual(xp_store.outbox.status()['everest_acknowledged'], 3)
            self.assertEqual(xp_store.outbox.status()['pending'], 0)
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()

    def test_no_sqlite_files_or_unbounded_message_history(self):
        self.box = TelemetryOutbox()
        with patch('sqlite3.connect', side_effect=AssertionError('SQLite forbidden')):
            for sequence in range(200):
                self.box.enqueue(json.dumps(packet(sequence)), 'fixture UTC')
                body = self.box.peek()
                self.store.accept(request(body))
                self.box.acknowledge(body['relay_id'], body['message_id'])
            snapshot = self.store.snapshot()
            self.assertEqual(snapshot['received_this_process'], 200)
            self.assertEqual(len(snapshot['publications']), 1)
            self.assertEqual(len(self.store.relays), 1)
            self.assertFalse(snapshot['durable'])
            self.assertFalse(snapshot['history_available'])
            self.assertTrue(snapshot['reset_on_restart'])
            self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_restart_accepts_current_xp_head_without_requiring_id_one(self):
        self.store.accept(request(self.box.peek()))
        first = self.box.peek()
        self.box.acknowledge(first['relay_id'], first['message_id'])
        self.box.enqueue(json.dumps(packet(1)), 'fixture UTC')
        session = self.store.snapshot()['receiver_session']
        self.store.close()
        self.store = TelemetrySinkStore(KEY)
        self.assertNotEqual(self.store.snapshot()['receiver_session'], session)
        self.assertEqual(self.store.snapshot()['publications'], {})
        ack = self.store.accept(request(self.box.peek()))
        self.assertEqual(ack['body']['message_id'], 2)
        self.assertFalse(ack['body']['duplicate'])
        old = copy.deepcopy(first)
        with self.assertRaisesRegex(ValueError, 'out of order'):
            self.store.accept(request(old))

    def test_relay_identity_limit_rejects_new_without_forgetting_duplicates(self):
        self.store.close()
        self.store = TelemetrySinkStore(KEY, max_relays=2)
        body = self.box.peek()
        self.store.accept(request(body))
        second = dict(body, relay_id='b' * 32)
        self.store.accept(request(second))
        with self.assertRaisesRegex(ValueError, 'capacity reached'):
            self.store.accept(request(dict(body, relay_id='c' * 32)))
        self.assertTrue(self.store.accept(request(body))['body']['duplicate'])
        self.assertEqual(self.store.snapshot()['relay_sessions'], 2)

    def test_close_prevents_new_receipts_and_snapshot_cannot_mutate_store(self):
        self.store.accept(request(self.box.peek()))
        snapshot = self.store.snapshot()
        snapshot['publications']['C1NI6071E']['data'][0] = 99
        self.assertEqual(self.store.snapshot()['publications']['C1NI6071E']['data'][0], 1.5)
        self.store.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            self.store.accept(request(self.box.peek()))

    def test_invalid_relay_limits_rejected(self):
        for limit in (True, 0, -1, 1025, 1.5):
            with self.assertRaises(ValueError):
                TelemetrySinkStore(KEY, max_relays=limit)


if __name__ == '__main__':
    unittest.main()
