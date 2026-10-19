"""Stateless signed projection: no runtime, listener or hardware is invoked."""

import time
import unittest
import uuid

from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac


class UnusableRuntime(object):
    def __getattr__(self, name):
        raise AssertionError("stateless projection accessed runtime: " + name)


class SavedXNodeRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b"software-test-key-32-bytes-minimum"
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, payload, method="POST"):
        path = "/v1/replay/saved-xnode"
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        raw = json_bytes(payload)
        return dict(
            method=method,
            path=path,
            payload=payload,
            timestamp=timestamp,
            nonce=nonce,
            signature=request_mac(
                self.key, "RPC/" + method, path, timestamp, nonce, raw
            ),
        )

    def payload(self):
        return dict(
            source_id="APP-17",
            uid="36467",
            inputs=[2, 5, 11, 17],
            error_in=dict(status=False, code=-17, source="warning"),
        )

    def test_signed_body_result_without_state_or_output_access(self):
        request = self.request(self.payload())
        response = self.endpoint.dispatch(request)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["result"]["result"], 120 / 35.0)
        self.assertFalse(response["body"]["hardware_writes"])
        self.assertEqual(
            response["signature"],
            response_mac(
                self.key,
                "RPC/POST",
                request["path"],
                request["nonce"],
                200,
                json_bytes(response["body"]),
            ),
        )

    def test_authentication_precedes_projection_and_nonce_dedup(self):
        request = self.request(self.payload())
        self.assertEqual(self.endpoint.dispatch(request)["status"], 200)
        self.assertEqual(self.endpoint.dispatch(request)["status"], 401)
        request = self.request(self.payload())
        request["signature"] = "0" * 64
        self.assertEqual(self.endpoint.dispatch(request)["status"], 401)

    def test_invalid_domain_never_acknowledges_a_procedure(self):
        payload = self.payload()
        payload["inputs"] = [0, 0, 0, 0]
        response = self.endpoint.dispatch(self.request(payload))
        self.assertEqual(response["status"], 400)
        self.assertFalse(response["body"]["accepted"])
        self.assertNotIn("run", response["body"])

    def test_error_branch_preserves_supplied_error(self):
        payload = self.payload()
        payload.update(
            inputs=None, error_in=dict(status=True, code=0, source="disconnect")
        )
        response = self.endpoint.dispatch(self.request(payload))
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["result"]["result"], 0.0)
        self.assertEqual(response["body"]["result"]["error_out"], payload["error_in"])


if __name__ == "__main__":
    unittest.main()
