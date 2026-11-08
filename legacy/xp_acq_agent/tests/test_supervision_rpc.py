"""Python 3.4 tests of the original agent, its signed extension, and shared stubs."""
import copy
import os
import shutil
import tempfile
import time
import unittest
import uuid

from main import build_agent
from elyse_agent.config import load_config
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac


class RpcAgentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        config = load_config()
        config.update(mode="simulation", bind_host="127.0.0.1", command_port=0,
                      audit_path=os.path.join(self.directory, "audit.jsonl"))
        self.key = b"software-test-key-32-bytes-minimum"
        self.path = os.path.join(self.directory, "state.sqlite3")
        self.server, unused = build_agent(config, dict(state_db=self.path, time_scale=0, key=self.key))
        self.router = self.server.router
        self.runtime = self.router.supervision.runtime
        self.router.backend.initialize()

    def tearDown(self):
        self.server.server_close()
        shutil.rmtree(self.directory)

    def request(self, method="GET", path="/v1/state", payload=None):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        raw = b"" if payload is None else json_bytes(payload)
        params = dict(method=method, path=path, payload=payload, timestamp=timestamp, nonce=nonce,
                      signature=request_mac(self.key, "RPC/" + method, path, timestamp, nonce, raw))
        return dict(id="request-" + uuid.uuid4().hex, command="supervision", params=params)

    def signed(self, request):
        reply = self.router.dispatch(request)
        self.assertTrue(reply["ok"])
        result, params = reply["result"], request["params"]
        self.assertEqual(result["signature"], response_mac(self.key, "RPC/" + params["method"], params["path"],
                                                         params["nonce"], result["status"], json_bytes(result["body"])))
        return result

    def procedure(self, intent_id, procedure="modulator.heating.start"):
        state = self.runtime.read_state()
        payload = dict(intent_id=intent_id, procedure=procedure, session_id=state["session_id"],
                       expected_revision=state["revision"])
        result = self.signed(self.request("POST", "/v1/intents", payload))
        self.runtime._worker.join(5)
        return result

    def legacy(self, command, params=None):
        return self.router.dispatch(dict(id=uuid.uuid4().hex, command=command, params=params or {}))

    def test_nonce_replay_is_checked_before_legacy_cache_even_same_request_id(self):
        request = self.request()
        self.assertEqual(self.signed(request)["status"], 200)
        self.assertEqual(self.signed(request)["status"], 401)

    def test_bad_signature_and_cross_transport_signature_are_rejected(self):
        request = self.request()
        request["params"]["signature"] = "0" * 64
        self.assertEqual(self.signed(request)["status"], 401)
        request = self.request()
        params = request["params"]
        params["signature"] = request_mac(self.key, "GET", params["path"], params["timestamp"], params["nonce"], b"")
        self.assertEqual(self.signed(request)["status"], 401)

    def test_shared_state_image_and_legacy_digital_projection(self):
        self.assertEqual(self.procedure("shared")["status"], 200)
        state = self.runtime.read_state()
        snapshot = self.legacy("get_snapshot")["result"]
        self.assertEqual(snapshot["supervision"]["run"], state["run"])
        self.assertEqual(self.legacy("get_status")["result"]["supervision"]["session_id"], state["session_id"])
        image = self.signed(self.request(path="/v1/outputs"))["body"]["result"]
        self.assertEqual(snapshot["procedure_outputs"], image)
        for target, value in image["digital"].items():
            group, index = target.rsplit(".", 1)
            self.assertEqual(snapshot["digital_outputs"][group.replace("_OUT_DIO96", "_DIO96_DO")][int(index)], value)
        self.assertFalse(snapshot["hardware_writes"])

    def test_unsigned_raw_setters_are_blocked_only_when_procedure_owner_enabled(self):
        self.assertFalse(self.legacy("reset_simulated_outputs")["ok"])
        capabilities = self.legacy("get_capabilities")["result"]
        self.assertFalse(capabilities["simulated_output_mutation"])
        self.assertTrue(capabilities["named_procedure_simulation"])
        self.assertTrue(capabilities["supervision_shared_state"])

    def test_duplicate_intent_and_initialization_never_reexecute_or_reset_image(self):
        self.procedure("once")
        trace = self.runtime.trace("once")
        image = self.runtime.outputs.snapshot()
        self.legacy("initialize")
        self.assertEqual(self.procedure("once")["body"]["result"]["state"], "SUCCEEDED")
        self.assertEqual(self.runtime.trace("once"), trace)
        self.assertEqual(self.runtime.outputs.snapshot(), image)

    def test_fault_stub_stops_sequence_and_recovery_permits_new_intent(self):
        self.legacy("set_simulation_scenario", dict(name="fault"))
        self.procedure("fault")
        self.assertEqual(self.runtime.read_state()["run"]["state"], "FAILED")
        self.assertIn("Simulated equipment fault", self.runtime.read_state()["run"]["error"])
        self.assertFalse(any(self.runtime.read_state()["dps"]))
        self.legacy("set_simulation_scenario", dict(name="idle"))
        self.procedure("recovered")
        self.assertEqual(self.runtime.read_state()["run"]["state"], "SUCCEEDED")

    def test_signed_raw_route_and_malformed_intent_are_rejected(self):
        self.assertEqual(self.signed(self.request("POST", "/v1/write", {}))["status"], 404)
        self.assertEqual(self.signed(self.request("POST", "/v1/intents", {}))["status"], 400)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "IDLE")

    def test_supervision_in_discover_mode_is_rejected_before_driver_enumeration(self):
        config = load_config()
        with self.assertRaises(ValueError):
            build_agent(config, dict(state_db=self.path, time_scale=0, key=self.key))

    def test_tampered_payload_does_not_enter_procedure(self):
        state = self.runtime.read_state()
        request = self.request("POST", "/v1/intents", dict(intent_id="tampered", procedure="cooling.start",
                                                          session_id=state["session_id"], expected_revision=state["revision"]))
        request["params"]["payload"]["procedure"] = "cooling.stop"
        self.assertEqual(self.signed(request)["status"], 401)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "IDLE")

    def test_all_23_plans_have_stub_execution_without_a_physical_adapter(self):
        self.assertTrue(self.runtime.simulate_all_plans)
        count = 0
        for name, plan in sorted(self.runtime.plans.items()):
            if plan.get("kind") == "LIFECYCLE":
                continue  # Separate lifecycle tests; these are not DPS event cases.
            with self.subTest(procedure=name):
                intent_id = "stub-{0}".format(plan["legacy_event_case"])
                self.procedure(intent_id, name)
                self.assertEqual(self.runtime.read_state()["run"]["state"], "SUCCEEDED")
                succeeded = [phase for phase in self.runtime.trace(intent_id)
                             if phase["step_index"] >= 0 and phase["outcome"] == "SUCCEEDED"]
                self.assertEqual([phase["operation"] for phase in succeeded], [step["operation"] for step in plan["steps"]])
                count += len(succeeded)
        self.assertEqual(count, 158)


if __name__ == "__main__":
    unittest.main()
