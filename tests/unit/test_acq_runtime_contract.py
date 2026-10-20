"""Strict v2 runtime health, entirely synthetic and import-inert."""
import copy
import unittest

from DeviceServers.control.elyse_acq.runtime_health import (
    INPUT_BANKS, project_runtime_contract, validate_runtime_identity,
)


def runtime_snapshot(**changes):
    banks = {name: dict(kind=kind, device=device,
                        values=[False if kind == "digital_input" else 1.0] * count)
             for name, (kind, device, count) in INPUT_BANKS.items()}
    value = dict(runtime_protocol_version=2, session_id="1" * 32, build_id="a" * 64,
                 state_revision=0, recovery=dict(required=False, reason="", protection_active=True),
                 storage_mode="ram_latest", auto_initialize=False,
                 remote_initialization_enabled=False, remote_setpoints_enabled=False,
                 state="RUNNING", stale=False, age_seconds=0.1, error="",
                 latest=dict(source="python_daqmx_acquisition", simulated=False, banks=banks))
    value.update(changes)
    return value


class RuntimeContractTests(unittest.TestCase):
    def test_protocol_v2_fresh_input_is_observation_never_command_permission(self):
        source = runtime_snapshot()
        before = copy.deepcopy(source)
        result = project_runtime_contract(source, 0.2, read_duration_seconds=0.1)
        self.assertEqual(result["quality"], "FRESH")
        self.assertEqual(result["session_id"], "1" * 32)
        self.assertEqual(result["source_age_seconds"], 0.4)
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["hardware_writes"])
        self.assertEqual(before, source)

    def test_missing_wrong_or_invalid_identity_never_looks_fresh(self):
        cases = [dict(runtime_protocol_version=None), dict(runtime_protocol_version=True),
                 dict(runtime_protocol_version=1), dict(session_id=""), dict(session_id="F" * 32),
                 dict(build_id="x" * 64), dict(state_revision=True), dict(state_revision=-1),
                 dict(state_revision=2**53), dict(state=[]), dict(recovery=None),
                 dict(error=0), dict(stale=0),
                 dict(recovery=dict(required=0, reason="", protection_active=True)),
                 dict(remote_setpoints_enabled=True)]
        for changes in cases:
            with self.subTest(changes=changes):
                result = project_runtime_contract(runtime_snapshot(**changes), 0.1)
                self.assertEqual(result["quality"], "INCOMPATIBLE")
                self.assertTrue(result["source_stale"])
                self.assertIsNone(result["session_id"])

    def test_transport_error_takes_precedence_over_cached_or_invalid_identity(self):
        for value in (runtime_snapshot(), {}, None):
            result = project_runtime_contract(value, 0.1, "connection refused")
            self.assertEqual(result["quality"], "UNAVAILABLE")
            self.assertFalse(result["source_current"])

    def test_source_and_bridge_age_are_independently_rechecked(self):
        for changes, age, duration in ((dict(age_seconds=2.1), 0.0, 0.0),
                                       (dict(age_seconds=1.7), 0.2, 0.2),
                                       (dict(age_seconds=0.0), 3.1, 0.0),
                                       (dict(stale=True), 0.0, 0.0)):
            result = project_runtime_contract(runtime_snapshot(**changes), age,
                                              read_duration_seconds=duration)
            self.assertEqual(result["quality"], "STALE")

    def test_recovery_idle_executing_and_fault_do_not_expose_fresh_measurements(self):
        cases = [(dict(state="RECOVERY_REQUIRED", recovery=dict(
                    required=True, reason="prior ownership", protection_active=True)), "RECOVERY_REQUIRED"),
                 (dict(state="IDLE", latest=None), "IDLE"),
                 (dict(state="INITIALIZING"), "EXECUTING"),
                 (dict(state="EXECUTING"), "EXECUTING"),
                 (dict(state="FAULT", error="cleanup failed"), "FAULT")]
        for changes, expected in cases:
            result = project_runtime_contract(runtime_snapshot(**changes), 0.1)
            self.assertEqual(result["quality"], expected)
            self.assertTrue(result["source_stale"])

    def test_recovery_required_overrides_running_without_claiming_hardware_unsafe(self):
        source = runtime_snapshot(recovery=dict(required=True, reason="retained owner", protection_active=True))
        result = project_runtime_contract(source, 0.0)
        self.assertEqual(result["quality"], "RECOVERY_REQUIRED")
        self.assertEqual(result["tango_state"], "FAULT")

    def test_guard_inactive_does_not_fabricate_missing_ni_measurements(self):
        source = runtime_snapshot(recovery=dict(required=False, reason="", protection_active=False))
        self.assertEqual(project_runtime_contract(source, 0.0)["quality"], "FRESH")

    def test_restart_session_needs_another_consistent_poll(self):
        result = project_runtime_contract(runtime_snapshot(), 0.0, session_changed=True)
        self.assertEqual(result["quality"], "STALE")
        self.assertEqual(project_runtime_contract(runtime_snapshot(), 0.0)["quality"], "FRESH")

    def test_frozen_build_or_revision_protocol_error_is_incompatible(self):
        result = project_runtime_contract(runtime_snapshot(), 0.0,
                                          protocol_error="revision moved backwards")
        self.assertEqual(result["quality"], "INCOMPATIBLE")

    def test_complete_six_bank_type_shape_and_source_revalidated_every_time(self):
        for defect in ("missing", "unknown", "bool_ai", "numeric_di", "wrong_device", "nan", "demo"):
            value = runtime_snapshot()
            banks = value["latest"]["banks"]
            if defect == "missing":
                banks.pop("C1_NI6071E_AI")
            elif defect == "unknown":
                banks["other"] = {}
            elif defect == "bool_ai":
                banks["C1_NI6071E_AI"]["values"][0] = False
            elif defect == "numeric_di":
                banks["C3_DIO96_DI"]["values"][0] = 0
            elif defect == "wrong_device":
                banks["C1_NI6071E_AI"]["device"] = True
            elif defect == "nan":
                banks["C1_NI6071E_AI"]["values"][0] = float("nan")
            else:
                value["latest"].update(source="python_acquisition_demo", simulated=True)
            self.assertEqual(project_runtime_contract(value, 0.0)["quality"], "STALE", defect)

    def test_identity_validation_is_pure_and_has_no_reader_or_hardware_dependency(self):
        source = runtime_snapshot()
        result = validate_runtime_identity(source)
        result["recovery"]["required"] = True
        self.assertFalse(source["recovery"]["required"])


if __name__ == "__main__":
    unittest.main()
