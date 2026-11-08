from datetime import datetime, timezone
from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
import unittest

from supervision_reconstruction.service.application import OfflineSupervision
from supervision_reconstruction.service.http import OfflineHTTPServer, strict_json
from supervision_reconstruction.service.store import ShadowJournal


class OfflineHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "journal.sqlite3"
        self.journal = ShadowJournal(self.path)
        self.root = Path(__file__).resolve().parents[3]
        self.app = OfflineSupervision(self.journal, supervision_root=self.root)
        self.server = OfflineHTTPServer(("127.0.0.1", 0), self.app, self.root / "web_prototype")
        self.worker = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.journal.close()
        self.temporary.cleanup()

    def request(self, method="GET", path="/api/supervision/snapshot", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body=body,
                headers={"Host": f"127.0.0.1:{self.server.server_port}", **(headers or {})})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def body(self, key="http:1", current=1):
        return {"idempotency_key": key, "expected_revision": self.app.registry.revision,
                "requests": [{"equipment_id": "H1", "current_a": current}]}

    def post(self, body=None, headers=None):
        return self.request("POST", "/api/shadow/current-preview", json.dumps(body or self.body()),
                            {"Content-Type": "application/json", **(headers or {})})

    def test_only_loopback_binding_is_possible(self):
        for host in ["0.0.0.0", "10.20.30.2", "localhost", "::1"]:
            with self.assertRaises(ValueError):
                OfflineHTTPServer((host, 0), self.app, self.root / "web_prototype")

    def test_snapshot_is_display_only_with_explicit_coverage_and_source_identity(self):
        status, headers, raw = self.request()
        snapshot = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["mode"], "OFFLINE_SHADOW")
        self.assertFalse(snapshot["execution_allowed"])
        self.assertEqual(len(snapshot["registry"]["entries"]), 21)
        self.assertEqual(snapshot["coverage"]["top_level_events"], 34)
        self.assertEqual(snapshot["coverage"]["timed_frames"], 9)
        self.assertEqual(snapshot["coverage"]["catalog_vi_count"], 126)
        self.assertEqual(snapshot["coverage"]["application_vi_count"], 39)
        self.assertEqual(snapshot["coverage"]["verified_replacement_count"], 0)
        self.assertFalse(snapshot["coverage"]["complete_vi_replacement"])
        self.assertIn("Password-protected Error Code Database.vi", snapshot["coverage"]["blockers"])
        self.assertFalse(snapshot["source_integrity"]["source_modified_by_service"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_static_api_capability_is_injected_into_response_only(self):
        status, _, raw = self.request(path="/")
        self.assertEqual(status, 200)
        self.assertIn(b'data-offline-api="true"', raw)
        self.assertNotIn(b'data-offline-api="true"', (self.root / "web_prototype/index.html").read_bytes())

    def test_preview_history_retry_and_conflict_have_no_physical_success(self):
        status, _, raw = self.post()
        self.assertEqual(status, 200)
        first = json.loads(raw)
        self.assertFalse(first["replayed"])
        self.assertFalse(first["record"]["result"]["execution_allowed"])
        self.assertEqual(first["record"]["result"]["physical_status"], "NOT_EXECUTED")
        retry = json.loads(self.post()[2])
        self.assertTrue(retry["replayed"])
        self.assertEqual(first["record"], retry["record"])
        self.assertEqual(self.post(self.body(current=2))[0], 409)
        history = json.loads(self.request(path="/api/shadow/history")[2])
        self.assertEqual(len(history["records"]), 1)

    def test_cross_origin_and_dns_rebinding_requests_are_denied(self):
        for headers in [{"Origin": "http://evil.example"}, {"Origin": "null"},
                        {"Sec-Fetch-Site": "cross-site"}, {"Host": "evil.example"}]:
            self.assertEqual(self.post(headers=headers)[0], 403)
        self.assertEqual(self.request(headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.journal.verify()["count"], 0)

    def test_same_origin_browser_preview_is_allowed(self):
        self.assertEqual(self.post(headers={"Origin": f"http://127.0.0.1:{self.server.server_port}",
                                           "Sec-Fetch-Site": "same-origin"})[0], 200)

    def test_invalid_bodies_media_types_and_duplicate_json_are_rejected(self):
        for raw in ['{"idempotency_key":"a","idempotency_key":"b"}',
                    '{"current":NaN}', '{"current":Infinity}', '[]', '{}', 'null', '{broken']:
            self.assertEqual(self.request("POST", "/api/shadow/current-preview", raw,
                                          {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/shadow/current-preview", "{}",
                                      {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/shadow/current-preview", "x" * 16385,
                                      {"Content-Type": "application/json"})[0], 413)
        self.assertEqual(self.journal.verify()["count"], 0)

    def test_no_execution_raw_write_or_source_download_endpoint_exists(self):
        for path in ["/api/execute", "/api/tango/write", "/api/daqmx/write", "/../source/file",
                     "/%2e%2e/source/file", "/api/supervision/snapshot?execute=true",
                     "http://evil.example/api/supervision/snapshot"]:
            self.assertEqual(self.request(path=path)[0], 404)
        self.assertEqual(self.request("POST", "/api/execute", "{}")[0], 404)
        for method in ["PUT", "DELETE", "PATCH", "OPTIONS"]:
            self.assertEqual(self.request(method, "/api/shadow/current-preview")[0], 405)

    def test_tampered_journal_returns_unavailable_without_overwrite(self):
        self.post()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE shadow_intents SET record_sha='tampered'")
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.post(self.body(key="http:2"))[0], 503)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM shadow_intents").fetchone()[0], 1)

    def test_closed_journal_is_service_unavailable_not_execution_success(self):
        self.journal.close()
        self.assertEqual(self.post()[0], 503)

    def test_nested_duplicate_keys_and_nonfinite_json_fail_before_parsing(self):
        for raw in [b'{"outer":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":Infinity}']:
            with self.assertRaises(ValueError):
                strict_json(raw)

    def test_snapshot_requires_explicit_timezone(self):
        with self.assertRaises(ValueError):
            self.app.snapshot(now=datetime(2026, 10, 3))


if __name__ == "__main__":
    unittest.main()
