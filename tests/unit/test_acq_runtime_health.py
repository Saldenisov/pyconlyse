"""Offline freshness regression; no Tango import, sockets, processes or NI."""

import ast
import copy
import importlib.util
import json
from pathlib import Path
import threading
import types
import unittest

from DeviceServers.control.elyse_acq.runtime_polling import RuntimePollingWorker
from tests.unit.test_acq_runtime_contract import runtime_snapshot


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "DeviceServers/control/elyse_acq/runtime_health.py"
SPEC = importlib.util.spec_from_file_location("isolated_acq_runtime_health", MODULE_PATH)
HEALTH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HEALTH)


def snapshot(**changes):
    value = dict(state="RUNNING", stale=False, age_seconds=0.1, error="",
                 latest=dict(source="python_daqmx_acquisition", simulated=False, banks={}))
    value.update(changes)
    return value


class RuntimeHealthTests(unittest.TestCase):
    def test_fresh_bridge_and_source_are_running_without_mutating_inputs(self):
        value = snapshot()
        before = copy.deepcopy(value)
        result = HEALTH.project_runtime_health(value, 0.2)
        self.assertEqual(result["tango_state"], "RUNNING")
        self.assertTrue(result["source_current"])
        self.assertFalse(result["source_stale"])
        self.assertFalse(result["bridge_stale"])
        self.assertEqual(value, before)

    def test_fresh_http_cannot_hide_runtime_reported_stale_ni(self):
        result = HEALTH.project_runtime_health(snapshot(stale=True), 0.1)
        self.assertFalse(result["bridge_stale"])
        self.assertTrue(result["source_stale"])
        self.assertEqual(result["tango_state"], "UNKNOWN")
        self.assertIn("NI input snapshot stale", result["status"])

    def test_old_source_cannot_claim_running_even_when_source_flag_is_false(self):
        for age in (2.000001, 99.0):
            with self.subTest(age=age):
                result = HEALTH.project_runtime_health(snapshot(age_seconds=age), 0.1)
                self.assertEqual(result["tango_state"], "UNKNOWN")
                self.assertEqual(result["source_age_seconds"], age + 0.1)
                self.assertEqual(result["source_reported_age_seconds"], age)

    def test_existing_source_and_bridge_thresholds_remain_inclusive(self):
        result = HEALTH.project_runtime_health(snapshot(age_seconds=2.0), 0.0)
        self.assertEqual(result["tango_state"], "RUNNING")
        result = HEALTH.project_runtime_health(snapshot(age_seconds=0.0), 3.0)
        self.assertFalse(result["bridge_stale"])
        self.assertEqual(result["tango_state"], "UNKNOWN")
        result = HEALTH.project_runtime_health(snapshot(), 3.000001)
        self.assertTrue(result["bridge_stale"])
        self.assertEqual(result["tango_state"], "UNKNOWN")

    def test_cached_bridge_elapsed_is_added_to_source_age(self):
        result = HEALTH.project_runtime_health(snapshot(age_seconds=1.9), 0.2)
        self.assertAlmostEqual(result["source_age_seconds"], 2.1)
        self.assertEqual(result["source_reported_age_seconds"], 1.9)
        self.assertEqual(result["tango_state"], "UNKNOWN")

    def test_whole_http_duration_is_conservative_age_allowance(self):
        result = HEALTH.project_runtime_health(snapshot(age_seconds=1.6), 0.2,
                                               read_duration_seconds=0.3)
        self.assertAlmostEqual(result["source_age_seconds"], 2.1)
        self.assertEqual(result["tango_state"], "UNKNOWN")
        for duration in (-1, None, True, float("nan")):
            with self.subTest(duration=duration):
                result = HEALTH.project_runtime_health(snapshot(), 0.1,
                                                       read_duration_seconds=duration)
                self.assertFalse(result["source_current"])

    def test_invalid_source_age_is_not_fresh(self):
        for age in (None, True, -1, float("nan"), float("inf"), "0.1"):
            with self.subTest(age=age):
                result = HEALTH.project_runtime_health(snapshot(age_seconds=age), 0.1)
                self.assertFalse(result["source_current"])
                self.assertIsNone(result["source_age_seconds"])

    def test_invalid_bridge_age_is_not_fresh(self):
        for age in (None, False, -1, float("nan"), float("inf"), "0.1"):
            with self.subTest(age=age):
                result = HEALTH.project_runtime_health(snapshot(), age)
                self.assertTrue(result["bridge_stale"])
                self.assertEqual(result["tango_state"], "UNKNOWN")

    def test_missing_data_or_stale_flag_cannot_claim_running(self):
        for change in (dict(latest=None), dict(stale=None), dict(stale=0), dict(error="read failed")):
            with self.subTest(change=change):
                self.assertEqual(HEALTH.project_runtime_health(snapshot(**change), 0.1)["tango_state"],
                                 "UNKNOWN")

    def test_fresh_demo_or_unidentified_data_are_not_current_ni_inputs(self):
        for latest in ({}, dict(source="python_acquisition_demo", simulated=True),
                       dict(source="python_daqmx_acquisition", simulated=True),
                       dict(source="python_daqmx_acquisition")):
            with self.subTest(latest=latest):
                result = HEALTH.project_runtime_health(snapshot(latest=latest), 0.1)
                self.assertFalse(result["source_current"])
                self.assertEqual(result["tango_state"], "UNKNOWN")

    def test_bridge_error_overrides_cached_fresh_source(self):
        result = HEALTH.project_runtime_health(snapshot(), 0.1, "connection refused")
        self.assertEqual(result["tango_state"], "UNKNOWN")
        self.assertFalse(result["source_current"])
        self.assertIn("connection refused", result["status"])

    def test_no_reader_is_fault_not_merely_unknown(self):
        result = HEALTH.project_runtime_health(None, None, "key unavailable", reader_started=False)
        self.assertEqual(result["tango_state"], "FAULT")
        self.assertTrue(result["bridge_stale"])

    def test_fault_retains_runtime_error_and_source_is_not_current(self):
        result = HEALTH.project_runtime_health(snapshot(state="FAULT", error="stop failed"), 0.1)
        self.assertEqual(result["tango_state"], "FAULT")
        self.assertFalse(result["source_current"])
        self.assertIn("stop failed", result["status"])

    def test_inactive_lifecycle_is_standby_without_inventing_measurements(self):
        for state in ("IDLE", "INITIALIZING", "DEINITIALIZING", "STOPPED"):
            with self.subTest(state=state):
                result = HEALTH.project_runtime_health(
                    snapshot(state=state, stale=True, age_seconds=None, latest=None), 0.1)
                self.assertEqual(result["tango_state"], "STANDBY")
                self.assertEqual(result["runtime_state"], state)
                self.assertTrue(result["source_stale"])
                self.assertIn("no current NI acquisition data expected", result["status"])

    def test_executing_is_activity_not_a_fresh_acquisition_claim(self):
        result = HEALTH.project_runtime_health(snapshot(state="EXECUTING", stale=True), 0.1)
        self.assertEqual(result["tango_state"], "MOVING")
        self.assertEqual(result["runtime_state"], "EXECUTING")
        self.assertFalse(result["source_current"])
        self.assertIn("procedure active", result["status"])

    def test_unknown_payload_fails_closed_without_exception(self):
        for value in (None, [], {}, snapshot(state="UNKNOWN"), snapshot(state=7), snapshot(state=[])):
            with self.subTest(value=value):
                self.assertEqual(HEALTH.project_runtime_health(value, 0.1)["tango_state"], "UNKNOWN")


class RuntimeDeviceProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Execute only these adapter methods, not imports/class construction or
        # decorators. This verifies their wiring to the pure projection while
        # allowing the suite to run when PyTango is unavailable.
        path = ROOT / "DeviceServers/control/elyse_acq/DS_AcqRuntime.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        device = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == "AcqRuntime")
        methods = [node for node in device.body if isinstance(node, ast.FunctionDef)
                   and node.name in ("_view", "_health", "runtime_json", "dev_state", "delete_device")]
        for node in methods:
            node.decorator_list = []
        namespace = dict(json=json, time=types.SimpleNamespace(monotonic=lambda: 100.0),
                         project_runtime_contract=HEALTH.project_runtime_contract,
                         tango=types.SimpleNamespace(DevState=types.SimpleNamespace(
                             FAULT="FAULT", UNKNOWN="UNKNOWN", RUNNING="RUNNING",
                             STANDBY="STANDBY", MOVING="MOVING")))
        module = ast.Module(body=methods, type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
        cls.namespace = namespace
        cls.device_type = type("OfflineRuntimeView", (), {
            name: namespace[name] for name in ("_view", "_health", "runtime_json", "dev_state", "delete_device")})

    def make_device(self, value):
        device = self.device_type()
        device._reader = RuntimePollingWorker(b"synthetic-device-read-key-at-least32", clock=lambda: 100.0,
                                              reader=lambda *args, **kwargs: value)
        device._reader.poll_once()
        device.set_status = lambda status: setattr(device, "status", status)
        device.set_state = lambda state: setattr(device, "state", state)
        return device

    def test_device_no_longer_reports_running_for_fresh_http_stale_source(self):
        device = self.make_device(runtime_snapshot(stale=True, age_seconds=99.0))
        self.assertEqual(device.dev_state(), "UNKNOWN")
        body = json.loads(device.runtime_json())
        self.assertFalse(body["bridge_stale"])
        self.assertTrue(body["source_stale"])
        self.assertFalse(body["source_current"])
        self.assertEqual(body["source_age_seconds"], 99.0)
        self.assertEqual(device.state, "UNKNOWN")

    def test_device_fresh_data_remain_running(self):
        device = self.make_device(runtime_snapshot())
        body = json.loads(device.runtime_json())
        self.assertTrue(body["source_current"])
        self.assertEqual(device.state, "RUNNING")
        self.assertEqual(device.dev_state(), "RUNNING")

    def test_device_distinguishes_idle_from_executing(self):
        for state, expected in (("IDLE", "STANDBY"), ("EXECUTING", "MOVING")):
            with self.subTest(state=state):
                device = self.make_device(runtime_snapshot(state=state, stale=True))
                body = json.loads(device.runtime_json())
                self.assertEqual(body["runtime_state"], state)
                self.assertFalse(body["source_current"])
                self.assertEqual(device.dev_state(), expected)

    def test_device_adds_last_http_duration_before_claiming_source_current(self):
        device = self.make_device(runtime_snapshot(age_seconds=1.9))
        device._reader._duration = 0.2
        body = json.loads(device.runtime_json())
        self.assertAlmostEqual(body["source_age_seconds"], 2.1)
        self.assertEqual(body["source_reported_age_seconds"], 1.9)
        self.assertEqual(device.dev_state(), "UNKNOWN")

    def test_reader_records_elapsed_duration_without_network(self):
        times = iter((100.0, 100.3))
        reader = RuntimePollingWorker(b"synthetic-duration-key-at-least-32bytes",
                                      clock=lambda: next(times),
                                      reader=lambda *args, **kwargs: runtime_snapshot())
        reader.poll_once()
        self.assertEqual(reader._received, 100.3)
        self.assertAlmostEqual(reader._duration, 0.3)
        self.assertEqual(reader._runtime["state"], "RUNNING")

    def test_device_missing_protocol_is_unknown_and_hides_latest(self):
        device = self.make_device(snapshot())
        self.assertEqual(device.dev_state(), "UNKNOWN")
        body = json.loads(device.runtime_json())
        self.assertEqual(body["quality"], "INCOMPATIBLE")
        self.assertIsNone(body["runtime"]["latest"])

    def test_device_delete_stops_reader_without_hardware_calls(self):
        device = self.make_device(runtime_snapshot())
        device.delete_device()
        body = json.loads(device.runtime_json())
        self.assertEqual(body["quality"], "UNAVAILABLE")
        self.assertIsNone(body["runtime"])

    def test_device_delete_reports_retained_blocked_reader(self):
        device = self.make_device(runtime_snapshot())
        class RetainedReader:
            def stop(self, timeout):
                return False
        device._reader = RetainedReader()
        warnings = []
        device.warn_stream = warnings.append
        device.delete_device()
        self.assertEqual(len(warnings), 1)
        self.assertIn("live owner retained", warnings[0])
        self.assertIn("restart refused", device.status)
        self.assertIsInstance(device._reader, RetainedReader)


if __name__ == "__main__":
    unittest.main()
