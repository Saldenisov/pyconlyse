# -*- coding: utf-8 -*-
"""Actual Python 3.4 named setpoints, durable idempotency and native arithmetic."""
import json
import threading
import unittest

import test_supervision_rpc as helpers
from elyse_agent.supervision_runtime import SupervisionRuntime, Rejected
from elyse_agent.supervision_setpoints import rules, adjusted


class SetpointAgentTests(unittest.TestCase):
    setUp = helpers.RpcAgentTests.setUp
    tearDown = helpers.RpcAgentTests.tearDown
    request = helpers.RpcAgentTests.request
    signed = helpers.RpcAgentTests.signed
    legacy = helpers.RpcAgentTests.legacy

    def payload(self, intent_id="arrow", page="Page Fluides", control="> Canon", base_value=20):
        state = self.runtime.read_state()
        return dict(intent_id=intent_id, page=page, control=control, base_value=base_value,
                    expected_revision=state["revision"], session_id=state["session_id"])

    def submit(self, payload):
        return self.signed(self.request("POST", "/v1/setpoints", payload))

    def test_all_twenty_rules_boundaries_and_persisted_targets(self):
        self.assertEqual(len(rules()), 20)
        for index, rule in enumerate(rules()):
            for sample_index, sample in enumerate((-1e4, 0, 10, 1e4)):
                # A fresh explicit simulated base; no invented readback/zero.
                with self.runtime.outputs._lock:
                    self.runtime.outputs.image["analog"].pop(rule["target"], None)
                payload = self.payload("rule-{0}-{1}".format(index, sample_index), rule["page"], rule["control"], sample)
                reply = self.submit(payload)
                self.assertEqual(reply["status"], 200)
                self.assertEqual(reply["body"]["result"]["state"], "SUCCEEDED")
                value = self.runtime.read_setpoints()["values"][rule["target"]]
                self.assertEqual(value, adjusted(rule, sample))
                detail = self.runtime.trace(payload["intent_id"])[-1]["detail"]
                self.assertEqual(detail["value"], value)
                self.assertTrue(detail["seeded"])
        self.assertFalse(any(self.runtime.read_state()["dps"]))

    def test_duplicate_after_new_revision_never_adds_twice(self):
        payload = self.payload()
        self.submit(payload)
        image, trace = self.runtime.outputs.snapshot(), self.runtime.trace("arrow")
        replay = dict(payload, expected_revision="old", session_id="previous-session")
        self.assertEqual(self.submit(replay)["body"]["result"]["state"], "SUCCEEDED")
        self.assertEqual(self.runtime.outputs.snapshot(), image)
        self.assertEqual(self.runtime.trace("arrow"), trace)
        self.assertEqual(image["analog"]["C8NI6703.01"], 20.1)
        self.assertEqual(self.submit(dict(payload, base_value=21))["status"], 409)

    def test_stale_revision_session_and_base_are_definitely_rejected(self):
        payload = self.payload()
        self.submit(payload)
        for changed in (dict(intent_id="stale", expected_revision=payload["expected_revision"]),
                        dict(intent_id="old-session", session_id="old"), dict(intent_id="old-value", base_value=20)):
            request = self.payload(base_value=20.1)
            request.update(changed)
            self.assertEqual(self.submit(request)["status"], 409)
        self.assertEqual(self.runtime.read_setpoints()["values"]["C8NI6703.01"], 20.1)

    def test_all_29_dps_bits_do_not_gate_arrows_or_get_cleared(self):
        for index in range(29):
            dps = [False] * 29
            dps[index] = True
            with self.runtime._db() as db:
                self.runtime._put(db, "dps", json.dumps(dps))
            current = self.runtime.read_setpoints()["values"]["C8NI6703.01"]
            reply = self.submit(self.payload("busy-{0}".format(index), base_value=20 if current is None else current))
            self.assertEqual(reply["body"]["result"]["state"], "SUCCEEDED")
            self.assertEqual(self.runtime.read_state()["dps"], dps)

    def test_arrow_during_procedure_wait_preserves_active_run_and_own_dps(self):
        entered, release = threading.Event(), threading.Event()
        original = self.runtime.step_hook
        def hold(index, step):
            original(index, step)
            if step["operation"] != "setpoint":
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Test wait expired")
        self.runtime.step_hook = hold
        state = self.runtime.read_state()
        self.runtime.submit_procedure("procedure", "modulator.heating.start", state["revision"], state["session_id"])
        try:
            self.assertTrue(entered.wait(2))
            previous = self.runtime.read_state()
            self.assertEqual(self.submit(self.payload())["body"]["result"]["state"], "SUCCEEDED")
            current = self.runtime.read_state()
            self.assertEqual(current["run"], previous["run"])
            self.assertEqual(current["dps"], previous["dps"])
        finally:
            release.set()
            self.runtime._worker.join(5)

    def test_fault_records_failed_intent_without_initializing_value_then_recovers(self):
        self.legacy("set_simulation_scenario", dict(name="fault"))
        reply = self.submit(self.payload("fault"))
        self.assertEqual(reply["body"]["result"]["state"], "FAILED")
        self.assertIsNone(self.runtime.read_setpoints()["values"]["C8NI6703.01"])
        self.assertIn("Simulated equipment fault", self.runtime.trace("fault")[-1]["detail"]["error"])
        self.legacy("set_simulation_scenario", dict(name="idle"))
        self.assertEqual(self.submit(self.payload("recovered"))["body"]["result"]["state"], "SUCCEEDED")

    def test_invalid_values_names_and_raw_fields_are_rejected_before_admission(self):
        for number in (True, "20", None):
            self.assertEqual(self.submit(self.payload(base_value=number))["status"], 400)
        self.assertEqual(self.submit(self.payload(control="raw pin"))["status"], 409)
        for key in ("target", "delta", "native_limits", "hardware_writes"):
            request = self.payload()
            request[key] = 1
            self.assertEqual(self.submit(request)["status"], 400)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "IDLE")
        self.assertIsNone(self.runtime.read_setpoints()["values"]["C8NI6703.01"])

    def test_restart_restores_values_and_receipt_original_session(self):
        payload = self.payload()
        self.submit(payload)
        old = self.runtime.read_intent("arrow")
        self.server.server_close()
        restored = SupervisionRuntime(self.path, time_scale=0, simulate_setpoints=True)
        try:
            self.assertEqual(restored.read_intent("arrow"), old)
            self.assertEqual(restored.read_setpoints()["values"]["C8NI6703.01"], 20.1)
            self.assertEqual(restored.submit_setpoint(**payload)["state"], "SUCCEEDED")
        finally:
            restored.close()

    def test_unresolved_accepted_setpoint_survives_restart_and_blocks_both_lanes(self):
        payload = self.payload()
        self.submit(payload)
        with self.runtime._db() as db:
            db.execute("UPDATE setpoint_intents SET state='ACCEPTED' WHERE intent_id='arrow'")
        self.server.server_close()
        restored = SupervisionRuntime(self.path, time_scale=0, simulate_setpoints=True)
        try:
            state = restored.read_state()
            self.assertEqual(state["run"]["state"], "UNKNOWN")
            self.assertEqual(restored.submit_setpoint(**payload)["state"], "UNKNOWN")
            with self.assertRaises(Rejected):
                restored.submit_setpoint("new", "Page Fluides", "> Canon", 20.1, state["revision"], state["session_id"])
            with self.assertRaises(Rejected):
                restored.submit_procedure("new-procedure", "cooling.start", state["revision"], state["session_id"])
            self.assertEqual(restored.read_setpoints()["values"]["C8NI6703.01"], 20.1)
        finally:
            restored.close()

    def test_intent_id_cannot_cross_procedure_and_setpoint_lanes(self):
        self.submit(self.payload())
        state = self.runtime.read_state()
        with self.assertRaises(Rejected):
            self.runtime.submit_procedure("arrow", "cooling.start", state["revision"], state["session_id"])
        self.runtime.submit_procedure("procedure", "modulator.heating.start", state["revision"], state["session_id"])
        self.runtime._worker.join(5)
        self.assertEqual(self.submit(self.payload("procedure"))["status"], 409)
