"""Driver-free tests also runnable with the real Python 3.4 interpreter."""
import copy
import threading
import unittest
import json
import hmac
import urllib.request
import urllib.error
from uuid import uuid4

from legacy.xp_acq_control.elyse_agent.acquisition_remote import CommandBroker, OPERATIONS, validate_request
from legacy.xp_acq_control.elyse_agent.acquisition_remote import ControlHTTPServer, command_signature
from legacy.xp_acq_control.elyse_agent.acquisition_http import request_signature, response_signature
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities
from legacy.xp_acq_control.elyse_agent.cooling_startup import wait_for_cooling
from legacy.xp_acq_control.elyse_agent.acquisition_procedures import ProcedureCancelled
from legacy.xp_acq_control.elyse_agent.acquisition_stage_model import load_model
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend, control_identity


def normal_sample():
    sample = dict(source="python_daqmx_acquisition", simulated=False, banks={
        "C3_DIO96_DI": dict(values=[False] * 56),
        "C4_DIO96_DI": dict(values=[False] * 64)})
    for index in (1, 4, 7, 10):
        sample["banks"]["C3_DIO96_DI"]["values"][index] = True
    return sample


def ready_state():
    return dict(state="RUNNING", stale=False, age_seconds=.1, error="", resource_count=1,
                remote_setpoints_enabled=True, general_stop_required=False,
                recovery=dict(required=False, protection_active=True), latest=normal_sample(),
                stage_execution=dict(commissioned=True, ht_commissioned=True, focal_commissioned=True,
                                     counter_commissioned=True, ht_voltage_commissioned=True),
                full_stop_commissioned=True, general_cooling_ready=True, cooling_permit_current=True)


class Clock(object):
    def __init__(self):
        self.now, self.cancelled = 0., False
    def __call__(self):
        return self.now
    def wait(self, seconds):
        self.now += seconds
        return self.cancelled
    def is_set(self):
        return self.cancelled


class AdmissionRuntime(object):
    def __init__(self):
        self._lock = threading.RLock()
        self._identity = dict(session_id="a" * 32)
        self._state, self._pending, self._operation = "RUNNING", None, None
        self.calls = []
    def fenced_local_request(self, session, revision, callback):
        if session != "a" * 32 or revision != 7:
            raise RuntimeError("fence")
        callback()
    def dispatch_remote(self, operation, value):
        self.calls.append((operation, value))
        self._pending = "owned"


def command(operation="chauffage.start"):
    return dict(command_id="b" * 32, session_id="a" * 32, expected_revision=7,
                operation=operation, operator_confirmed=True, value=None)


