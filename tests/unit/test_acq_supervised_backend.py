"""Explicit operator test permission with RAM fixtures; no NI, XP or serial I/O."""
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.acquisition_backend import (
    AcquisitionCancelled, CardBackend, DemoBackend,
)
from legacy.xp_acq_control.elyse_agent.acquisition_procedures import GeneralStopError
from legacy.xp_acq_control.elyse_agent.chroma_focal_command import ChromaCommandError, ChromaFocalCommand
from tests.unit.test_acq_stage_status_telemetry import Clock, Owner


class Focal(object):
    resources_verified = False

    def __init__(self):
        self.ready_calls = 0
        self.output_calls = []
        self.blocked = False

    def ensure_ready(self):
        self.ready_calls += 1

    def ensure_quiescent(self):
        if self.blocked:
            raise RuntimeError("fixture retained Chroma worker")

    def execute(self, enabled, cancelled):
        self.ensure_quiescent()
        self.output_calls.append(enabled)
        return dict(hardware_acknowledged=False, physical_output_state="UNKNOWN")

    def snapshot(self):
        return dict(resources_verified=False, hardware_acknowledged=False,
                    pending_worker_count=int(self.blocked), physical_output_state="UNKNOWN")


def fixture(initialize=True, focal=None, **options):
    clock = Clock()
    owner = Owner(clock)
    options.setdefault("operator_supervised_test", True)
    options.setdefault("control_profile", "extended_ht_stop")
    backend = CardBackend(factory=lambda **kwargs: owner, stop_wait=clock.wait,
                          focal_command=focal or Focal(), **options)
    if initialize:
        backend.initialize(clock, startup_confirmed=True)
    owner.trace[:] = []
    return backend, owner, clock


