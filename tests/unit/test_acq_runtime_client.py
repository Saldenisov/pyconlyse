"""Authenticated HTTP decoder tests; only one fake loopback server is used."""
import copy
import json
import threading
import unittest
from unittest.mock import patch

from DeviceServers.control.elyse_acq.runtime_client import (
    MAX_RUNTIME_BYTES, _NoRedirect, read_runtime, strict_runtime_json,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_http import (
    RuntimeHTTPServer, request_signature, response_signature,
)
from tests.unit.test_acq_runtime_contract import runtime_snapshot


KEY = b"synthetic-client-shared-key-at-least32"


class Response:
    def __init__(self, body, signature):
        self.body = body
        self.headers = {"X-ACQ-Response-Signature": signature}
        self.read_sizes = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]


class RuntimeClientTests(unittest.TestCase):
    def fake_read(self, body, signature=None):
        class Opener:
            requests = []
            responses = []
            def open(self, request, timeout):
                self.requests.append((request, timeout))
                nonce = request.get_header("X-acq-nonce")
                result = Response(body, response_signature(KEY, nonce, body)
                                  if signature is None else signature)
                self.responses.append(result)
                return result
        return Opener()

    def test_nonce_signature_fixed_get_no_proxy_or_redirect_and_bounded_read(self):
        body = json.dumps(runtime_snapshot()).encode("utf-8")
        opener = self.fake_read(body)
        with patch("urllib.request.build_opener", return_value=opener) as build:
            first = read_runtime(KEY)
            second = read_runtime(KEY)
        self.assertEqual(first, second)
        nonces = []
        for request, timeout in opener.requests:
            nonce = request.get_header("X-acq-nonce")
            nonces.append(nonce)
            self.assertEqual(request.full_url, "http://10.20.30.10:8771/snapshot")
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(timeout, 2.0)
            self.assertEqual(request.get_header("X-acq-signature"), request_signature(KEY, "/snapshot", nonce))
        self.assertNotEqual(nonces[0], nonces[1])
        self.assertEqual(opener.responses[0].read_sizes, [MAX_RUNTIME_BYTES + 1])
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], _NoRedirect)

    def test_response_hmac_checked_before_json_or_cached_values(self):
        with patch("urllib.request.build_opener", return_value=self.fake_read(b"not JSON", signature="bad")):
            with self.assertRaisesRegex(ValueError, "response signature"):
                read_runtime(KEY)

    def test_complete_slow_total_response_rejected_even_when_signed_and_socket_active(self):
        body = json.dumps(runtime_snapshot()).encode("utf-8")
        with patch("urllib.request.build_opener", return_value=self.fake_read(body)):
            with patch("DeviceServers.control.elyse_acq.runtime_client.time.monotonic",
                       side_effect=(100.0, 102.001)):
                with self.assertRaisesRegex(TimeoutError, "total acceptance deadline"):
                    read_runtime(KEY, timeout=2.0)

    def test_oversized_response_rejected_before_signature_decode(self):
        with patch("urllib.request.build_opener", return_value=self.fake_read(b" " * (MAX_RUNTIME_BYTES + 1))):
            with self.assertRaisesRegex(ValueError, "exceeds limit"):
                read_runtime(KEY)

    def test_invalid_endpoint_key_timeout_rejected_before_http(self):
        cases = [dict(host="example.org"), dict(host="10.20.30.2"), dict(port=True),
                 dict(port=0), dict(port=65536), dict(timeout=0), dict(timeout=6),
                 dict(timeout=True), dict(timeout=float("nan")), dict(key=b"short")]
        for changes in cases:
            options = dict(key=KEY)
            options.update(changes)
            with patch("urllib.request.build_opener") as build:
                with self.assertRaises(ValueError):
                    read_runtime(**options)
                build.assert_not_called()

    def test_redirect_handler_always_refuses(self):
        with self.assertRaises(ValueError):
            _NoRedirect().redirect_request(None, None, 302, "redirect", {}, "http://other")

    def test_strict_json_rejects_duplicates_nonfinite_overflow_arrays_and_depth(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}',
                     b'[]', b'{"x":' + b'[' * 50 + b'0' + b']' * 50 + b'}'):
            with self.subTest(body=body[:40]):
                with self.assertRaises(ValueError):
                    strict_runtime_json(body)

    def test_authenticated_response_safety_contract_cannot_enable_mutations(self):
        for change in (dict(storage_mode="sqlite"), dict(auto_initialize=True),
                       dict(remote_initialization_enabled=True), dict(remote_setpoints_enabled=True)):
            value = runtime_snapshot()
            value.update(change)
            with patch("urllib.request.build_opener", return_value=self.fake_read(json.dumps(value).encode())):
                with self.assertRaisesRegex(ValueError, "safety contract"):
                    read_runtime(KEY)

    def test_real_loopback_signed_roundtrip_without_ni_or_tango(self):
        value = runtime_snapshot(state="IDLE", latest=None, stale=True, age_seconds=None)
        class FakeRuntime:
            def snapshot(self):
                return copy.deepcopy(value)
        server = RuntimeHTTPServer(("127.0.0.1", 0), FakeRuntime(), KEY)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertEqual(read_runtime(KEY, host="127.0.0.1", port=server.server_port), value)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
