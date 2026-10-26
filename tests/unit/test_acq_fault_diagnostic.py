"""Settled fault input readback without hardware, subprocesses or networking."""
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_backend import AcquisitionCancelled
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.acquisition_procedures import GeneralStopError
from legacy.xp_acq_control.elyse_agent.hardware_plan import AI_BANKS, DI_BANKS
from legacy.xp_acq_control.elyse_agent.standard_banks import INPUTS, standard_packet


def sample(value):
    banks = {}
    for name, device, count in AI_BANKS:
        banks[name] = dict(kind="analog_input", device=device, values=[value] * count,
                           legacy_scaled_values=[value] * count)
    for name, device, first, last, count in DI_BANKS:
        banks[name] = dict(kind="digital_input", device=device, values=[False] * count)
    for index in (1, 4, 7, 10):
        banks["C3_DIO96_DI"]["values"][index] = True
    return dict(source="python_daqmx_acquisition", simulated=False, banks=banks)


class Backend(object):
    resource_count = 21
    startup_complete = True
    control_profile = "legacy_full"
    stage_controls_verified = True
    cooling_trip_verified = False

    def __init__(self):
        self.generation, self.worker_state = "same-owner", "IDLE_OWNED"
        self.uncertain, self.request_id = False, None
        self.calls, self.hook, self.observer = [], None, None
        self.stop_failure = RuntimeError("explicit stop remains incomplete")

    def isolation_snapshot(self):
        return dict(worker_generation=self.generation, worker_state=self.worker_state,
            ownership_uncertain=self.uncertain, active_request_id=self.request_id,
            resource_count=self.resource_count)

    def set_execution_observer(self, observer):
        self.observer = observer

    def read_snapshot(self, cancel):
        self.calls.append("read")
        if self.hook is not None:
            self.hook(cancel)
        if cancel.is_set():
            raise AcquisitionCancelled()
        return sample(float(self.calls.count("read")))

    def general_stop(self, operator_confirmed=False):
        self.calls.append("general_stop")
        raise self.stop_failure

    def execute_stage(self, *args, **kwargs):
        self.calls.append("stage")

    def close(self):
        self.calls.append("close")
        self.resource_count = 0


class Wake(object):
    def __init__(self, runtime, cycles, after_cycle=None):
        self.runtime, self.cycles, self.after_cycle = runtime, cycles, after_cycle
        self.views = []

    def wait(self, seconds):
        self.views.append(self.runtime.snapshot())
        if self.after_cycle is not None:
            self.after_cycle(len(self.views))
        if len(self.views) >= self.cycles:
            self.runtime._state = "STOPPED"  # End deterministic owner loop without cleanup.

    def clear(self):
        pass

    def set(self):
        pass