class SupervisedBackendTests(unittest.TestCase):
    def test_mode_is_exact_boolean_and_never_sets_qualification_flags(self):
        for cls in (CardBackend, DemoBackend, ChromaFocalCommand):
            self.assertIs(cls().operator_supervised_test, False)
            for value in (1, 0, None, "true"):
                self.assertRaises(ValueError, cls, operator_supervised_test=value)
        backend, _owner, _clock = fixture()
        self.assertTrue(backend.operator_test_cold_attested)
        state = backend._stage_snapshot()
        for name in ("stage_controls_verified", "cooling_trip_verified", "ht_controls_verified",
                     "focal_controls_verified", "beamline_controls_verified", "focal_resources_verified"):
            self.assertIs(state[name], False)
        self.assertIs(backend.ht_feedback_verified, False)
        self.assertIs(backend.counter_controls_verified, False)
        self.assertIs(backend.ht_voltage_controls_verified, False)
        self.assertIs(state["hardware_acknowledged"], False)
        self.assertIn("not measured proof", state["operator_test_cold_attestation_interpretation"])

    def test_general_start_skips_chroma_readiness_and_ht_feedback_only_with_cold_attestation(self):
        checks = []
        focal = ChromaFocalCommand(operator_supervised_test=True,
            platform_check=lambda: checks.append("platform") or False,
            driver_verifier=lambda path: checks.append("DLL"))
        backend, owner, clock = fixture(focal=focal)
        backend.general_start(clock, operator_confirmed=True)
        self.assertEqual(checks, [])
        self.assertEqual(len([row for row in owner.trace if row[0] == "do"]), 6)
        self.assertTrue(backend.operator_test_cold_attested)
        self.assertFalse(backend.ht_feedback_verified)
        self.assertFalse(focal.resources_verified)
        backend.operator_test_cold_attested = False
        owner.trace[:] = []
        self.assertRaises(RuntimeError, backend.general_start, clock, operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_general_stop_keeps_every_source_frame_when_chroma_is_unavailable(self):
        focal = ChromaFocalCommand(operator_supervised_test=True, platform_check=lambda: False,
                                  driver_verifier=lambda path: None)
        backend, owner, clock = fixture(focal=focal)
        backend.general_start(clock, operator_confirmed=True)
        owner.trace[:] = []
        with patch("legacy.xp_acq_control.elyse_agent.acquisition_backend.execute_ht_shutdown",
                   side_effect=AssertionError("Cold operator test must not run the Python HT preamble")):
            with self.assertRaises(GeneralStopError) as raised:
                backend.general_stop(operator_confirmed=True)
        self.assertIn("32-bit XP", str(raised.exception))
        self.assertEqual(backend.procedure["source_frames_attempted"], list(range(17)))
        self.assertEqual(backend.procedure["stop_scope"], "labview_event_6")
        self.assertFalse(backend.procedure["ht_supply_stop_included"])
        self.assertFalse(backend.procedure["hardware_off_confirmed"])
        rows = [row for row in owner.trace if row[:2] == ("do", "C4_DIO96_DO")]
        self.assertEqual(len(rows), 10)
        self.assertEqual([(line, rows[index * 2][2][line], rows[index * 2 + 1][2][line])
                          for index, line in enumerate((8, 17, 6, 4, 1))],
                         [(8, False, True), (17, False, True), (6, False, True),
                          (4, False, True), (1, False, True)])
        self.assertFalse(any(row[0] in ("ai_start", "ai_read", "di_read") for row in owner.trace))

    def test_whitelisted_stages_execute_sequentially_without_qualification_claims(self):
        backend, _owner, clock = fixture()
        backend.general_start(clock, operator_confirmed=True)
        for operation in ("cooling.start", "chauffage.start", "chauffage.stop", "prema.start",
                          "prema.stop", "focales.start", "focales.stop", "relays_ht.start",
                          "relays_ht.stop", "modulator.reset"):
            report = backend.execute_stage(operation, clock, operator_confirmed=True)
            self.assertIs(report["hardware_acknowledged"], False)
            self.assertTrue(backend.operator_test_cold_attested)
        self.assertEqual(backend.focal_command.output_calls, [True, False])
        self.assertIs(backend.stage_controls_verified, False)
        self.assertIs(backend.focal_controls_verified, False)
        self.assertIs(backend.ht_controls_verified, False)

    def test_ht_energy_and_nonwhitelisted_operations_receive_no_exemption(self):
        backend, owner, clock = fixture()
        for operation in ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset",
                          "cooling.stop", "faraday_1.en_pulse"):
            self.assertRaises(RuntimeError, backend.execute_stage, operation, clock, operator_confirmed=True)
        self.assertRaises(RuntimeError, backend.execute_impulsion, "modulator_impulse.start", clock,
                          operator_confirmed=True)
        self.assertRaises(RuntimeError, backend.set_ht_voltage, 7.0, clock, operator_confirmed=True)
        self.assertEqual(owner.trace, [])
        self.assertTrue(backend.operator_test_cold_attested)

    def test_uninitialized_cancelled_and_partial_startup_never_attest_cold(self):
        backend, owner, clock = fixture(initialize=False)
        self.assertFalse(backend.operator_test_cold_attested)
        self.assertRaises(ValueError, backend.initialize, clock)
        self.assertRaises(RuntimeError, backend.general_start, clock, operator_confirmed=True)
        owner.cancel_initial_images = True
        self.assertRaises(AcquisitionCancelled, backend.initialize, clock, startup_confirmed=True)
        self.assertFalse(backend.operator_test_cold_attested)
        self.assertFalse(backend.startup_complete)
        owner.trace[:] = []
        self.assertRaises(RuntimeError, backend.general_start, Clock(), operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_unknown_images_and_retained_workers_still_block_test_commands(self):
        for kind in ("ht", "counter", "pulse", "shape", "worker", "cold"):
            backend, owner, clock = fixture()
            if kind == "ht":
                backend.ht_command_uncertain = True
            elif kind == "counter":
                backend._counter_configuration_uncertain.add(3)
            elif kind == "pulse":
                bank = list(backend.commanded_digital["C4_DIO96_DO"])
                bank[0] = True
                backend.commanded_digital["C4_DIO96_DO"] = tuple(bank)
            elif kind == "shape":
                backend.commanded_digital["C4_DIO96_DO"] = (False,)
            elif kind == "worker":
                backend.focal_command.blocked = True
            else:
                backend.operator_test_cold_attested = False
            self.assertRaises(RuntimeError, backend.general_start, clock, operator_confirmed=True)
            self.assertRaises(RuntimeError, backend.execute_stage, "chauffage.start", clock,
                              operator_confirmed=True)
            self.assertEqual(owner.trace, [])

    def test_actual_ht_effects_invalidate_attestation_before_ni_callback_even_when_it_raises(self):
        for effect in ("supply", "counter", "voltage"):
            backend, owner, clock = fixture(stage_controls_verified=True, ht_controls_verified=True)
            observed = []

            def interrupted(*args, **kwargs):
                observed.append(backend.operator_test_cold_attested)
                raise IOError("fixture unknown hardware result")

            if effect == "supply":
                owner.write_digital_bank = interrupted
                self.assertRaises(Exception, backend.execute_stage, "alimentation_ht.start", clock,
                                  operator_confirmed=True)
            elif effect == "counter":
                owner.start_counter = interrupted
                self.assertRaises(IOError, backend._source_counter_start, 3)
            else:
                owner.write_analog_logical_bank = interrupted
                self.assertRaises(IOError, backend._source_commit_analog, "C9NI6703",
                                  backend.commanded_analog["C9NI6703"])
            self.assertTrue(observed)
            self.assertEqual(set(observed), {False})
            self.assertFalse(backend.operator_test_cold_attested)
            self.assertRaises(RuntimeError, backend.general_stop, operator_confirmed=True)

    def test_close_clears_attestation_even_when_quiescence_is_unresolved(self):
        backend, owner, _clock = fixture()
        backend.focal_command.blocked = True
        self.assertRaises(RuntimeError, backend.close)
        self.assertFalse(backend.operator_test_cold_attested)
        self.assertFalse(backend.startup_complete)
        self.assertIs(backend.owner, owner)

    def test_demo_requires_confirmed_mode_startup_and_preserves_false_resource_flag(self):
        backend, clock = DemoBackend(operator_supervised_test=True), Clock()
        self.assertRaises(ValueError, backend.initialize, clock)
        backend.initialize(clock, startup_confirmed=True)
        backend.general_start(clock, operator_confirmed=True)
        backend.execute_stage("focales.start", clock, operator_confirmed=True)
        self.assertTrue(backend.operator_test_cold_attested)
        self.assertFalse(backend.stage_controls_verified)
        self.assertFalse(backend.focal_command.resources_verified)
        with patch("legacy.xp_acq_control.elyse_agent.acquisition_backend.time.sleep", clock.wait):
            backend.general_stop(operator_confirmed=True)
        self.assertFalse(backend._focal_helper_results["1_Focales OFF.vi"]["output_enabled"])
        backend.close()
        self.assertFalse(backend.operator_test_cold_attested)


class FinishedProcess(object):
    pid = 123

    def poll(self):
        return 0

    def wait(self, timeout):
        return 0

    def communicate(self, timeout):
        return b"", b""


class SupervisedChromaTests(unittest.TestCase):
    def test_explicit_fixed_target_permission_preserves_platform_driver_and_output_semantics(self):
        calls = []

        def spawn(argv, **kwargs):
            calls.append((argv, kwargs))
            return FinishedProcess()

        verified = []
        command = ChromaFocalCommand(resources_verified=False, operator_supervised_test=True,
            process_factory=spawn, platform_check=lambda: True, driver_verifier=verified.append)
        self.assertEqual(verified, [])
        self.assertEqual(calls, [])
        command.ensure_ready()
        for enabled in (True, False):
            result = command.execute(enabled, lambda: False)
            self.assertTrue(result["completed"])
            self.assertFalse(result["hardware_acknowledged"])
            self.assertEqual(result["physical_output_state"], "UNKNOWN")
        self.assertEqual([call[0][-2:] for call in calls],
                         [["3", "1"], ["2", "1"], ["1", "1"],
                          ["3", "0"], ["2", "0"], ["1", "0"]])
        self.assertEqual(len(verified), 3)
        snapshot = command.snapshot()
        self.assertFalse(snapshot["resources_verified"])
        self.assertTrue(snapshot["operator_test_fixed_targets_permitted"])
        self.assertEqual(snapshot["fixed_targets"], [dict(focal=3, resource="COM10"),
            dict(focal=2, resource="COM11"), dict(focal=1, resource="COM12")])

    def test_test_permission_never_skips_platform_driver_target_or_timeout_checks(self):
        def driver_failure(path):
            raise ValueError("fixture wrong reviewed DLL hash")

        command = ChromaFocalCommand(operator_supervised_test=True, platform_check=lambda: False,
                                    driver_verifier=lambda path: None)
        self.assertRaises(RuntimeError, command.ensure_ready)
        command._platform_check = lambda: True
        command._verify = driver_failure
        self.assertRaises(ValueError, command.ensure_ready)
        command._verify = lambda path: None
        command.timeout = .01
        self.assertRaises(ValueError, command.ensure_ready)
        command.timeout = 10.
        with patch("legacy.xp_acq_control.elyse_agent.chroma_focal_command.BRANCHES",
                   ((3, "COM99", 70., .02, 15.1),)):
            self.assertRaises(RuntimeError, command.ensure_ready)
        self.assertFalse(command.resources_verified)

    def test_pending_unknown_worker_blocks_further_readiness_and_remains_retained(self):
        class PendingProcess(object):
            def poll(self):
                return None

            def kill(self):
                raise OSError("fixture kill unavailable")

            def wait(self, timeout):
                raise RuntimeError("fixture join unconfirmed")

        command = ChromaFocalCommand(operator_supervised_test=True,
            platform_check=lambda: True, driver_verifier=lambda path: None)
        command._workers.append(dict(focal=3, process=PendingProcess()))
        self.assertRaises(ChromaCommandError, command.ensure_ready)
        self.assertEqual(command.pending_worker_count, 1)
        self.assertFalse(command.snapshot()["hardware_acknowledged"])


if __name__ == "__main__":
    unittest.main()
