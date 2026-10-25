"""Python 3.4 synchronization acceptance; injected owners, no NI or live I/O."""
import copy
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_counter_timing import (
    CounterTimingError, execute_remote_timing, validate_remote_timing,
)
from legacy.xp_acq_control.elyse_agent.acquisition_source_controls import SourceControls
from legacy.xp_acq_control.elyse_agent.command_protocol import validate_request
from legacy.xp_acq_control.elyse_agent.command_broker import CommandBroker
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities, require_command
from legacy.xp_acq_control.elyse_agent.acquisition_runtime import AcquisitionRuntime
from tests.unit.test_acq_experiment_commands import FakeCards, wait_running
from tests.unit.test_acq_control_release import AdmissionRuntime, ready_state


def timing(counter=0):
    return dict(counter=counter, delay_us=1.25, width_us=3.5)


def command(value):
    return dict(command_id="b" * 32, session_id="a" * 32, expected_revision=7,
                operation="counter_timing.set", operator_confirmed=True, value=value)


class InjectedOwner(object):
    def __init__(self):
        self.effects, self.fail = [], None
    def effect(self, name, *args):
        self.effects.append((name,) + args)
        if name == self.fail:
            raise IOError("synthetic partially applied property call")
    def read_counter_pulse_done(self, number):
        self.effect("done", number)
        return True
    def stop_counter(self, number):
        self.effect("stop", number)
    def write_counter_ticks(self, *args):
        self.effect("properties", *args)
    def start_counter(self, number):
        self.effect("start", number)


class InjectedBackend(SourceControls):
    stage_controls_verified = counter_timing_controls_verified = True
    control_profile = "legacy_full"
    def __init__(self):
        self.owner, self.started_counters = InjectedOwner(), [0, 3]
        self.commanded_digital = {"C4_DIO96_DO": [False] * 32}
        self._reset_source_controls()
        self.procedure = None
        self._ht_pulses_sequence_completed = True
    def _stage_require_initialized(self):
        pass
    def _ensure_focal_quiescent(self):
        pass
    def _retry_stage_restorations(self):
        pass
    def _retain_control_failure(self, error):
        self.procedure["report"] = copy.deepcopy(getattr(error, "report", {}))


class SynchronizationContractTests(unittest.TestCase):
    def test_exact_pair_no_raw_bank_c11_selector_or_nonfinite(self):
        for counter in range(8):
            self.assertEqual(validate_remote_timing(timing(counter)), timing(counter))
        invalid = [None, [], dict(timing(), counter=True), dict(timing(), counter=8),
                   dict(timing(), counter=-1), dict(timing(), counter=1.5), dict(timing(), selector=1),
                   dict(timing(), delay_us=0), dict(timing(), width_us=-1),
                   dict(timing(), delay_us=float("nan")), dict(timing(), width_us=float("inf")),
                   dict(timing(), width_us=True), dict(timing(), delay_us="1"),
                   dict(timing(), delay_us=.025), dict(timing(), width_us=1e12),
                   dict(timing(), delay_us=10 ** 400)]
        for value in invalid:
            with self.assertRaises(ValueError):
                validate_remote_timing(value)
        value = timing()
        normalized = validate_request(command(value))
        value["delay_us"] = 99
        self.assertEqual(normalized["value"]["delay_us"], 1.25)

    def test_exact_argument_survives_broker_and_changed_value_cannot_replay(self):
        runtime = AdmissionRuntime()
        broker = CommandBroker(runtime, enabled=True)
        request = command(timing())
        result = broker.submit(request, broker.snapshot(issue_lease=True)["lease"])
        self.assertEqual(result["outcome"], "QUEUED")
        request["value"]["delay_us"] = 99
        with self.assertRaises(ValueError):
            broker.submit(request, None)
        self.assertEqual(broker.records[request["command_id"]]["request"]["value"]["delay_us"], 1.25)
        self.assertEqual(len(runtime.calls), 1)

    def test_policy_requires_qualification_current_inputs_cooling_and_running_selection(self):
        value = ready_state()
        value["stage_execution"]["counter_timing_commissioned"] = True
        value["counter_timing_state"] = dict(running_counters=[0, 2])
        require_command(value, "counter_timing.set", timing())
        with self.assertRaises(RuntimeError):
            require_command(value, "counter_timing.set", timing(3))
        for field in ("counter_timing_commissioned", "commissioned"):
            altered = copy.deepcopy(value)
            altered["stage_execution"][field] = False
            self.assertFalse(command_capabilities(altered)["counter_timing.set"]["enabled"])
        for fields in (dict(stale=True), dict(general_cooling_ready=False), dict(cooling_permit_current=False),
                       dict(full_stop_commissioned=False), dict(state="FAULT")):
            altered = dict(value, **fields)
            self.assertFalse(command_capabilities(altered)["counter_timing.set"]["enabled"])