class PolicyTests(unittest.TestCase):
    def test_all_named_operations_and_no_remote_lifecycle(self):
        caps = command_capabilities(ready_state())
        self.assertEqual(set(caps), set(OPERATIONS))
        self.assertFalse(caps["cooling.stop"]["enabled"])
        self.assertNotIn("acquisition.initialize", OPERATIONS)
        self.assertTrue(caps["modulator.general.start"]["enabled"])
        self.assertEqual(len(load_model().plan("cooling.start")), 12)
        self.assertEqual(control_identity()["runtime_protocol_version"], 2)

    def test_no_start_without_cooling_but_recovery_and_general_available(self):
        value = ready_state()
        value.update(general_cooling_ready=False, cooling_permit_current=False)
        caps = command_capabilities(value)
        self.assertTrue(caps["modulator.general.start"]["enabled"])
        self.assertTrue(caps["cooling.start"]["enabled"])
        for operation in ("chauffage.start", "prema.start", "focales.start", "relays_ht.start", "alimentation_ht.start"):
            self.assertFalse(caps[operation]["enabled"], operation)

    def test_no_repeat_general_or_start_with_missing_commissioning(self):
        value = ready_state()
        value["general_stop_required"] = True
        self.assertFalse(command_capabilities(value)["modulator.general.start"]["enabled"])
        for field in ("full_stop_commissioned", "remote_setpoints_enabled"):
            value = ready_state(); value[field] = False
            self.assertFalse(command_capabilities(value)["modulator.general.start"]["enabled"])
        for state in ("IDLE", "STOPPED", "FAULT", "RECOVERY_REQUIRED", "EXECUTING"):
            value = ready_state(); value["state"] = state
            self.assertFalse(command_capabilities(value)["chauffage.start"]["enabled"])

    def test_stale_simulated_unknown_and_recovery_never_authorize_start(self):
        for change in (dict(age_seconds=2), dict(age_seconds=float("nan")), dict(stale=True),
                       dict(error="failed"), dict(resource_count=0),
                       dict(recovery=dict(required=True, protection_active=True)),
                       dict(latest=dict(source="copied_labview_telemetry", simulated=False)),
                       dict(latest=dict(source="python_daqmx_acquisition", simulated=True))):
            value = ready_state(); value.update(change)
            self.assertFalse(command_capabilities(value)["chauffage.start"]["enabled"])

    def test_general_stop_remains_available_during_input_fault(self):
        value = ready_state(); value.update(state="FAULT", error="read failed", stale=True)
        self.assertTrue(command_capabilities(value)["modulator.general.stop"]["enabled"])
        value.update(state="EXECUTING", current_operation="modulator.general.start")
        self.assertTrue(command_capabilities(value)["modulator.general.stop"]["enabled"])
        value["current_operation"] = "modulator.general.stop"
        self.assertFalse(command_capabilities(value)["modulator.general.stop"]["enabled"])

    def test_exact_protocol_rejects_raw_outputs_and_unconfirmed(self):
        for change in (dict(operation="raw.write"), dict(operator_confirmed=False),
                       dict(expected_revision=True), dict(value=1)):
            value = command(); value.update(change)
            self.assertRaises(ValueError, validate_request, value)


class CoolingStartupTests(unittest.TestCase):
    def test_repeated_measurements_and_stable_interval(self):
        clock, samples = Clock(), []
        report = wait_for_cooling(lambda unused: normal_sample(), clock,
                                  lambda *args: samples.append(args), timeout=3, clock=clock)
        self.assertGreaterEqual(report["repeated_samples"], 2)
        self.assertGreaterEqual(report["stable_seconds"], 2)
        self.assertEqual(len(samples), report["repeated_samples"])

    def test_unknown_fault_or_flicker_never_pass(self):
        for bad in ("unknown", "fault", "flicker"):
            clock = Clock()
            def read(unused):
                sample = normal_sample()
                if bad == "unknown": sample["banks"] = {}
                elif bad == "fault" or int(clock.now * 10) % 4 == 0:
                    sample["banks"]["C4_DIO96_DI"]["values"][19] = True
                return sample
            self.assertRaises(RuntimeError, wait_for_cooling, read, clock, lambda *args: None, 3, clock)

    def test_cancel_and_simulated_samples(self):
        clock = Clock(); clock.cancelled = True
        self.assertRaises(ProcedureCancelled, wait_for_cooling, lambda unused: normal_sample(), clock, lambda *args: None)
        clock = Clock(); sample = normal_sample(); sample["simulated"] = True
        self.assertRaises(RuntimeError, wait_for_cooling, lambda unused: sample, clock, lambda *args: None)

    def test_general_power_water_then_verified_ready_and_failure_does_not_continue(self):
        for fault in (False, True):
            clock, calls = Clock(), []
            class Backend(object):
                def general_start(self, cancel, operator_confirmed=False): calls.append("general")
                def execute_stage(self, operation, cancel, operator_confirmed=False): calls.append(operation)
                def read_snapshot(self, cancel):
                    sample = normal_sample()
                    if fault: sample["banks"] = {}
                    return sample
            runtime = AcquisitionControlRuntime(Backend, clock=clock, cooling_start_timeout=3)
            wrapper = _ObservedBackend(Backend(), runtime)
            if fault:
                self.assertRaises(RuntimeError, wrapper.general_start, clock, operator_confirmed=True)
                self.assertFalse(runtime._general_cooling_ready)
            else:
                wrapper.general_start(clock, operator_confirmed=True)
                self.assertTrue(runtime._general_cooling_ready)
            self.assertEqual(calls, ["general", "cooling.start"])


