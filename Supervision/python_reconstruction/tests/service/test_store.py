from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from supervision_reconstruction.service.store import AuditIntegrityError, IdempotencyConflict, ShadowJournal


NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
REQUEST = {"expected_revision": "fixture.v1", "requests": [{"equipment_id": "fixture", "current_a": 1.0}]}
RESULT = {"execution_allowed": False, "physical_status": "NOT_EXECUTED", "state": "PREVIEW_BLOCKED"}


class ShadowJournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "journal.sqlite3"
        self.journal = ShadowJournal(self.path)

    def tearDown(self):
        self.journal.close()
        self.temporary.cleanup()

    def append(self, key="fixture:1", request=REQUEST, result=RESULT):
        return self.journal.append(key, request, result, now=NOW)

    def test_empty_journal_has_no_hardware_queue_or_signature(self):
        status = self.journal.verify()
        self.assertEqual(status["count"], 0)
        self.assertEqual(status["head_sha"], "0" * 64)
        self.assertFalse(status["hardware_queue"])
        self.assertFalse(status["signed"])

    def test_repeated_request_returns_same_record_without_replanning(self):
        first, replayed = self.append()
        second, again = self.append(result={**RESULT, "state": "OTHER_OFFLINE_RESULT"})
        self.assertFalse(replayed)
        self.assertTrue(again)
        self.assertEqual(first, second)
        self.assertEqual(self.journal.verify()["count"], 1)

    def test_conflicting_idempotency_key_rolls_back(self):
        self.append()
        with self.assertRaises(IdempotencyConflict):
            self.append(request={**REQUEST, "expected_revision": "different"})
        self.append("fixture:2")
        self.assertEqual(self.journal.verify()["count"], 2)

    def test_restart_preserves_chain_and_history(self):
        first, _ = self.append()
        second, _ = self.append("fixture:2")
        self.assertEqual(second["previous_sha"], first["record_sha"])
        self.journal.close()
        self.journal = ShadowJournal(self.path)
        self.assertEqual(self.journal.history(), [second, first])
        replay, same = self.append()
        self.assertTrue(same)
        self.assertEqual(replay, first)

    def test_returned_objects_are_detached_from_persisted_data(self):
        record, _ = self.append()
        record["result"]["execution_allowed"] = True
        self.assertFalse(self.journal.history()[0]["result"]["execution_allowed"])

    def test_snapshot_count_head_and_history_are_coherent(self):
        for index in range(25):
            self.append(f"snapshot:{index}")
        status, records = self.journal.snapshot()
        self.assertEqual(status["count"], 25)
        self.assertEqual(len(records), 20)
        self.assertEqual(status["head_sha"], records[0]["record_sha"])
        self.assertEqual(records[0]["seq"], 25)

    def test_parallel_retry_creates_one_record(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.append(), range(16)))
        self.assertEqual(sum(not replayed for _, replayed in results), 1)
        self.assertEqual(len({r["command_id"] for r, _ in results}), 1)
        self.assertEqual(self.journal.verify()["count"], 1)

    def test_parallel_distinct_requests_have_contiguous_hash_chain(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda index: self.append(f"fixture:{index}"), range(12)))
        self.assertEqual(self.journal.verify()["count"], 12)
        self.assertEqual([r["seq"] for r in self.journal.history()], list(range(12, 0, -1)))

    def test_unsafe_result_naive_time_and_bad_history_limit_are_rejected(self):
        for result in [{**RESULT, "execution_allowed": True}, {**RESULT, "physical_status": "DISPATCHED"}]:
            with self.assertRaises(ValueError):
                self.append(result=result)
        with self.assertRaises(ValueError):
            self.journal.append("bad", REQUEST, RESULT, now=NOW.replace(tzinfo=None))
        for limit in [0, 101, True, "1"]:
            with self.assertRaises(ValueError):
                self.journal.history(limit)
        self.assertEqual(self.journal.verify()["count"], 0)

    def test_mid_chain_tampering_fails_closed_without_deleting_data(self):
        self.append()
        self.append("fixture:2")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE shadow_intents SET record_json=? WHERE seq=1", (json.dumps({"tampered": True}),))
        with self.assertRaises(AuditIntegrityError):
            self.journal.history()
        with self.assertRaises(AuditIntegrityError):
            self.append("fixture:3")
        with self.assertRaises(AuditIntegrityError):
            ShadowJournal(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM shadow_intents").fetchone()[0], 2)

    def test_foreign_database_is_not_silently_initialized(self):
        foreign = Path(self.temporary.name) / "foreign.sqlite3"
        with closing(sqlite3.connect(foreign)) as connection, connection:
            connection.execute("CREATE TABLE other_data (value TEXT)")
            connection.execute("INSERT INTO other_data VALUES ('preserve')")
        before = foreign.read_bytes()
        with self.assertRaises(AuditIntegrityError):
            ShadowJournal(foreign)
        self.assertEqual(foreign.read_bytes(), before)

    def test_empty_existing_database_is_not_recreated_as_a_new_journal(self):
        foreign = Path(self.temporary.name) / "empty.sqlite3"
        with closing(sqlite3.connect(foreign)):
            pass
        before = foreign.read_bytes()
        with self.assertRaises(AuditIntegrityError):
            ShadowJournal(foreign)
        self.assertEqual(foreign.read_bytes(), before)