class FaultDiagnosticTests(unittest.TestCase):
    def make_runtime(self):
        backend = Backend()
        runtime = AcquisitionControlRuntime(lambda: backend, clock=lambda: 100., remote_enabled=True)
        runtime._backend = _ObservedBackend(backend, runtime)
        runtime._state = "RUNNING"
        runtime._general_stop_required = True
        runtime._procedure_fault(RuntimeError("cooling timeout and partial stop"))
        return runtime, backend

    def run_cycles(self, runtime, cycles=3, after_cycle=None):
        wake = Wake(runtime, cycles, after_cycle)
        runtime._wake = wake
        runtime._run()
        return wake.views

    def test_repeated_fault_reads_keep_fault_sticky_and_starts_blocked(self):
        runtime, backend = self.make_runtime()
        original_error, original_revision = runtime._error, runtime._state_revision
        self.assertFalse(runtime.snapshot()["fault_diagnostic_measurement"]["current"])
        views = self.run_cycles(runtime)
        self.assertEqual(backend.calls, ["read"] * 3)
        for index, view in enumerate(views, 1):
            evidence = view["fault_diagnostic_measurement"]
            self.assertEqual((view["state"], view["error"], view["state_revision"]),
                             ("FAULT", original_error, original_revision))
            self.assertTrue(view["stale"])
            self.assertFalse(view["measurement_current"])
            self.assertTrue(evidence["current"])
            self.assertEqual(evidence["sequence"], index)
            self.assertEqual(evidence["sequence"], view["sequence"])
            self.assertEqual(evidence["session_id"], view["session_id"])
            self.assertEqual(evidence["age_seconds"], view["age_seconds"])
            self.assertEqual(evidence["worker_generation"], backend.generation)
            self.assertEqual(evidence["source"], "settled_fault_owner_readback")
            self.assertFalse(evidence["command_admission"])
            self.assertEqual(view["latest"]["banks"][AI_BANKS[0][0]]["values"][0], float(index))
            for operation, capability in view["control"]["capabilities"].items():
                if operation.endswith(".start") or operation.endswith(".reset") or operation.endswith(".set"):
                    self.assertFalse(capability["enabled"], operation)

    def test_uncertain_pending_hung_cancelled_incomplete_and_changed_owner_do_not_read(self):
        for case in ("uncertain", "request", "hung", "cancel", "startup", "recovery", "generation", "operation"):
            runtime, backend = self.make_runtime()
            if case == "uncertain": backend.uncertain = True
            elif case == "request": backend.request_id = 7
            elif case == "hung": backend.worker_state = "EXECUTING_GENERAL_STOP"
            elif case == "cancel": runtime._cancel.set()
            elif case == "startup": backend.startup_complete = False
            elif case == "recovery": runtime._recovery_latched = True
            elif case == "generation": backend.generation = "unexpected-replacement"
            else: runtime._operation = "modulator.general.stop"
            views = self.run_cycles(runtime)
            self.assertEqual(backend.calls, [], case)
            self.assertTrue(all(not view["fault_diagnostic_measurement"]["current"] for view in views), case)
            if case == "cancel": self.assertTrue(runtime._cancel.is_set())

    def test_pending_priority_stop_runs_without_diagnostic_read(self):
        runtime, backend = self.make_runtime()
        runtime.general_stop(operator_confirmed=True)
        self.run_cycles(runtime, cycles=1)
        self.assertEqual(backend.calls, ["general_stop"])

    def test_confirmed_close_and_shutdown_keep_lifecycle_priority(self):
        runtime, backend = self.make_runtime()
        runtime.deinitialize(electrical_off_confirmed=True)
        views = self.run_cycles(runtime, cycles=1)
        self.assertEqual(backend.calls, ["close"])
        self.assertEqual(views[0]["state"], "IDLE")
        self.assertFalse(views[0]["fault_diagnostic_measurement"]["current"])
        runtime, backend = self.make_runtime()
        runtime.request_shutdown(electrical_off_confirmed=True)
        runtime._run()
        self.assertEqual(backend.calls, ["close"])
        self.assertEqual(runtime._state, "STOPPED")

    def test_priority_stop_interrupts_read_and_superseded_sample_is_discarded(self):
        runtime, backend = self.make_runtime()
        backend.hook = lambda cancel: runtime.general_stop(operator_confirmed=True)
        views = self.run_cycles(runtime, cycles=2)
        self.assertEqual(backend.calls, ["read", "general_stop"])
        self.assertEqual(runtime._sequence, 0)
        self.assertIsNone(runtime._latest)
        self.assertFalse(any(view["fault_diagnostic_measurement"]["current"] for view in views))

    def test_diagnostic_failure_preserves_original_fault_and_does_not_retry_or_close(self):
        runtime, backend = self.make_runtime()
        original_error = runtime._error
        def fail(cancel):
            backend.observer(dict(sample=sample(99.), sample_age_seconds=0., safe_to_sample=True))
            raise IOError("diagnostic read failed")
        backend.hook = fail
        views = self.run_cycles(runtime)
        self.assertEqual(backend.calls, ["read"])
        self.assertEqual(runtime._sequence, 0)
        self.assertIsNone(runtime._latest)
        self.assertTrue(all(view["error"] == original_error for view in views))
        self.assertTrue(all(not view["fault_diagnostic_measurement"]["current"] for view in views))
        self.assertIn("diagnostic read failed", views[-1]["fault_diagnostic_measurement"]["error"])

    def test_cooling_trip_partial_chroma_stop_remains_failed_without_repeat_stop(self):
        runtime, backend = self.make_runtime()
        now = [100.]
        runtime._clock = runtime.cooling.clock = lambda: now[0]
        runtime._state, runtime._error = "RUNNING", ""
        backend.operator_supervised_test = backend.operator_test_cold_attested = True
        backend.stop_failure = GeneralStopError(["Focales OFF: Chroma unavailable"])
        for at in (100., 101., 102.):
            now[0] = at
            runtime._sequence += 1
            runtime._latest, runtime._received_at = sample(1.), at
            runtime._run_cooling_guard(runtime._latest)
        faulty = sample(1.)
        for index in (0, 6):
            faulty["banks"]["C3_DIO96_DI"]["values"][index] = True
        runtime._latest, runtime._received_at = faulty, now[0]
        runtime._run_cooling_guard(faulty)
        self.assertTrue(runtime.cooling.snapshot()["active"])
        self.assertFalse(runtime._stop_qualified())
        now[0] += 120.
        runtime._tick_cooling()
        self.assertEqual(runtime._pending, "general_stop")
        views = self.run_cycles(runtime, cycles=4,
            after_cycle=lambda unused: runtime._tick_cooling())
        self.assertEqual(backend.calls, ["general_stop", "read", "read", "read"])
        for view in views:
            self.assertEqual(view["state"], "FAULT")
            self.assertEqual(view["error"], "GeneralStopError: Focales OFF: Chroma unavailable")
            self.assertEqual(view["resource_count"], 21)
            self.assertEqual(view["native_isolation"]["worker_state"], "IDLE_OWNED")
            self.assertEqual(view["cooling_safety"]["stop_state"], "FAILED")
            self.assertTrue(view["cooling_safety"]["active"])
            self.assertFalse(view["general_cooling_ready"])
        self.assertTrue(all(view["fault_diagnostic_measurement"]["current"] for view in views[1:]))

    def test_owner_changes_during_read_cannot_attest_or_trigger_next_read(self):
        runtime, backend = self.make_runtime()
        backend.hook = lambda cancel: setattr(backend, "generation", "replacement")
        views = self.run_cycles(runtime)
        self.assertEqual(backend.calls, ["read"])
        self.assertEqual(runtime._sequence, 0)
        self.assertFalse(any(view["fault_diagnostic_measurement"]["current"] for view in views))

    def test_fast_telemetry_exposes_same_evidence_without_recovery_io(self):
        runtime, backend = self.make_runtime()
        captured = []
        def inspect(cycle):
            runtime._recovery_snapshot = lambda: (_ for _ in ()).throw(AssertionError("metadata path read recovery file"))
            captured.append(runtime.try_telemetry_snapshot())
        self.run_cycles(runtime, cycles=1, after_cycle=inspect)
        view = captured[0]
        self.assertTrue(view["fault_diagnostic_measurement"]["current"])
        self.assertFalse(view["measurement_current"])
        self.assertTrue(view["stale"])
        self.assertEqual(view["native_isolation"]["worker_generation"], backend.generation)

    def test_old_measurement_and_progress_cannot_create_fault_diagnostic_evidence(self):
        runtime, backend = self.make_runtime()
        runtime._latest, runtime._received_at = sample(9.), 100.
        view = runtime.try_telemetry_snapshot()
        self.assertFalse(view["fault_diagnostic_measurement"]["current"])
        self.assertRaises(AcquisitionCancelled, runtime._backend.read_snapshot, runtime._cancel)
        self.assertEqual(backend.calls, [])

    def test_completed_inputs_remain_fresh_during_real_delayed_read_rpc(self):
        runtime, backend = self.make_runtime()
        runtime._clock = runtime.cooling.clock = time.monotonic
        entered, release = threading.Event(), threading.Event()
        def delay_second_read(cancel):
            if backend.calls.count("read") != 2:
                return
            backend.worker_state, backend.request_id = "EXECUTING_READ_SNAPSHOT", 2
            entered.set()
            try:
                if not release.wait(3.):
                    raise AssertionError("Delayed diagnostic fixture was not released")
            finally:
                backend.worker_state, backend.request_id = "IDLE_OWNED", None
        backend.hook = delay_second_read
        runtime._wake = Wake(runtime, 2)
        worker = threading.Thread(target=runtime._run)
        worker.start()
        try:
            self.assertTrue(entered.wait(2.))
            self.assertFalse(runtime._fault_diagnostic_ready())
            for unused in range(10):
                view = runtime.try_telemetry_snapshot()
                self.assertIsNotNone(view)
                self.assertTrue(view["fault_diagnostic_measurement"]["current"])
                self.assertTrue(view["fault_diagnostic_measurement"]["read_in_progress"])
                self.assertEqual(view["sequence"], 1)
                self.assertEqual(view["latest"]["banks"][AI_BANKS[0][0]]["values"][0], 1.)
                self.assertEqual(view["native_isolation"]["active_request_id"], 2)
                self.assertEqual(view["state"], "FAULT")
                self.assertFalse(view["measurement_current"])
                packet = standard_packet(view, unused)
                populated = {row["publication"] for row in packet["data"]["banks"] if row["data"] is not None}
                self.assertEqual(populated, set(INPUTS))
            completed_at = runtime._received_at
            runtime._clock = lambda: completed_at + 2.
            self.assertFalse(runtime.try_telemetry_snapshot()["fault_diagnostic_measurement"]["current"])
            runtime._clock = time.monotonic
        finally:
            release.set()
            worker.join(3.)
        self.assertFalse(worker.is_alive())
        self.assertEqual(backend.calls, ["read", "read"])

    def test_inflight_completed_evidence_invalidates_for_any_control_or_owner_change(self):
        for change in ("cancel", "stop", "close", "revision", "uncertain", "generation", "wrong_rpc", "unattested_rpc"):
            runtime, backend = self.make_runtime()
            self.run_cycles(runtime, cycles=1)
            runtime._state = "FAULT"
            runtime._fault_diagnostic_read_in_progress = True
            backend.worker_state, backend.request_id = "EXECUTING_READ_SNAPSHOT", 2
            self.assertTrue(runtime.try_telemetry_snapshot()["fault_diagnostic_measurement"]["current"])
            if change == "cancel": runtime._cancel.set()
            elif change == "stop": runtime.general_stop(operator_confirmed=True)
            elif change == "close": runtime.deinitialize(electrical_off_confirmed=True)
            elif change == "revision": runtime._state_revision += 1
            elif change == "uncertain": backend.uncertain = True
            elif change == "generation": backend.generation = "replacement"
            elif change == "wrong_rpc": backend.worker_state = "EXECUTING_GENERAL_STOP"
            else: runtime._fault_diagnostic_read_in_progress = False
            self.assertFalse(runtime.try_telemetry_snapshot()["fault_diagnostic_measurement"]["current"], change)
            self.assertEqual(backend.calls, ["read"], change)


if __name__ == "__main__":
    unittest.main()
