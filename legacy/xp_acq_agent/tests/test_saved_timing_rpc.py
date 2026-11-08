"""Signed replay never reads runtime, listener or output state."""
import time
import unittest
import uuid

from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac


class UnusableRuntime(object):
    def __getattr__(self, name):
        raise AssertionError("stateless timing projection accessed runtime: " + name)


class SavedTimingRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b"software-test-key-32-bytes-minimum"
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, uid="19070", inputs=None):
        path = "/v1/replay/saved-timing"
        payload = dict(source_id="APP-17", uid=uid, inputs={} if inputs is None else inputs)
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        return dict(method="POST", path=path, payload=payload, timestamp=timestamp, nonce=nonce,
                    signature=request_mac(self.key, "RPC/POST", path, timestamp, nonce, json_bytes(payload)))

    def test_signed_constant_replay_without_runtime_access(self):
        request = self.request()
        response = self.endpoint.dispatch(request)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["result"]["outputs"]["timing"]["period"], 1000)
        self.assertFalse(response["body"]["execution_allowed"])
        self.assertEqual(response["signature"], response_mac(self.key, "RPC/POST", request["path"],
                         request["nonce"], 200, json_bytes(response["body"])))

    def test_authentication_and_nonce_precede_replay(self):
        request = self.request()
        self.assertEqual(self.endpoint.dispatch(request)["status"], 200)
        self.assertEqual(self.endpoint.dispatch(request)["status"], 401)
        request = self.request()
        request["signature"] = "0" * 64
        self.assertEqual(self.endpoint.dispatch(request)["status"], 401)

    def test_late_projection_preserves_selection_even_with_error(self):
        raw = self.endpoint.dispatch(self.request())["body"]["result"]["outputs"]["timing"]
        raw.update(finished_late_i_1=True, error=dict(status=True, code=-17, source="fault"))
        response = self.endpoint.dispatch(self.request("32954", dict(timing=raw)))
        self.assertEqual(response["status"], 200)
        self.assertIs(response["body"]["result"]["outputs"]["finished_late_i_1"], True)
        self.assertFalse(response["body"]["result"]["acquired_data_bound"])

    def test_unqualified_error_adapter_never_acknowledges_execution(self):
        response = self.endpoint.dispatch(self.request("19142"))
        self.assertEqual(response["status"], 400)
        self.assertFalse(response["body"]["accepted"])
        self.assertNotIn("run", response["body"])


if __name__ == "__main__":
    unittest.main()
