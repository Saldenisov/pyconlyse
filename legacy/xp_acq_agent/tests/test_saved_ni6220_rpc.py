"""Signed supplied-return projection never accesses hardware/runtime state."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from test_saved_ni6220 import payload


class UnusableRuntime(object):
    def __getattr__(self, name):
        raise AssertionError("stateless NI6220 replay accessed runtime: " + name)


class SavedNI6220RpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b"software-test-key-32-bytes-minimum"
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, data=None):
        path = "/v1/replay/ni6220-means"
        data = payload() if data is None else data
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        return dict(method="POST", path=path, payload=data, timestamp=timestamp, nonce=nonce,
                    signature=request_mac(self.key, "RPC/POST", path, timestamp, nonce, json_bytes(data)))

    def test_signed_replay_returns_capped_data_and_independent_error(self):
        request = self.request()
        response = self.endpoint.dispatch(request)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["result"]["loop_iterations"], 10)
        self.assertEqual(response["body"]["result"]["outputs"]["read_error"], request["payload"]["read_error"])
        self.assertEqual(response["signature"], response_mac(self.key, "RPC/POST", request["path"], request["nonce"], 200, json_bytes(response["body"])))

    def test_authentication_precedes_projection_and_nonce_cannot_repeat(self):
        request = self.request()
        self.assertEqual(self.endpoint.dispatch(request)["status"], 200)
        self.assertEqual(self.endpoint.dispatch(request)["status"], 401)
        request = self.request()
        request["signature"] = "0" * 64
        self.assertEqual(self.endpoint.dispatch(request)["status"], 401)

    def test_invalid_projection_returns400_without_runtime_access(self):
        data = payload()
        data["sample_count"] = -1
        response = self.endpoint.dispatch(self.request(data))
        self.assertEqual(response["status"], 400)
        self.assertFalse(response["body"]["accepted"])
        self.assertFalse(response["body"]["execution_allowed"])


if __name__ == "__main__":
    unittest.main()
