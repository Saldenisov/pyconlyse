"""Execution telemetry: mocked NI owner, real3.4 subprocesses, no devices.

Source procedure effect/timing proofs remain in the source executor suites.
These tests prove transport, ownership generation and independent clocks.
"""
import copy
import io
import math
import threading
import time
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_backend import AcquisitionCancelled
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_control.elyse_agent.cooperative_execution import CooperativeExecution
from legacy.xp_acq_control.elyse_agent.hardware_plan import AI_BANKS, DI_BANKS
from legacy.xp_acq_control.elyse_agent.isolated_backend import IsolatedCardBackend
from legacy.xp_acq_control.elyse_agent.isolated_worker import Worker
from legacy.xp_acq_control.elyse_agent.isolated_wire import encode_frame
from legacy.xp_acq_control.elyse_agent.telemetry_publisher import StandardTelemetryPublisher


def native_sample(value=1.):
    banks = {}
    for name, device, count in AI_BANKS:
        banks[name] = dict(kind="analog_input", device=device, values=[value] * count,
                           legacy_scaled_values=[value] * count)
    for name, device, first, last, count in DI_BANKS:
        banks[name] = dict(kind="digital_input", device=device, values=[False] * count)
    for index in (1, 4, 7, 10):
        banks["C3_DIO96_DI"]["values"][index] = True
    return dict(source="python_daqmx_acquisition", simulated=False, banks=banks,
                commanded_digital={}, commanded_analog_logical={})


def software_event(revision=1, eps=True, dps=True):
    ep, dp = [False] * 77, [False] * 29
    ep[14], dp[5] = eps, dps
    return dict(kind="SOFTWARE_STATE_NOT_MEASUREMENT", simulated=False, hardware_acknowledged=False,
                safe_to_sample=False, software_state=dict(revision=revision, EPS=tuple(ep), DPS=tuple(dp)))


def wait_until(predicate, timeout=4):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("Driver-free execution condition not reached")


class RAMBackend(object):
    resource_count = 2
    control_profile = "legacy_full"
    stage_controls_verified = True
    cooling_trip_verified = False
    def __init__(self, events=(), hook=None):
        self.events, self.hook, self.observer = list(events), hook, None
        self.procedure = None
    def set_execution_observer(self, observer):
        self.observer = observer
    def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
        for event in self.events:
            self.observer(copy.deepcopy(event))
        if self.hook is not None:
            self.hook(self)
    def close(self):
        self.resource_count = 0


class ExecutionFixtureBackend(object):
    """Importable child fixture with no driver imports or hardware methods."""
    def __init__(self):
        self.resource_count, self.procedure = 0, None
        self.control_profile, self.stage_controls_verified = "legacy_full", True
        self.cooling_trip_verified = False
        self._stage_simulated, self._revision, self._value = False, 0, 0.
        self._eps, self._dps = [False] * 77, [False] * 29
        self._observer = None
        self.owner = threading.current_thread().ident
    def set_execution_observer(self, observer):
        self._observer = observer
    def initialize(self, cancel, startup_confirmed=False):
        assert startup_confirmed and not cancel.is_set()
        self.resource_count, self._revision = 2, 1
    def get_software_state(self):
        if not self.resource_count:
            raise RuntimeError("Cold fixture software state unavailable")
        return dict(revision=self._revision, EPS=tuple(self._eps), DPS=tuple(self._dps))
    def read_snapshot(self, cancel):
        assert threading.current_thread().ident == self.owner
        if cancel.is_set():
            raise AcquisitionCancelled()
        self._value += 1.
        return native_sample(self._value)
    def execution_sample_budget_seconds(self):
        return 2.
    def read_snapshot_for_execution(self, cancel, deadline):
        assert time.monotonic() < deadline
        return self.read_snapshot(cancel)
    def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
        assert threading.current_thread().ident == self.owner
        assert operator_confirmed
        self._revision += 1
        self._eps[14], self._dps[4] = False, True
        self._observer(dict(software_event(self._revision), software_state=self.get_software_state()))
        scheduler = CooperativeExecution(self._observer, interval_seconds=.03)
        scheduler.wait(3.2, cancel.wait, safe_to_sample=True,
                       phase=dict(operation=operation, phase="offline_mock_safe_wait"))
        if not cancel.is_set():
            self._revision += 1
            self._eps[14], self._dps[4] = True, False
            self._observer(dict(software_event(self._revision), software_state=self.get_software_state()))
    def close(self):
        self.resource_count = 0


