"""Production per-card backend integration using private RAM subprocesses.

Actual Python 3.4-compatible tests. No NI, XP, serial or network access. The
full-topology test runs the production CardBackend and CardProcessTasks paths;
only the card service's trusted local hardware constructor is replaced.
"""
import copy
import threading
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend, AcquisitionCancelled
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.card_observation import card_inputs_current, generation_vector
from legacy.xp_acq_control.elyse_agent.card_process_owner import create_card_process_tasks
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities
from legacy.xp_acq_control.elyse_agent.hardware_plan import AI_BANKS, DI_BANKS, digital_startup_image
from tests.unit import test_acq_card_process_owner as process_fixture


class Clock(object):
    def __init__(self):
        self.now = 100.

    def __call__(self):
        return self.now


class Focal(object):
    resources_verified = False

    def ensure_quiescent(self):
        pass

    def ensure_ready(self):
        raise AssertionError("General-only integration must not open Chroma")

    def snapshot(self):
        return dict(pending_worker_count=0, hardware_acknowledged=False)


def _private_process_factory(**options):
    options.update(trusted_factory="tests.unit.test_acq_card_process_owner:normal_fixture",
                   initialize_timeout=20., close_timeout=1., rpc_timeout=2., period=.05)
    return create_card_process_tasks(**options)


def _runtime(backend, clock):
    runtime = AcquisitionControlRuntime(lambda: backend, clock=clock, remote_enabled=True)
    wrapper = _ObservedBackend(backend, runtime)
    runtime._backend, runtime._state = wrapper, "RUNNING"
    runtime._ht_sequence_owner = wrapper
    isolated = getattr(backend, "isolation_snapshot", None)
    runtime._ht_sequence_generation = isolated()["worker_generation"] if isolated else None
    runtime._recovery_snapshot = lambda: dict(required=False, protection_active=True)
    return runtime


def _accept(runtime, clock, sample):
    runtime._latest = copy.deepcopy(sample)
    runtime._received_at = clock.now - sample.get("source_age_seconds", 0.)
    runtime._sequence += 1


def _ram_sample():
    banks = {}
    for name, device, count in AI_BANKS:
        banks[name] = dict(kind="analog_input", device=device, values=[0.] * count,
                           legacy_scaled_values=[0.] * count)
    for name, device, first, last, count in DI_BANKS:
        values = [False] * count
        if device == 3:
            for index in (1, 4, 7, 10):
                values[index] = True
        if device == 4:
            values[48] = True
        banks[name] = dict(kind="digital_input", device=device, values=values)
    vector = [(device, "{0:032x}".format(device)) for device in range(1, 12)]
    state = dict(all_required_ready=True, generation_vector=vector, transport_age_seconds=0.)
    sample = dict(source="python_daqmx_acquisition", simulated=False,
        source_age_seconds=1.99, banks=banks,
        input_health=dict(all_current=True, generation_vector=vector,
                          required_input_cards=[1, 2, 3, 4, 5, 11]))
    return sample, state


class OneSampleBackend(object):
    """A RAM-only owner that blocks its second read until the test releases it."""
    resource_count = 1
    startup_complete = True
    operator_supervised_test = True
    operator_test_cold_attested = True
    operator_cold_water_only = True
    control_profile = "extended_ht_stop"
    ht_feedback_verified = False
    stage_controls_verified = False
    cooling_trip_verified = False

    def __init__(self):
        self.sample, self.card_processes = _ram_sample()
        self.used = False
        self.second_read, self.release = threading.Event(), threading.Event()

    def isolation_snapshot(self):
        return dict(ownership_uncertain=False, worker_generation="a" * 32,
                    worker_state="IDLE_OWNED", active_request_id=None, resource_count=self.resource_count)

    def read_snapshot(self, cancel):
        if not self.used:
            self.used = True
            return copy.deepcopy(self.sample)
        self.second_read.set()
        self.release.wait(5.)
        raise AcquisitionCancelled()

    def close(self):
        self.resource_count = 0


