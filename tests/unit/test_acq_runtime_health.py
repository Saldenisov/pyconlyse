"""Read-only FAULT diagnostic projection with complete RAM input snapshots."""
import copy
import unittest

from DeviceServers.control.elyse_acq.control_runtime_health import (
    project_runtime_contract, project_runtime_health,
)
from tests.unit.test_acq_fault_telemetry import diagnostic_state


def runtime():
    value = diagnostic_state()
    value.update(runtime_protocol_version=2, build_id="d" * 64, storage_mode="ram_latest",
                 auto_initialize=False, remote_initialization_enabled=False,
                 remote_setpoints_enabled=False,
                 recovery=dict(required=False, protection_active=False, reason=""))
    value["latest"]["banks"]["C11_NI6220_AI"] = dict(kind="analog_input", device=11,
        values=[1.] * 16, legacy_scaled_values=[2.] * 16)
    return value


class RuntimeHealthDiagnosticTests(unittest.TestCase):
    def assert_not_diagnostic(self, value, **options):
        for project in (project_runtime_health, project_runtime_contract):
            with self.subTest(project=project.__name__, options=options):
                result = project(value, options.get("bridge_age_seconds", .1),
                    **dict((key, item) for key, item in options.items() if key != "bridge_age_seconds"))
                self.assertIs(result["diagnostic_source_current"], False)
                self.assertIs(result["source_current"], False)
                self.assertNotIn("fresh diagnostic", result["status"])
                if project is project_runtime_contract:
                    self.assertNotEqual(result["quality"], "FRESH")
                    self.assertIs(result["execution_allowed"], False)
                    self.assertIs(result["hardware_writes"], False)

    def test_fresh_diagnostic_is_explicit_while_fault_and_commands_stay_unchanged(self):
        value = runtime()
        before = copy.deepcopy(value)
        for project in (project_runtime_health, project_runtime_contract):
            result = project(value, .1, read_duration_seconds=.05)
            self.assertIs(result["diagnostic_source_current"], True)
            self.assertAlmostEqual(result["diagnostic_source_age_seconds"], .4)
            self.assertEqual(result["runtime_state"], "FAULT")
            self.assertEqual(result["tango_state"], "FAULT")
            self.assertIs(result["source_current"], False)
            self.assertIs(result["source_stale"], True)
            self.assertIn("fresh diagnostic NI input readback during FAULT", result["status"])
            self.assertIn(value["error"], result["status"])
            self.assertIn("no remote controls enabled", result["status"])
            if project is project_runtime_contract:
                self.assertEqual(result["quality"], "FAULT")
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["hardware_writes"], False)
        self.assertEqual(value, before)

    def test_cached_fault_inputs_without_explicit_observation_are_not_current(self):
        value = runtime()
        del value["fault_diagnostic_measurement"]
        self.assert_not_diagnostic(value)

    def test_source_and_full_transport_elapsed_time_expire_diagnostics(self):
        for age in (2., -.1, float("nan"), float("inf"), True, 2**4096):
            with self.subTest(age=age):
                value = runtime()
                value["age_seconds"] = age
                value["fault_diagnostic_measurement"]["age_seconds"] = age
                self.assert_not_diagnostic(value)
        self.assert_not_diagnostic(runtime(), bridge_age_seconds=1.75)
        self.assert_not_diagnostic(runtime(), read_duration_seconds=1.65)
        self.assert_not_diagnostic(runtime(), read_duration_seconds=-.1)

    def test_uncertain_pending_or_changed_native_owner_never_qualifies(self):
        for name, candidate in (("worker_state", "EXECUTING_READ_SNAPSHOT"),
                ("ownership_uncertain", True), ("active_request_id", "pending"),
                ("resource_count", 0), ("resource_count", True), ("worker_generation", "c" * 32)):
            value = runtime()
            value["native_isolation"][name] = candidate
            self.assert_not_diagnostic(value)

    def test_read_attestation_must_match_session_sequence_owner_and_age(self):
        for name, candidate in (("current", False), ("session_id", "c" * 32),
                ("sequence", 4), ("sequence", True), ("worker_generation", "c" * 32),
                ("age_seconds", .1), ("command_admission", True), ("source", "execution_heartbeat")):
            value = runtime()
            value["fault_diagnostic_measurement"][name] = candidate
            self.assert_not_diagnostic(value)
        self.assert_not_diagnostic(runtime(), session_changed=True)

    def test_bridge_errors_inactive_reader_and_protocol_errors_invalidate_diagnostics(self):
        self.assert_not_diagnostic(runtime(), bridge_error="signature verification failed")
        self.assert_not_diagnostic(runtime(), reader_started=False)
        self.assert_not_diagnostic(runtime(), protocol_error="inconsistent runtime build")
        for age in (-.1, None, float("nan"), 3.1):
            self.assert_not_diagnostic(runtime(), bridge_age_seconds=age)

    def test_identity_and_recovery_contract_are_required_even_for_loose_health_projection(self):
        for field, candidate in (("runtime_protocol_version", 1), ("session_id", "invalid"),
                ("build_id", "invalid"), ("state_revision", -1), ("storage_mode", "file"),
                ("remote_setpoints_enabled", True), ("stale", False),
                ("measurement_current", True), ("error", ""), ("telemetry_view_current", False)):
            value = runtime()
            value[field] = candidate
            self.assert_not_diagnostic(value)
        value = runtime()
        value["recovery"]["required"] = True
        result = project_runtime_contract(value, .1)
        self.assertEqual(result["quality"], "RECOVERY_REQUIRED")
        self.assert_not_diagnostic(value)

    def test_all_six_input_shapes_types_and_source_must_be_valid(self):
        for change in ("missing", "extra", "count", "digital", "analog", "scaled", "overflow",
                       "device", "kind", "source", "simulated", "latest"):
            with self.subTest(change=change):
                value = runtime()
                banks = value["latest"]["banks"]
                if change == "missing":
                    del banks["C11_NI6220_AI"]
                elif change == "extra":
                    banks["unexpected"] = {}
                elif change == "count":
                    banks["C1_NI6071E_AI"]["values"].pop()
                elif change == "digital":
                    banks["C3_DIO96_DI"]["values"][0] = 0
                elif change == "analog":
                    banks["C1_NI6071E_AI"]["values"][0] = True
                elif change == "scaled":
                    banks["C1_NI6071E_AI"]["legacy_scaled_values"][0] = float("nan")
                elif change == "overflow":
                    banks["C1_NI6071E_AI"]["values"][0] = 2**4096
                elif change == "device":
                    banks["C1_NI6071E_AI"]["device"] = True
                elif change == "kind":
                    banks["C1_NI6071E_AI"]["kind"] = "analog_output"
                elif change == "source":
                    value["latest"]["source"] = "simulated"
                elif change == "simulated":
                    value["latest"]["simulated"] = True
                else:
                    value["latest"] = ["invalid"]
                self.assert_not_diagnostic(value)

    def test_normal_running_projection_does_not_become_a_fault_diagnostic(self):
        value = runtime()
        value.update(state="RUNNING", stale=False, measurement_current=True, error="")
        result = project_runtime_contract(value, .1)
        self.assertEqual(result["quality"], "FRESH")
        self.assertEqual(result["tango_state"], "RUNNING")
        self.assertIs(result["source_current"], True)
        self.assertIs(result["diagnostic_source_current"], False)
        self.assertIs(result["execution_allowed"], False)


if __name__ == "__main__":
    unittest.main()