class ExecutionRuntimeTests(unittest.TestCase):
    def runtime(self, backend=None):
        self.now = [100.]
        backend = backend or RAMBackend()
        runtime = AcquisitionControlRuntime(lambda: backend, clock=lambda: self.now[0])
        wrapper = _ObservedBackend(backend, runtime)
        runtime._backend, runtime._state = wrapper, "EXECUTING"
        runtime._operation, runtime._state_revision = "acq.stage.chauffage.start", 7
        return runtime, wrapper, backend

    def test_real_complete_sample_is_current_during_executing(self):
        event = dict(sample=native_sample(), sample_age_seconds=.1, safe_to_sample=True)
        runtime, wrapper, backend = self.runtime(RAMBackend([event]))
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        for state in (runtime.snapshot(), runtime.try_telemetry_snapshot()):
            self.assertEqual(state["state"], "EXECUTING")
            self.assertFalse(state["stale"])
            self.assertTrue(state["measurement_current"])
            self.assertAlmostEqual(state["age_seconds"], .1)
        self.assertEqual(runtime._sequence, 1)

    def test_status_clock_and_sequence_never_refresh_measurement_clock(self):
        event = dict(sample=native_sample(), sample_age_seconds=.1, safe_to_sample=True)
        runtime, wrapper, backend = self.runtime(RAMBackend([event, software_event()]))
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        received, sequence = runtime._received_at, runtime._sequence
        self.now[0] += 3.
        backend.events = [software_event(2)]
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        state = runtime.try_telemetry_snapshot()
        self.assertEqual((runtime._received_at, runtime._sequence), (received, sequence))
        self.assertTrue(state["stale"])
        self.assertTrue(state["software_state_current"])
        self.assertEqual(state["software_state_sequence"], 2)
        self.assertEqual(state["software_state"]["source_revision"], 2)
        self.assertAlmostEqual(state["software_state_age_seconds"], 0.)

    def test_transported_software_age_is_preserved_and_invalid_age_rejected(self):
        runtime, wrapper, backend = self.runtime(RAMBackend([dict(software_event(), software_state_age_seconds=3.)]))
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        self.assertAlmostEqual(runtime.snapshot()["software_state_age_seconds"], 3.)
        sequence = runtime._software_sequence
        for age in (-1., float("nan"), float("inf"), True):
            backend.events = [dict(software_event(2), software_state_age_seconds=age)]
            wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
            self.assertEqual(runtime._software_sequence, sequence)
            self.assertFalse(runtime.try_telemetry_snapshot()["software_state_current"])

    def test_progress_only_never_refreshes_input_or_software_time(self):
        runtime, wrapper, backend = self.runtime(RAMBackend([dict(phase="heartbeat", safe_to_sample=True)]))
        runtime._latest, runtime._received_at = native_sample(), 99.
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        self.assertEqual((runtime._sequence, runtime._received_at), (0, 99.))
        self.assertIsNone(runtime._software_received_at)

    def test_regressed_software_revision_invalidates_current_proof_but_identical_heartbeat_reproves(self):
        runtime, wrapper, backend = self.runtime(RAMBackend([software_event(5)]))
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        sequence, received = runtime._software_sequence, runtime._software_received_at
        self.now[0] += 1.
        backend.events = [software_event(4)]
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        state = runtime.try_telemetry_snapshot()
        self.assertFalse(state["software_state_current"])
        self.assertEqual(state["software_state_error"], "SOFTWARE_STATE_REVISION_REGRESSED")
        self.assertEqual(state["software_state"]["source_revision"], 5)
        self.assertEqual((runtime._software_sequence, runtime._software_received_at), (sequence, received))
        backend.events = [software_event(5)]
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        self.assertTrue(runtime.try_telemetry_snapshot()["software_state_current"])
        self.assertEqual(runtime._software_sequence, sequence + 1)

    def test_partial_slow_nonfinite_failed_unsafe_and_cancelled_samples_unavailable(self):
        partial = native_sample()
        partial["banks"].pop("C11_NI6220_AI")
        cases = [dict(sample=partial, sample_age_seconds=0., safe_to_sample=True),
                 dict(sample=native_sample(), sample_age_seconds=2., safe_to_sample=True),
                 dict(sample=native_sample(), sample_age_seconds=float("nan"), safe_to_sample=True),
                 dict(sample=native_sample(), sample_age_seconds=0., safe_to_sample=False),
                 dict(sample_error=dict(type="TimeoutError", message="offline"), safe_to_sample=True)]
        for event in cases:
            runtime, wrapper, backend = self.runtime(RAMBackend([event]))
            runtime._latest, runtime._received_at = native_sample(), 100.
            wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
            self.assertIsNone(runtime._received_at)
            self.assertTrue(runtime.try_telemetry_snapshot()["stale"])

    def test_superseded_start_cannot_freshen_new_stop_or_its_software_state(self):
        def supersede(backend):
            AcquisitionRuntime.general_stop(runtime, operator_confirmed=True)
            backend.observer(dict(sample=native_sample(9.), sample_age_seconds=0., safe_to_sample=True))
            backend.observer(software_event(9))
        runtime, wrapper, backend = self.runtime(RAMBackend(hook=supersede))
        runtime._latest, runtime._received_at = native_sample(), 100.
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        self.assertEqual(runtime._operation, "modulator.general.stop")
        self.assertIsNone(runtime._received_at)
        self.assertEqual(runtime._sequence, 0)
        self.assertIsNone(runtime._software_state)

    def test_general_admissions_immediately_invalidate_precommand_measurement(self):
        for operation in ("general_start", "general_stop"):
            runtime, wrapper, backend = self.runtime()
            runtime._state, runtime._operation = "RUNNING", None
            runtime._latest, runtime._received_at = native_sample(), 100.
            getattr(AcquisitionRuntime, operation)(runtime, operator_confirmed=True)
            self.assertIsNone(runtime._received_at)
            self.assertTrue(runtime.try_telemetry_snapshot()["stale"])

    def test_read_superseded_before_entry_uses_acquisition_cancel_and_preserves_pending_command(self):
        runtime, wrapper, backend = self.runtime()
        runtime._state, runtime._operation = "RUNNING", None
        runtime.stage_request("chauffage.start", operator_confirmed=True)
        with self.assertRaises(AcquisitionCancelled):
            wrapper.read_snapshot(runtime._cancel)
        self.assertEqual(runtime._pending, "stage")
        self.assertEqual(runtime._operation, "acq.stage.chauffage.start")

    def test_wrong_worker_generation_and_old_session_observations_rejected(self):
        class IsolatedRAM(RAMBackend):
            def isolation_snapshot(self):
                return dict(worker_generation="current", ownership_uncertain=False)
        events = [dict(sample=native_sample(), sample_age_seconds=0., safe_to_sample=True,
                       worker_generation="old")]
        runtime, wrapper, backend = self.runtime(IsolatedRAM(events))
        wrapper.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        self.assertEqual(runtime._sequence, 0)
        context = dict(session_id="0" * 32, state_revision=7,
                       operation=runtime._operation, backend_identity=id(backend))
        runtime.observe_execution(dict(events[0], worker_generation="current", runtime_operation_context=context))
        self.assertEqual(runtime._sequence, 0)


