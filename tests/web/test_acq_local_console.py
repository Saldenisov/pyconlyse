"""Loopback context and one-shot approvals with provisioned temporary secrets."""
import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest

from web.backend.acq_local_console import (
    DEFAULT_ORIGIN, SUBJECT, LocalConsoleError, consume_approval, is_local_context,
    issue_approval, local_subject,
)


TABLE = "acq_local_console_approvals"


def request(remote="127.0.0.1", host="127.0.0.1:5000", origin=DEFAULT_ORIGIN, **headers):
    headers.update(Host=host)
    if origin is not None:
        headers["Origin"] = origin
    return SimpleNamespace(remote_addr=remote, headers=headers)


def intent(**changes):
    value = dict(operation="modulator.general.start", value=None, session_id="a" * 32,
                 expected_revision=7, device="elyse/acquisition/control", method="POST",
                 route="acquisition.command.modulator.general.start")
    value.update(changes)
    return value


class LocalConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.key = root / "provisioned.key"
        self.key.write_bytes(b"temporary-test-secret-000000000000000000000000")
        self.db = root / "approvals.sqlite3"
        self.settings = dict(ACQ_LOCAL_CONSOLE_ENABLED=True,
                             ACQ_LOCAL_CONSOLE_KEY_FILE=str(self.key),
                             ACQ_LOCAL_CONSOLE_DB_FILE=str(self.db))
        self.now = 1000.0

    def clock(self):
        return self.now

    def issue(self, value=None, **settings):
        return issue_approval(value or intent(), SUBJECT, dict(self.settings, **settings), self.clock)

    def consume(self, nonce, value=None, subject=SUBJECT):
        return consume_approval(value or intent(), subject, nonce, self.settings, self.clock)

    def test_fixed_subject_requires_explicit_mode_auth_opt_out_and_literal_loopback(self):
        self.assertEqual(local_subject(request(), self.settings, False), SUBJECT)
        self.assertEqual(local_subject(request(remote="::1"), self.settings, False), SUBJECT)
        for enabled in (False, None, 1, "true"):
            self.assertIsNone(local_subject(request(), dict(self.settings, ACQ_LOCAL_CONSOLE_ENABLED=enabled), False))
        self.assertIsNone(local_subject(request(), {}, False))
        for required in (True, None, 0, "false"):
            self.assertIsNone(local_subject(request(), self.settings, required))
        for remote in ("192.0.2.1", "localhost", "::ffff:127.0.0.1", "127.0.0.2", None):
            self.assertIsNone(local_subject(request(remote=remote), self.settings, False))

    def test_host_and_origin_must_match_exact_configured_origin(self):
        for host in (None, "localhost:5000", "127.0.0.1:5001", "attacker.invalid", "127.0.0.1:5000.attacker.invalid"):
            with self.assertRaises(LocalConsoleError) as raised:
                local_subject(request(host=host), self.settings, False)
            self.assertEqual(raised.exception.status_code, 403)
        for origin in (None, "null", "http://attacker.invalid", DEFAULT_ORIGIN + "/", "https://127.0.0.1:5000"):
            with self.assertRaises(LocalConsoleError) as raised:
                local_subject(request(origin=origin), self.settings, False)
            self.assertEqual(raised.exception.status_code, 403)

    def test_forwarded_headers_and_browser_identity_never_establish_locality(self):
        headers = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1",
                   "X-Forwarded-Host": "127.0.0.1:5000", "X-User": "local-console"}
        self.assertIsNone(local_subject(request(remote="192.0.2.1", **headers), self.settings, False))
        with self.assertRaises(LocalConsoleError):
            local_subject(request(host="foreign.invalid", **headers), self.settings, False)
        self.assertEqual(local_subject(request(**{"X-Forwarded-For": "192.0.2.1", "X-User": "admin"}),
                                       self.settings, False), SUBJECT)

    def test_read_only_context_can_omit_origin_but_never_accepts_foreign_origin(self):
        self.assertTrue(is_local_context(request(origin=None), self.settings, False))
        self.assertEqual(local_subject(request(origin=None), self.settings, False, require_origin=False), SUBJECT)
        with self.assertRaises(LocalConsoleError):
            is_local_context(request(origin="https://attacker.invalid"), self.settings, False)

    def test_configured_origin_is_explicit_loopback_url_including_ipv6(self):
        settings = dict(self.settings, ACQ_LOCAL_CONSOLE_ORIGIN="http://[::1]:5000")
        self.assertEqual(local_subject(request(remote="::1", host="[::1]:5000", origin="http://[::1]:5000"),
                                       settings, False), SUBJECT)
        for origin in ("http://localhost:5000", "https://example.com", "http://127.0.0.1:5000/",
                       "http://user@127.0.0.1:5000", "http://127.0.0.1:5000?x=1",
                       "http://127.0.0.1:65536", "http://127.0.0.1:05000", "/relative"):
            with self.assertRaises(LocalConsoleError):
                local_subject(request(), dict(self.settings, ACQ_LOCAL_CONSOLE_ORIGIN=origin), False)

    def test_valid_approval_is_64_hex_stores_only_nonce_hash_and_is_one_shot(self):
        nonce = self.issue()
        self.assertEqual(len(nonce), 64)
        self.assertEqual(int(nonce, 16).bit_length() <= 256, True)
        with closing(sqlite3.connect(str(self.db))) as db, db:
            row = db.execute("SELECT nonce_hash,subject,intent,used FROM " + TABLE).fetchone()
        self.assertEqual(row[0], hashlib.sha256(nonce.encode("ascii")).hexdigest())
        self.assertNotIn(nonce, str(row))
        self.assertNotIn(self.key.read_bytes().decode("ascii"), str(row))
        self.assertEqual(row[1], SUBJECT)
        self.assertEqual(row[3], 0)
        self.assertIs(self.consume(nonce), True)
        with self.assertRaises(LocalConsoleError) as raised:
            self.consume(nonce)
        self.assertEqual(raised.exception.status_code, 409)

    def test_every_intent_field_and_subject_is_bound_without_consuming_mismatched_approval(self):
        nonce = self.issue()
        changes = dict(operation="chauffage.start", value=1.0, session_id="b" * 32,
                       expected_revision=8, device="another/device", method="DELETE", route="another.route")
        for field, value in changes.items():
            with self.assertRaises(LocalConsoleError):
                self.consume(nonce, intent(**{field: value}))
        with self.assertRaises(LocalConsoleError):
            self.consume(nonce, subject="browser-chosen-identity")
        self.assertIs(self.consume(nonce), True)

    def test_canonical_json_is_order_independent_and_preserves_json_types(self):
        value = intent(value={"counter": 0, "delay_us": 1.25, "width_us": 3.5})
        nonce = self.issue(value)
        reordered = dict(reversed(list(value.items())))
        reordered["value"] = dict(reversed(list(value["value"].items())))
        self.assertIs(self.consume(nonce, reordered), True)
        nonce = self.issue(intent(value=True))
        with self.assertRaises(LocalConsoleError):
            self.consume(nonce, intent(value=1))

    def test_expiry_and_clock_rollback_fail_closed(self):
        nonce = self.issue()
        self.now += 30
        with self.assertRaises(LocalConsoleError):
            self.consume(nonce)
        self.now = 999.0
        with self.assertRaises(LocalConsoleError):
            self.consume(nonce)
        self.now = 1029.999
        self.assertTrue(self.consume(nonce))

    def test_ttl_is_positive_finite_and_at_most_sixty_seconds(self):
        for ttl in (0, -1, 61, True, "30", float("nan"), float("inf")):
            with self.assertRaises(LocalConsoleError):
                self.issue(ACQ_LOCAL_CONSOLE_TTL_SECONDS=ttl)
        self.assertFalse(self.db.exists())
        nonce = self.issue(ACQ_LOCAL_CONSOLE_TTL_SECONDS=60)
        self.now += 59.999
        self.assertTrue(self.consume(nonce))

    def test_tampered_row_or_mac_is_never_accepted(self):
        for field, value in (("subject", "other"), ("intent", "{}"), ("issued_at", 900.0),
                             ("expires_at", 9000.0), ("used", 1), ("consumed_at", 1001.), ("mac", "0" * 64)):
            nonce = self.issue()
            nonce_hash = hashlib.sha256(nonce.encode("ascii")).hexdigest()
            with closing(sqlite3.connect(str(self.db))) as db, db:
                db.execute("UPDATE " + TABLE + " SET " + field + "=? WHERE nonce_hash=?", (value, nonce_hash))
            with self.assertRaises(LocalConsoleError):
                self.consume(nonce)

    def test_used_bit_reset_does_not_restore_a_consumed_approval(self):
        nonce = self.issue()
        self.consume(nonce)
        with closing(sqlite3.connect(str(self.db))) as db, db:
            db.execute("UPDATE " + TABLE + " SET used=0,consumed_at=NULL")
        with self.assertRaises(LocalConsoleError):
            self.consume(nonce)

    def test_simultaneous_consumers_have_exactly_one_success(self):
        nonce, barrier, results = self.issue(), threading.Barrier(2), []

        def consume():
            barrier.wait(3)
            try:
                results.append(self.consume(nonce))
            except LocalConsoleError as error:
                results.append(error.status_code)

        threads = [threading.Thread(target=consume) for _index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(4)
            self.assertFalse(thread.is_alive())
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(409), 1)

    def test_no_automatic_key_generation_or_configuration_fallback(self):
        self.key.unlink()
        with self.assertRaises(LocalConsoleError) as raised:
            self.issue()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertFalse(self.key.exists())
        self.assertFalse(self.db.exists())
        self.key.write_bytes(b"too short")
        with self.assertRaises(LocalConsoleError):
            self.issue()
        for changed in (dict(ACQ_LOCAL_CONSOLE_ENABLED=False), dict(ACQ_LOCAL_CONSOLE_DB_FILE="relative.sqlite3")):
            with self.assertRaises(LocalConsoleError):
                issue_approval(intent(), SUBJECT, dict(self.settings, **changed), self.clock)

    def test_intent_rejects_extra_identity_and_correlation_fields_and_nonfinite_values(self):
        for value in (dict(intent(), command_id="c" * 32), dict(intent(), subject=SUBJECT),
                      intent(expected_revision=True), intent(value=float("nan")),
                      intent(value={1: "ambiguous key"}), intent(value=(1, 2))):
            with self.assertRaises(LocalConsoleError) as raised:
                self.issue(value)
            self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse(self.db.exists())

    def test_nonce_required_and_invalid_nonce_rejected_without_disclosing_secret(self):
        for nonce in (None, "", "A" * 64, "a" * 63, b"a" * 64):
            with self.assertRaises(LocalConsoleError) as raised:
                self.consume(nonce)
            self.assertNotIn(self.key.read_bytes().decode("ascii"), str(raised.exception))


if __name__ == "__main__":
    unittest.main()