class BrokerTests(unittest.TestCase):
    def test_internal_runtime_snapshots_do_not_allocate_leases(self):
        runtime = AcquisitionControlRuntime(lambda: None, remote_enabled=True)
        for unused in range(100):
            self.assertIsNone(runtime.snapshot()["control"]["lease"])
        self.assertEqual(runtime.broker.leases, {})

    def test_duplicate_id_dispatches_once_and_rejects_different_request(self):
        runtime = AdmissionRuntime(); broker = CommandBroker(runtime, enabled=True)
        lease = broker.snapshot(issue_lease=True)["lease"]
        first = broker.submit(command(), lease)
        second = broker.submit(command(), None)
        self.assertEqual(first["outcome"], "QUEUED")
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(runtime.calls), 1)
        self.assertRaises(ValueError, broker.submit, command("prema.start"), None)
        token = broker.begin("chauffage.start"); broker.finish(token)
        self.assertEqual(broker.snapshot()["results"][0]["outcome"], "COMPLETED")
        self.assertFalse(broker.snapshot()["results"][0]["hardware_acknowledged"])

    def test_disabled_expired_and_old_session_do_not_dispatch(self):
        runtime, clock = AdmissionRuntime(), Clock()
        broker = CommandBroker(runtime, enabled=False, clock=clock)
        self.assertRaises(RuntimeError, broker.submit, command(), None)
        broker.enabled = True
        lease = broker.snapshot(issue_lease=True)["lease"]; clock.now = 2
        self.assertRaises(RuntimeError, broker.submit, command(), lease)
        value = command(); value["session_id"] = "c" * 32
        self.assertRaises(RuntimeError, broker.submit, value, None)
        self.assertEqual(runtime.calls, [])


class HTTPTests(unittest.TestCase):
    def test_authenticated_python34_http_leases_and_no_remote_initialization(self):
        runtime = AcquisitionControlRuntime(lambda: None, remote_enabled=True)
        server = ControlHTTPServer(("127.0.0.1", 0), runtime, b"r" * 32, b"w" * 32)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02))
        worker.daemon = True; worker.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            nonce = uuid4().hex
            request = urllib.request.Request(base + "/snapshot", headers={"X-ACQ-Nonce": nonce,
                "X-ACQ-Signature": request_signature(b"r" * 32, "/snapshot", nonce)})
            response = opener.open(request, timeout=2)
            raw = response.read(); response.close()
            self.assertTrue(hmac.compare_digest(response_signature(b"r" * 32, nonce, raw),
                                                response.headers["X-ACQ-Response-Signature"]))
            state = json.loads(raw.decode("utf-8"))
            self.assertEqual(state["state"], "IDLE")
            self.assertEqual(state["resource_count"], 0)
            self.assertIsNotNone(state["control"]["lease"])
            value = command(); value.update(session_id=state["session_id"], expected_revision=state["state_revision"])
            body = json.dumps(dict(request=value, lease=state["control"]["lease"])).encode("utf-8")
            nonce = uuid4().hex
            request = urllib.request.Request(base + "/commands", data=body, headers={"X-ACQ-Nonce": nonce,
                "X-ACQ-Signature": command_signature(b"w" * 32, nonce, body), "Content-Type": "application/json"})
            response = opener.open(request, timeout=2)
            raw = response.read(); response.close()
            result = json.loads(raw.decode("utf-8"))
            self.assertEqual(result["outcome"], "REJECTED")
            self.assertEqual(runtime.snapshot()["state"], "IDLE")
            self.assertFalse(result["hardware_acknowledged"])
        finally:
            server.shutdown(); server.server_close(); worker.join(2)


if __name__ == "__main__":
    unittest.main()