class WorkerBudgetTests(unittest.TestCase):
    def worker(self, configured=2., elapsed=.1, failure=False):
        self.now, frames, calls = [100.], [], []
        class Backend(object):
            resource_count = 2
            def execution_sample_budget_seconds(self):
                return 3.05  # Six configured .5s reads plus accounting margin.
            def read_snapshot_for_execution(inner, cancel, deadline):
                calls.append((threading.current_thread().ident, deadline))
                self.now[0] += elapsed
                if failure:
                    raise TimeoutError("Offline deadline read")
                return native_sample()
        worker = Worker(io.BytesIO(), io.BytesIO())
        worker.backend, worker.active_id = Backend(), 1
        worker.configuration = dict(safe_sample_budget_seconds=configured)
        worker._emit = lambda message, reliable=False: frames.append(copy.deepcopy(message))
        return worker, frames, calls

    def test_none_never_enables_reads_and_configured_budget_cannot_shrink_derived_budget(self):
        for configured, remaining in ((None, 30.), (2., 3.)):
            worker, frames, calls = self.worker(configured)
            with mock.patch("legacy.xp_acq_control.elyse_agent.isolated_worker.time.monotonic", lambda: self.now[0]):
                worker._observe(dict(safe_to_sample=True, remaining_seconds=remaining))
            self.assertEqual(calls, [])
            self.assertNotIn("sample", frames[-1]["event"])

    def test_qualified_deadline_read_runs_same_owner_and_late_or_error_result_discarded(self):
        for elapsed, failure, valid in ((.1, False, True), (4., False, False), (.1, True, False)):
            worker, frames, calls = self.worker(elapsed=elapsed, failure=failure)
            with mock.patch("legacy.xp_acq_control.elyse_agent.isolated_worker.time.monotonic", lambda: self.now[0]):
                worker._observe(dict(safe_to_sample=True, remaining_seconds=4., minimum_next_action_deadline=104.))
            self.assertEqual(calls[0][0], threading.current_thread().ident)
            self.assertAlmostEqual(calls[0][1], 103.95)
            self.assertEqual("sample" in frames[-1]["event"], valid)
            self.assertEqual("sample_error" in frames[-1]["event"], not valid)

    def test_software_events_and_unsafe_pulse_span_never_read_cards(self):
        worker, frames, calls = self.worker()
        worker._observe(dict(software_event(), remaining_seconds=30.))
        worker._observe(dict(safe_to_sample=False, remaining_seconds=30.))
        self.assertEqual(calls, [])

    def test_software_outbox_and_parent_inbox_are_independent_from_heartbeat_slots(self):
        worker = Worker(io.BytesIO(), io.BytesIO())
        worker._emit(dict(kind="progress", id=1, event=dict(kind="HEARTBEAT")))
        worker._emit(dict(kind="progress", id=1, event=dict(kind="HEARTBEAT")))
        worker._emit(dict(kind="progress", id=1, event=software_event(1)))
        worker._emit(dict(kind="progress", id=1, event=software_event(2)))
        self.assertEqual(worker.outgoing.qsize(), 2)
        self.assertEqual(worker.software_pending[0]["event"]["software_state"]["revision"], 2)
        messages = [dict(kind="progress", id=1, event=software_event(1))]
        messages += [dict(kind="progress", id=1, event=dict(kind="HEARTBEAT", index=i)) for i in range(50)]
        messages.append(dict(kind="progress", id=1, event=software_event(2)))
        messages += [dict(kind="progress", id=1, event=dict(kind="HEARTBEAT", index=i)) for i in range(50)]
        class PipeFixture(object):
            stdout = io.BytesIO(b"".join(encode_frame(message) for message in messages))
        proxy = IsolatedCardBackend(backend_factory=ExecutionFixtureBackend)
        proxy._process, proxy._active_id, proxy._active_operation = PipeFixture(), 1, "execute_stage"
        proxy._read_loop()  # EOF faults this inert pipe; no subprocess created.
        self.assertEqual(proxy._software_progress["software_state"]["revision"], 2)
        self.assertEqual(proxy._software_version, 2)
        self.assertEqual(proxy._progress["kind"], "HEARTBEAT")

    def test_request_duration_anchor_preserves_queue_and_pipe_delay_without_shared_epochs(self):
        observations = []
        proxy = IsolatedCardBackend(backend_factory=ExecutionFixtureBackend, progress_observer=observations.append)
        proxy._active_id = 1
        event = dict(sample=native_sample(), sample_age_seconds=.1,
            sample_started_after_request_seconds=.5, observation_after_request_seconds=.6,
            parent_request_started_monotonic=100., parent_received_monotonic=102.)
        with mock.patch("legacy.xp_acq_control.elyse_agent.isolated_backend.time.monotonic", lambda: 104.):
            proxy._observe_progress(event)
            proxy._observe_progress(dict(software_event(), software_state_age_seconds=.1,
                software_observed_after_request_seconds=.5, observation_after_request_seconds=.6,
                parent_request_started_monotonic=100., parent_received_monotonic=102.))
        self.assertAlmostEqual(observations[0]["sample_age_seconds"], 3.5)
        self.assertAlmostEqual(observations[1]["software_state_age_seconds"], 3.5)

    def test_missing_invalid_or_future_relative_duration_cannot_freshen_sample(self):
        observations = []
        proxy = IsolatedCardBackend(backend_factory=ExecutionFixtureBackend, progress_observer=observations.append)
        proxy._active_id = 1
        for offset in (None, -1., float("nan"), float("inf"), 5.):
            event = dict(sample=native_sample(), sample_age_seconds=.01,
                sample_started_after_request_seconds=offset, observation_after_request_seconds=.6,
                parent_request_started_monotonic=100., parent_received_monotonic=104.)
            with mock.patch("legacy.xp_acq_control.elyse_agent.isolated_backend.time.monotonic", lambda: 104.):
                proxy._observe_progress(event)
            self.assertNotIn("sample", observations[-1])
            self.assertEqual(observations[-1]["sample_error"]["type"], "InvalidSamplingProvenance")