class PerCardIntegrationTests(unittest.TestCase):
    def test_cold_backend_selects_reviewed_factory_only_after_initialize(self):
        with patch("legacy.xp_acq_control.elyse_agent.card_process_owner.create_card_process_tasks") as create:
            backend = CardBackend(native_isolation_mode="per_card")
            self.assertEqual(backend.resource_count, 0)
            self.assertIsNone(backend.card_processes)
            self.assertFalse(create.called)
            self.assertRaises(ValueError, backend.initialize, threading.Event())
            self.assertFalse(create.called)
        self.assertRaises(ValueError, CardBackend, native_isolation_mode="per_card", factory=lambda: None)

    def test_full_backend_source_images_fresh_ht_and_generation_bound_general_epoch(self):
        cancel, clock = threading.Event(), Clock()
        with patch("legacy.xp_acq_control.elyse_agent.card_process_owner.create_card_process_tasks",
                   side_effect=_private_process_factory) as create:
            backend = CardBackend(native_isolation_mode="per_card", operator_supervised_test=True,
                                  control_profile="extended_ht_stop", focal_command=Focal())
            backend.initialize(cancel, startup_confirmed=True)
        try:
            self.assertEqual(create.call_count, 1)
            self.assertIs(create.call_args[1]["authorized"], True)
            self.assertIs(create.call_args[1]["outputs_commissioned"], True)
            self.assertEqual(backend.resource_count, 21)
            self.assertTrue(backend.startup_complete)
            self.assertEqual(backend.started_counters, [0, 1, 2, 5, 6, 7])
            self.assertEqual(backend.commanded_digital, digital_startup_image())
            self.assertEqual(backend.owner.write_counter_ticks(0, 0, 31, 20)["legacy_start_count"], 1)
            process_fixture.wait_until(lambda: backend.owner.input_snapshot()["all_current"])
            sample = backend.read_snapshot(cancel)
            self.assertEqual(len(sample["banks"]), 6)
            self.assertEqual(sample["source"], "python_daqmx_acquisition")
            self.assertFalse(sample["simulated"])
            self.assertTrue(card_inputs_current(sample, backend.card_processes))
            self.assertEqual(generation_vector(sample["input_health"]), generation_vector(backend.card_processes))
            for name, device, count in AI_BANKS:
                row = sample["banks"][name]
                self.assertFalse(row["software_averaging"])
                self.assertEqual(row["legacy_scaled_values"], [value * backend.calibration[(name, index)][0]
                    + backend.calibration[(name, index)][1] for index, value in enumerate(row["values"])])

            # A 1.99-second old card cache must not acquire a fresh two-second
            # lifetime merely because the aggregate backend returned just now.
            aged_bundle = backend.owner.input_snapshot()
            for row in aged_bundle["banks"].values():
                row["age_seconds"] = 1.99
            with patch.object(backend.owner, "input_snapshot", return_value=aged_bundle):
                aged = backend.read_snapshot(cancel)
            # Allow floating subtraction error at a large monotonic epoch,
            # not a renewed sample lifetime (expiry is tested below).
            self.assertGreaterEqual(aged["source_age_seconds"], 1.99 - 1e-8)

            actual_fresh, foreground = backend.owner.fresh_input, {}
            def capture(card):
                foreground[card] = actual_fresh(card)
                return foreground[card]
            with patch.object(backend.owner, "fresh_input", side_effect=capture) as fresh:
                with patch.object(backend.owner, "input_snapshot", side_effect=AssertionError("HT must not use cached inputs")):
                    stop_sample = backend._read_ht_shutdown_sample()
            self.assertEqual([call[0][0] for call in fresh.call_args_list], [2, 4])
            raw = foreground[2]["sample"]["banks"]["C2_NI6071E_AI"]["values"][7]
            scale, offset = backend.calibration[("C2_NI6071E_AI", 7)]
            self.assertEqual(stop_sample["voltage_kv"], raw * scale + offset)
            self.assertFalse(stop_sample["raw_supply_contact"])
            self.assertTrue(stop_sample["supply_on"])
            self.assertLess(stop_sample["age_seconds"], 2.)

            # The existing runtime queues General; this test consumes its
            # private owner queue explicitly and executes the real source
            # procedure against the eleven RAM child processes.
            runtime = _runtime(backend, clock)
            _accept(runtime, clock, backend.read_snapshot(cancel))
            runtime.general_start(operator_confirmed=True)
            runtime._pending = None
            runtime._backend.general_start(cancel, operator_confirmed=True)
            runtime._state, runtime._operation = "RUNNING", None
            _accept(runtime, clock, backend.read_snapshot(cancel))
            self.assertTrue(runtime._supervised_general_current())
            self.assertTrue(command_capabilities(runtime.snapshot())["cooling.start"]["enabled"])

            before = backend.card_processes
            held = copy.deepcopy(runtime._latest)
            backend.owner.restart_card(1, affected_outputs_off_confirmed=True,
                expected_generation=before["cards"]["1"]["native"]["worker_generation"])
            process_fixture.wait_until(lambda: backend.owner.input_snapshot()["all_current"])
            after = backend.card_processes
            self.assertEqual(before["cards"]["10"]["native"]["worker_pid"],
                             after["cards"]["10"]["native"]["worker_pid"])
            self.assertEqual(before["cards"]["10"]["native"]["worker_generation"],
                             after["cards"]["10"]["native"]["worker_generation"])
            self.assertFalse(card_inputs_current(held, after))
            self.assertFalse(runtime._supervised_general_current())
            self.assertRaises(RuntimeError, runtime._require_current_owner_inputs,
                              runtime._received_at, "TEST_GENERATION")
            self.assertFalse(command_capabilities(runtime.snapshot())["cooling.start"]["enabled"])
            # New measurements alone cannot revive the old General/water epoch.
            _accept(runtime, clock, backend.read_snapshot(cancel))
            self.assertTrue(card_inputs_current(runtime._latest, after))
            self.assertFalse(runtime._supervised_general_current())
            self.assertFalse(command_capabilities(runtime.snapshot())["cooling.start"]["enabled"])
        finally:
            backend.close()
        self.assertEqual(backend.resource_count, 0)

    def test_runtime_preserves_1990ms_source_age_without_sleeping_for_expiry(self):
        clock, backend = Clock(), OneSampleBackend()
        runtime = _runtime(backend, clock)
        runtime.start()
        try:
            self.assertTrue(backend.second_read.wait(2.))
            before = runtime.snapshot()
            self.assertAlmostEqual(before["age_seconds"], 1.99)
            self.assertFalse(before["stale"])
            self.assertTrue(command_capabilities(before)["modulator.general.start"]["enabled"])
            clock.now += .02
            after = runtime.snapshot()
            self.assertAlmostEqual(after["age_seconds"], 2.01)
            self.assertTrue(after["stale"])
            self.assertFalse(command_capabilities(after)["modulator.general.start"]["enabled"])
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            backend.release.set()
            self.assertTrue(runtime.join(2.))


if __name__ == "__main__":
    unittest.main()