class SynchronizationOwnerTests(unittest.TestCase):
    def test_existing_local_full_bank_api_still_returns_and_publishes_source_report(self):
        backend = InjectedBackend()
        image = [0.] * 33
        image[0], image[1], image[32] = 1.25, 3.5, 1.
        report = backend.configure_counter_timing(tuple(image), threading.Event(), operator_confirmed=True)
        self.assertTrue(report["completed"])
        self.assertEqual(backend.counter_timing_publication["values"][0:2], (1.25, 3.5))
        self.assertEqual(backend.counter_timing_publication["values"][32], -1.)

    def test_vi_order_quantization_and_no_fabricated_shared_bank(self):
        backend = InjectedBackend()
        original = tuple(float(index) for index in range(33))
        backend._counter_timing_bank = original
        report = backend.configure_sync_parameters(dict(counter=0, delay_us=.075, width_us=.125),
            threading.Event(), operator_confirmed=True)
        self.assertEqual(backend.owner.effects, [("done", 0), ("stop", 0), ("properties", 0, 2, 2, 2), ("start", 0)])
        self.assertEqual(backend._counter_timing_bank, original)
        self.assertIsNone(backend.counter_timing_publication)
        self.assertTrue(report["request_image_only"])
        self.assertFalse(report["shared_bank_published"])
        self.assertNotIn("publication_snapshot", report)
        self.assertEqual(backend.commanded_counter_ticks[0]["high_ticks"], 2)

    def test_stopped_counter_is_not_started_by_timing_configuration(self):
        backend = InjectedBackend()
        with self.assertRaises(RuntimeError):
            backend.configure_sync_parameters(timing(4), threading.Event(), operator_confirmed=True)
        self.assertEqual(backend.owner.effects, [])

    def test_partial_property_failure_keeps_owner_and_uncertainty_without_restart(self):
        backend = InjectedBackend()
        backend.owner.fail = "properties"
        with self.assertRaises(CounterTimingError):
            backend.configure_sync_parameters(timing(3), threading.Event(), operator_confirmed=True)
        self.assertEqual(backend._counter_configuration_uncertain, {3})
        self.assertNotIn(3, backend.started_counters)
        self.assertNotIn(3, backend.commanded_counter_ticks)
        self.assertFalse(any(item[0] == "start" for item in backend.owner.effects))
        self.assertTrue(backend.last_counter_timing["configuration_uncertain"])
        self.assertIsNotNone(backend.owner)

    def test_cancelled_pair_does_not_stop_or_restart(self):
        owner = InjectedOwner()
        with self.assertRaises(CounterTimingError):
            execute_remote_timing(timing(), owner.read_counter_pulse_done, owner.stop_counter,
                owner.write_counter_ticks, owner.start_counter, lambda seconds: None, lambda: True)
        self.assertEqual(owner.effects, [])


class RuntimeCards(FakeCards):
    counter_timing_controls_verified = True
    def __init__(self):
        FakeCards.__init__(self)
        self.started_counters = [0, 3]
        self.commanded_counter_ticks = {}
    def configure_sync_parameters(self, value, cancel, operator_confirmed=False):
        self.calls.append(("counter_timing.set", dict(value), threading.current_thread().ident))


class SynchronizationRuntimeTests(unittest.TestCase):
    def test_aged_admission_observation_is_rechecked_before_owner_callback(self):
        clock = [10.]
        cards = RuntimeCards()
        runtime = AcquisitionRuntime(lambda: cards, period=.02, clock=lambda: clock[0])
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            wait_running(runtime)
            with runtime._lock:
                runtime.set_sync_parameters(timing(), operator_confirmed=True)
                clock[0] += 3
            wait_running(runtime, state="FAULT")
            self.assertEqual(cards.calls, [])
            self.assertIn("COUNTER_TIMING_REQUIRES_FRESH_CURRENT_OWNER_INPUTS", runtime.snapshot()["error"])
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(2))

    def test_general_stop_supersedes_queued_pair_without_properties_or_restart(self):
        cards = RuntimeCards()
        runtime = AcquisitionRuntime(lambda: cards, period=.02)
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            wait_running(runtime)
            with runtime._lock:
                runtime.set_sync_parameters(timing(), operator_confirmed=True)
                runtime.general_stop(operator_confirmed=True)
            wait_running(runtime)
            self.assertEqual([item[0] for item in cards.calls], ["general.stop"])
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(2))

    def test_pair_is_copied_and_runs_on_existing_owner_and_rejects_stopped(self):
        cards = RuntimeCards()
        runtime = AcquisitionRuntime(lambda: cards, period=.02)
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            wait_running(runtime)
            with self.assertRaises(RuntimeError):
                runtime.set_sync_parameters(timing(4), operator_confirmed=True)
            with runtime._lock:
                value = timing()
                runtime.set_sync_parameters(value, operator_confirmed=True)
                value["delay_us"] = 99
            wait_running(runtime)
            self.assertEqual(cards.calls[0][1]["delay_us"], 1.25)
            self.assertEqual(cards.calls[0][2], runtime._thread.ident)
            self.assertEqual(runtime.snapshot()["counter_timing_stop_required"], [0])
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(2))


if __name__ == "__main__":
    unittest.main()
