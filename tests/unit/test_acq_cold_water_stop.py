"""Cold General/water-only stop permission; RAM callbacks, Python 3.4."""
import unittest

from tests.unit.test_acq_supervised_backend import fixture
from tests.unit import test_acq_supervised_runtime as runtime_fixture
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities


class ColdWaterStopTests(unittest.TestCase):
    def test_source_water_stop_runs_without_serial_or_other_stage_start(self):
        backend, owner, clock = fixture()
        backend.general_start(clock, operator_confirmed=True)
        backend.execute_stage("cooling.start", clock, operator_confirmed=True)
        report = backend.execute_stage("cooling.stop", clock, operator_confirmed=True)
        self.assertFalse(report["hardware_acknowledged"])
        self.assertTrue(backend.operator_cold_water_only)
        self.assertEqual(backend.focal_command.output_calls, [])
        self.assertTrue(any(row[:2] == ("do", "C3_DIO96_DO") for row in owner.trace))

    def test_energy_attempt_revokes_cold_water_permission_before_driver_failure(self):
        for operation in ("chauffage.start", "prema.start", "focales.start", "relays_ht.start"):
            backend, owner, clock = fixture()
            observed = []
            def fail():
                observed.append(backend.operator_cold_water_only)
                raise IOError("injected pre-output failure")
            backend._ensure_focal_quiescent = fail
            self.assertRaises(IOError, backend.execute_stage, operation, clock, operator_confirmed=True)
            self.assertEqual(observed, [False])
            owner.trace[:] = []
            self.assertRaises(RuntimeError, backend.execute_stage, "cooling.stop", clock,
                              operator_confirmed=True)
            self.assertEqual(owner.trace, [])

    def test_permission_requires_current_cold_fact_even_in_fault(self):
        helper = runtime_fixture.SupervisedRuntimeTests()
        runtime, clock, backend = helper.make_runtime()
        backend.control_profile = "extended_ht_stop"
        backend.operator_cold_water_only = True
        helper.general(runtime)
        runtime._state, runtime._error = "FAULT", "COOLING_START_TIMEOUT"
        self.assertTrue(command_capabilities(runtime.snapshot())["cooling.stop"]["enabled"])
        self.assertTrue(runtime.stage_request("cooling.stop", operator_confirmed=True))
        runtime._state, runtime._pending, runtime._operation = "RUNNING", None, None
        backend.operator_cold_water_only = False
        self.assertFalse(command_capabilities(runtime.snapshot())["cooling.stop"]["enabled"])
        self.assertRaises(RuntimeError, runtime.stage_request, "cooling.stop", True)

    def test_missing_cold_fact_or_uncertain_owner_never_grants_stop_exception(self):
        for fact in (False, None, 1, "true"):
            backend, owner, clock = fixture()
            backend.operator_cold_water_only = fact
            self.assertRaises(RuntimeError, backend.execute_stage, "cooling.stop", clock,
                              operator_confirmed=True)
            self.assertEqual(owner.trace, [])
        helper = runtime_fixture.SupervisedRuntimeTests()
        runtime, clock, backend = helper.make_runtime()
        backend.operator_cold_water_only, backend.uncertain = True, True
        self.assertRaises(RuntimeError, runtime.stage_request, "cooling.stop", True)


if __name__ == "__main__":
    unittest.main()
