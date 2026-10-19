import hashlib
import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import uuid

from elyse_agent.supervision_http import SupervisionServer
from elyse_agent.supervision_runtime import SupervisionRuntime
from elyse_agent.supervision_wire import RequestGuard, json_bytes, request_mac, response_mac


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.key = b"software-test-key-32-bytes-minimum"
        self.runtime = SupervisionRuntime(os.path.join(self.directory, "state.sqlite3"), time_scale=0)
        self.server = SupervisionServer(("127.0.0.1", 0), self.runtime, self.key)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.runtime.close()
        shutil.rmtree(self.directory)

    def request(self, method="GET", path="/v1/state", raw=b"", nonce=None, signature=None):
        timestamp, nonce = str(int(time.time())), nonce or uuid.uuid4().hex
        headers = {"X-ACQ-Timestamp": timestamp, "X-ACQ-Nonce": nonce, "Content-Type": "application/json",
                   "X-ACQ-Signature": signature or request_mac(self.key, method, path, timestamp, nonce, raw)}
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=raw, headers=headers)
            response = connection.getresponse()
            body = response.read()
            self.assertEqual(response.getheader("X-ACQ-Signature"), response_mac(self.key, method, path, nonce, response.status, body))
            return response.status, json.loads(body.decode("utf-8"))
        finally:
            connection.close()

    def test_authenticated_state_and_named_submission(self):
        status, value = self.request()
        self.assertEqual(status, 200)
        self.assertFalse(value["hardware_writes"])
        state = value["result"]
        payload = dict(intent_id="http-one", procedure="cooling.start", expected_revision=state["revision"], session_id=state["session_id"])
        status, value = self.request("POST", "/v1/intents", json_bytes(payload))
        self.assertEqual(status, 200)
        self.assertEqual(value["result"]["state"], "ACCEPTED")
        self.runtime._worker.join(5)
        status, value = self.request(path="/v1/intents/http-one")
        self.assertEqual(value["result"]["run"]["state"], "SUCCEEDED")
        status, value = self.request(path="/v1/trace/http-one")
        self.assertTrue(value["result"])

    def test_bad_signature_and_nonce_replay_are_rejected(self):
        self.assertEqual(self.request(signature="0" * 64)[0], 401)
        nonce = uuid.uuid4().hex
        self.assertEqual(self.request(nonce=nonce)[0], 200)
        self.assertEqual(self.request(nonce=nonce)[0], 401)

    def test_expired_auth_and_tampered_body_path_are_rejected(self):
        guard = RequestGuard(self.key, clock=lambda: 100)
        signature = request_mac(self.key, "GET", "/v1/state", "1", "0" * 32, b"")
        with self.assertRaises(ValueError):
            guard.verify("GET", "/v1/state", "1", "0" * 32, signature, b"")
        signature = request_mac(self.key, "POST", "/v1/intents", "100", "0" * 32, b"original")
        with self.assertRaises(ValueError):
            guard.verify("POST", "/v1/intents", "100", "0" * 32, signature, b"changed")

    def test_raw_io_duplicate_keys_nonfinite_and_bad_revision_do_not_mutate(self):
        state = self.runtime.read_state()
        payload = dict(intent_id="invalid", procedure="cooling.start", expected_revision="old", session_id=state["session_id"])
        status, value = self.request("POST", "/v1/intents", json_bytes(payload))
        self.assertEqual(status, 409)
        self.assertFalse(value["accepted"])
        for raw in (b'{"intent_id":"x","intent_id":"y"}', b'{"value":NaN}', b'{"value":1e999}', b'[]'):
            self.assertEqual(self.request("POST", "/v1/intents", raw)[0], 400)
        self.assertEqual(self.request("POST", "/v1/write", b'{}')[0], 404)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "IDLE")

    def test_keys_and_bind_interfaces_fail_closed(self):
        with self.assertRaises(ValueError):
            RequestGuard(b"short")
        with self.assertRaises(ValueError):
            SupervisionServer(("0.0.0.0", 0), self.runtime, self.key)


if __name__ == "__main__":
    unittest.main()