class RuntimePublisherIntegrationTests(unittest.TestCase):
    def test_accepted_close_during_start_return_blocks_late_sample_and_cooling_chain(self):
        entered, release = threading.Event(), threading.Event()
        class Backend(RAMBackend):
            def __init__(self):
                RAMBackend.__init__(self)
                self.resource_count, self.close_calls, self.stage_calls = 0, 0, []
            def initialize(self, cancel, startup_confirmed=False):
                self.resource_count = 2
            def read_snapshot(self, cancel):
                if cancel.is_set():
                    raise AcquisitionCancelled()
                return native_sample()
            def general_start(self, cancel, operator_confirmed=False):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("Offline start race was not released")
                self.observer(dict(sample=native_sample(99.), sample_age_seconds=0., safe_to_sample=True))
            def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
                self.stage_calls.append(operation)
            def close(self):
                self.close_calls += 1
                self.resource_count = 0
        backend = Backend()
        runtime = AcquisitionControlRuntime(lambda: backend, period=.02)
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            wait_until(lambda: runtime.snapshot()["state"] == "RUNNING" and runtime._sequence > 0)
            # Test bypasses only physical commissioning of a RAM fixture; the
            # actual owner loop, observed wrapper and lifecycle remain real.
            AcquisitionRuntime.general_start(runtime, operator_confirmed=True)
            self.assertTrue(entered.wait(3))
            runtime.request_shutdown(electrical_off_confirmed=True)
            before = runtime._sequence
            release.set()
            self.assertTrue(runtime.join(4))
            self.assertEqual(runtime._sequence, before)
            self.assertEqual(backend.stage_calls, [])
            self.assertEqual(backend.close_calls, 1)
            self.assertEqual(runtime.snapshot()["state"], "STOPPED")
        finally:
            release.set()
            if runtime._thread.is_alive():
                runtime.request_shutdown(electrical_off_confirmed=True)
                runtime.join(4)

    def test_real_runtime_child_publisher_updates_inputs_and_eps_dps_during_long_command(self):
        backend = IsolatedCardBackend(backend_factory=ExecutionFixtureBackend, safe_sample_budget_seconds=2.)
        runtime = AcquisitionControlRuntime(lambda: backend, period=.02)
        publisher = StandardTelemetryPublisher(runtime, ("127.0.0.1", 1), b"offline-execution-telemetry-key-000000")
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            wait_until(lambda: runtime.snapshot()["state"] == "RUNNING" and runtime._sequence > 0)
            runtime.stage_request("chauffage.start", operator_confirmed=True)
            wait_until(lambda: runtime.try_telemetry_snapshot()["measurement_current"] is True
                       and runtime.snapshot()["state"] == "EXECUTING")
            before = runtime._sequence
            self.assertTrue(publisher.publish_once())
            envelope = publisher.outbox.peek()
            packet = envelope["packet"]
            banks = {row["publication"]: row for row in packet["data"]["banks"]}
            self.assertEqual(len(banks), 27)
            self.assertIsNotNone(banks["C1NI6071E"]["data"])
            self.assertFalse(banks["EPS"]["data"][14])
            self.assertTrue(banks["DPS"]["data"][4])
            publisher.outbox.acknowledge(envelope["relay_id"], envelope["message_id"])
            wait_until(lambda: runtime._sequence > before and runtime.snapshot()["state"] == "EXECUTING")
            self.assertTrue(publisher.publish_once())
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)  # RAM fixture only.
            self.assertTrue(runtime.join(5))
            publisher.close()


if __name__ == "__main__":
    unittest.main()
