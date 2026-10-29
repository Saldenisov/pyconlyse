"""No hardware. Disk queue failure/replay and independent live view tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock
import zlib

from DeviceServers.control.elyse_acq.telemetry_archive import (
    DurableArchive, PostgresStore, encoded, ingress_record, telemetry_only_record)
from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore
from tests.unit.test_acq_telemetry_sink import KEY, packet, request
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import TelemetryOutbox


class FakeStore:
    def __init__(self):
        self.rows = {}
        self.fail = False

    def initialize(self):
        pass

    def write_records(self, rows):
        if self.fail:
            raise ConnectionError('fixture database offline')
        for row in rows:
            self.rows.setdefault(row['uid'], row)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Path(self.temp.name) / 'config.json'
        self.config.write_text(json.dumps(dict(spool_path=str(Path(self.temp.name) / 'spool.sqlite'))))
        self.pg = FakeStore()
        self.archive = DurableArchive(self.config, store=self.pg, min_free_bytes=0)
        self.sink = TelemetrySinkStore(KEY, archive=self.archive)
        self.box = TelemetryOutbox()
        self.box.enqueue(json.dumps(packet()), 'fixture-time')

    def tearDown(self):
        self.sink.close()
        self.archive.close()
        self.temp.cleanup()

    def test_durable_spool_before_acceptance_and_database_delivery(self):
        self.assertTrue(self.sink.accept(request(self.box.peek()))['body']['accepted'])
        self.assertEqual(self.archive.status()['pending'], 1)
        self.assertEqual(self.archive.drain_once(), 1)
        self.assertEqual(self.archive.status()['pending'], 0)
        row = next(iter(self.pg.rows.values()))
        self.assertEqual(row['snapshot']['publications']['C1NI6071E']['data'], [1.5, None, -0.2])
        self.assertTrue(self.sink.snapshot()['history_available'])

    def test_database_failure_retains_pending_after_restart_and_deduplicates(self):
        self.sink.accept(request(self.box.peek()))
        self.pg.fail = True
        with self.assertRaises(ConnectionError):
            self.archive.drain_once()
        self.assertEqual(self.archive.status()['pending'], 1)
        self.sink.close()
        self.archive.close()
        self.archive = DurableArchive(self.config, store=self.pg, min_free_bytes=0)
        self.sink = TelemetrySinkStore(KEY, archive=self.archive)
        self.assertTrue(self.sink.accept(request(self.box.peek()))['body']['accepted'])
        self.assertEqual(self.archive.status()['pending'], 1)
        self.pg.fail = False
        self.archive.drain_once()
        self.assertEqual(len(self.pg.rows), 1)

    def test_spool_failure_does_not_advance_counter_or_publish_unarchived_frame(self):
        self.archive.max_pending = 0
        with self.assertRaisesRegex(RuntimeError, 'capacity'):
            self.sink.accept(request(self.box.peek()))
        self.assertEqual(self.sink.snapshot()['received_this_process'], 0)
        self.assertEqual(self.sink.snapshot()['publications'], {})
        self.archive.max_pending = 10
        self.assertTrue(self.sink.accept(request(self.box.peek()))['body']['accepted'])

    def test_slow_disk_does_not_hold_snapshot_lock_and_age_is_not_refreshed(self):
        entered, release = threading.Event(), threading.Event()
        original = self.archive.append_ingress
        def delayed(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('fixture')
            return original(*args)
        self.archive.append_ingress = delayed
        thread = threading.Thread(target=self.sink.accept, args=(request(self.box.peek()),))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            self.assertEqual(self.sink.snapshot()['received_this_process'], 0)
            self.archive.status()
            self.assertLess(time.monotonic() - start, 0.1)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.sink.snapshot()['received_this_process'], 1)

    def test_authentication_rejection_never_reaches_archive(self):
        bad = request(self.box.peek())
        bad['signature'] = '0' * 64
        with self.assertRaises(ValueError):
            self.sink.accept(bad)
        self.assertEqual(self.archive.status()['pending'], 0)

    def test_duplicate_does_not_enqueue_or_refresh_observation_time(self):
        self.sink.accept(request(self.box.peek()))
        before = self.sink.snapshot()['publications']['C1NI6071E']['received_utc_on_everest']
        self.assertTrue(self.sink.accept(request(self.box.peek()))['body']['duplicate'])
        after = self.sink.snapshot()['publications']['C1NI6071E']['received_utc_on_everest']
        self.assertEqual(before, after)
        self.assertEqual(self.archive.status()['pending'], 1)

    def test_preserves_integer_precision_boolean_none_and_error_quality(self):
        value = self.box.peek()
        value['packet']['data'] = [2**63 + 17, False, None, 1.2345678901234567]
        record = ingress_record(value, 'receiver', 1, '2026-10-22T12:00:00+00:00')
        self.archive.append(record)
        self.archive.drain_once()
        self.assertEqual(next(iter(self.pg.rows.values()))['snapshot']['publications']['C1NI6071E']['data'], value['packet']['data'])

    def test_worker_drains_and_close_is_idempotent(self):
        self.archive.start()
        self.sink.accept(request(self.box.peek()))
        deadline = time.monotonic() + 2
        while self.archive.status()['pending'] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.archive.status()['pending'], 0)
        self.assertTrue(self.archive.close())
        self.assertTrue(self.archive.close())

    def test_camera_pixels_excluded_but_sync_memory_and_live_image_preserved(self):
        from tests.unit.test_acq_federated_video import source, video
        from tests.unit.test_acq_federated_telemetry import body
        wire = body(source(image=video()))
        original = copy.deepcopy(wire)
        record = ingress_record(wire, 'receiver', 1, '2026-10-29T07:00:00+00:00')
        self.assertEqual(wire, original)
        self.assertNotIn('data', record['wire_body']['packet']['video_frame'])
        self.assertEqual(record['wire_body']['packet']['counter_part'], wire['packet']['counter_part'])
        self.archive.append(record)
        payload = self.archive.db.execute('SELECT payload FROM pending').fetchone()[0]
        saved = json.loads(zlib.decompress(payload))
        self.assertNotIn('data', saved['wire_body']['packet']['video_frame'])
        self.assertEqual(saved['wire_body']['packet']['counter_part']['values'], [1.] * 16)
        self.assertEqual(saved['archive_image_policy'], 'metadata_only_no_pixels')
        self.assertEqual(self.archive.status()['image_policy'], 'metadata_only_no_pixels')
        self.assertEqual(telemetry_only_record(saved), saved)

    def test_postgres_strips_legacy_spool_pixels_without_changing_retry_identity(self):
        from tests.unit.test_acq_federated_video import source, video
        from tests.unit.test_acq_federated_telemetry import body
        wire = body(source(image=video()))
        record = ingress_record(wire, 'receiver', 1, '2026-10-29T07:00:00+00:00')
        # Model a row committed to the spool by an older version.
        record['wire_body'] = copy.deepcopy(wire)
        record.pop('archive_image_policy')
        record['wire_body']['packet']['video_frame']['future_payload'] = 'must not persist'
        original = copy.deepcopy(record)
        for explicit in (False, True):
            with self.subTest(explicit_identity=explicit):
                candidate = copy.deepcopy(record)
                if explicit:
                    candidate['identity_digest'] = 'd' * 64
                digest = candidate.get('identity_digest') or hashlib.sha256(encoded(candidate)).hexdigest()
                store = object.__new__(PostgresStore)
                store._known_types = {hashlib.sha256(encoded(row['lv_type'])).hexdigest()
                    for row in candidate['snapshot']['publications'].values()}
                store.Jsonb = lambda value: value
                conn, cur = MagicMock(), MagicMock()
                conn.__enter__.return_value = conn
                conn.cursor.return_value.__enter__.return_value = cur
                conn.execute.return_value.fetchall.return_value = []
                cur.execute.return_value.fetchall.return_value = [(candidate['uid'], digest)]
                store.connect = MagicMock(return_value=conn)
                store._write_records_once([candidate])
                frames = cur.executemany.call_args_list[0].args[1]
                stored = json.loads(zlib.decompress(frames[0][5]))
                image = stored['wire_body']['packet']['video_frame']
                self.assertNotIn('data', image)
                self.assertNotIn('future_payload', image)
                self.assertEqual(frames[0][4], digest)
                self.assertEqual(stored['wire_body']['packet']['counter_part'], wire['packet']['counter_part'])
        self.assertEqual(record, original)


if __name__ == '__main__':
    unittest.main()
