"""Actual subprocess tests on Python 3.4; RAM fixture, no NI/XP/network.

The fixture deliberately crashes ONLY its private driver-free subprocess in
one test. No existing process, device, Tango server or live archive is used.
"""
import io
import os
import sys
import tempfile
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.isolated_backend import (
    IsolatedCardBackend, IsolatedBackendError, IsolatedBackendUncertain,
)
from legacy.xp_acq_control.elyse_agent.isolated_wire import (
    encode_frame, read_frame, IsolationProtocolError,
)
from legacy.xp_acq_control.elyse_agent.acquisition_procedures import ProcedureCancelled
from legacy.xp_acq_control.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker


class FixtureBackend(object):
    """Top-level importable constructor; never constructs a native adapter."""
    def __init__(self, mode="normal", delay=.3):
        self.mode, self.delay = mode, delay
        self.resource_count, self.procedure = 0, None
        self.control_profile = "extended_ht_stop"
        self.stage_controls_verified = self.ht_feedback_verified = True
        self._observer, self.calls = None, []
        self._owner, self._close_count = threading.current_thread().ident, 0

    def _record(self, name, value=None):
        assert threading.current_thread().ident == self._owner
        self.calls.append(name)
        return dict(pid=os.getpid(), owner_thread=self._owner, calls=tuple(self.calls),
                    value=value, nidaqmx_loaded="nidaqmx" in sys.modules)

    def set_execution_observer(self, observer):
        self._observer = observer

    def initialize(self, cancel, startup_confirmed=False):
        assert startup_confirmed is True
        self.resource_count = 2
        return self._record("initialize")

    def read_snapshot(self, cancel):
        if self.mode == "crash_read":
            os._exit(19)  # Explicit private RAM-only crash fixture.
        if self.mode == "disconnect_read":
            def inspect_retention_then_exit_fixture():
                time.sleep(.6)
                frame, retained_frame = sys._current_frames().get(self._owner), False
                while frame is not None:
                    retained_frame = retained_frame or frame.f_code.co_name == "_retain_owner"
                    frame = frame.f_back
                retained = retained_frame and self.resource_count == 2 and self._close_count == 0
                os._exit(23 if retained else 24)  # Ends only this RAM fixture.
            inspector = threading.Thread(target=inspect_retention_then_exit_fixture)
            inspector.daemon = True
            inspector.start()
            time.sleep(.05)
            os.close(sys.stdout.fileno())  # Lose result pipe during active call.
            time.sleep(.05)
        if self.mode == "slow_read":
            time.sleep(self.delay)
        return self._record("read_snapshot", {39: (1.25, False), "banks": {"fixture": (True, False)}})

    def general_start(self, cancel, operator_confirmed=False):
        assert operator_confirmed is True
        self.procedure = dict(name="general_start", state="EXECUTING")
        if self._observer is not None:
            self._observer(dict(operation="general_start", safe_to_sample=self.mode != "unsafe_progress",
                                remaining_seconds=3., hardware_acknowledged=False))
        if self.mode == "cancel_start":
            deadline = time.monotonic() + 3
            while not cancel.wait(.01) and time.monotonic() < deadline:
                pass
            if cancel.is_set():
                self.procedure["state"] = "CANCELLED"
                raise ProcedureCancelled("cooperative child cancellation observed")
            raise RuntimeError("Fixture cancellation was not delivered")
        self.procedure["state"] = "COMPLETED_NOT_HARDWARE_ACK"
        return self._record("general_start")

    def general_stop(self, operator_confirmed=False):
        assert operator_confirmed is True
        return self._record("general_stop")

    def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
        assert operator_confirmed is True
        return self._record("execute_stage", (operation, new_value))

    def execute_impulsion(self, operation, cancel, operator_confirmed=False, new_value=True):
        assert operator_confirmed is True
        return self._record("execute_impulsion", (operation, new_value))

    def set_ht_voltage(self, value, cancel, operator_confirmed=False):
        assert operator_confirmed is True
        return self._record("set_ht_voltage", value)

    def configure_counter_timing(self, snapshot, cancel, operator_confirmed=False):
        assert operator_confirmed is True and type(snapshot) is tuple
        return self._record("configure_counter_timing", snapshot)

    def outer_controlled_stop(self, operator_confirmed=False):
        assert operator_confirmed is True
        return self._record("outer_controlled_stop")

    def execute_cooling_guard(self, snapshot, cancel):
        assert type(snapshot[39]) is tuple
        return self._record("execute_cooling_guard", snapshot)

    def close(self):
        self._close_count += 1
        if self.mode == "partial_close" and self._close_count == 1:
            self.resource_count = 1
            raise RuntimeError("Fixture partial cleanup retained one task")
        self.resource_count = 0
        if self.mode == "late_close":
            time.sleep(self.delay)
        return self._record("close")


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("Driver-free subprocess condition not reached")


class IsolatedWireTests(unittest.TestCase):
    def test_exact_source_values_survive_json(self):
        value = dict(integer_locals={39: (1.25, False), 44: (True,) * 77},
                     list_value=[1, "x"], set_value={3, 4}, collision={"type": "tuple", "items": []})
        self.assertEqual(read_frame(io.BytesIO(encode_frame(value))), value)

    def test_bounded_finite_nonexecutable_values(self):
        for value in (dict(bad=float("nan")), dict(huge="a" * 1048576), dict(code=lambda: None)):
            with self.assertRaises(IsolationProtocolError):
                encode_frame(value)
        with self.assertRaises(IsolationProtocolError):
            read_frame(io.BytesIO(b"\x7f\xff\xff\xff"))


class IsolatedBackendTests(unittest.TestCase):
    def make_backend(self, **kwargs):
        return IsolatedCardBackend(backend_factory=FixtureBackend, **kwargs)

    def test_constructor_and_attributes_are_cold_ram_only(self):
        backend = self.make_backend(focal_options=dict(resources_verified=True))
        self.assertIsNone(backend._process)
        self.assertEqual(backend.resource_count, 0)
        self.assertEqual(backend.isolation_snapshot()["worker_state"], "COLD")
        self.assertTrue(backend.focal_command.resources_verified)
        with self.assertRaises(ValueError):
            backend.initialize(threading.Event(), startup_confirmed=False)
        backend.close()
        self.assertIsNone(backend._process)

    def test_progress_dispatch_preserves_child_age_and_parent_wait_age(self):
        observations = []
        backend = self.make_backend(progress_observer=observations.append)
        event = dict(sample={"fixture": True}, sample_age_seconds=.1,
                     parent_received_monotonic=time.monotonic() - .25)
        backend._observe_progress(event)
        self.assertGreaterEqual(observations[0]["sample_age_seconds"], .35)
        self.assertEqual(event["sample_age_seconds"], .1)
        backend._observe_progress(dict(operation="heartbeat"))
        self.assertNotIn("sample_age_seconds", observations[1])

    def test_pythonw_parent_chooses_hidden_console_capable_sibling(self):
        original = sys.executable
        try:
            sys.executable = os.path.join(os.path.dirname(original), "pythonw.exe")
            backend = self.make_backend()
            self.assertEqual(os.path.basename(backend._python).lower(), "python.exe")
            self.assertIsNone(backend._process)
        finally:
            sys.executable = original

    def test_all_calls_serial_in_one_child_main_thread_and_cached_properties(self):
        backend, cancel = self.make_backend(), threading.Event()
        first = backend.initialize(cancel, startup_confirmed=True)
        try:
            self.assertNotEqual(first["pid"], os.getpid())
            self.assertEqual(backend.resource_count, 2)
            results = [backend.read_snapshot(cancel), backend.general_start(cancel, operator_confirmed=True),
                       backend.general_stop(operator_confirmed=True),
                       backend.execute_stage("prema.stop", cancel, operator_confirmed=True, new_value=False),
                       backend.execute_impulsion("modulator_impulse.stop", cancel, operator_confirmed=True),
                       backend.set_ht_voltage(0., cancel, operator_confirmed=True),
                       backend.configure_counter_timing((0.,) * 33, cancel, operator_confirmed=True),
                       backend.execute_cooling_guard({39: (1.,)}, cancel),
                       backend.outer_controlled_stop(operator_confirmed=True)]
            for result in results:
                self.assertEqual(result["pid"], first["pid"])
                self.assertEqual(result["owner_thread"], first["owner_thread"])
                self.assertFalse(result["nidaqmx_loaded"])
            self.assertEqual(results[0]["value"][39], (1.25, False))
            self.assertEqual(type(results[6]["value"]), tuple)
            saved = backend._rpc
            def forbidden(*args, **kwargs):
                raise AssertionError("RAM attribute attempted RPC")
            backend._rpc = forbidden
            try:
                self.assertEqual(backend.resource_count, 2)
                self.assertEqual(backend.control_profile, "extended_ht_stop")
                self.assertIsInstance(backend.procedure, dict)
                self.assertFalse(backend.isolation_snapshot()["cleanup_confirmed"])
            finally:
                backend._rpc = saved
        finally:
            backend.close()
        self.assertEqual(backend.resource_count, 0)
        self.assertEqual(backend._process.returncode, 0)
        self.assertTrue(backend.isolation_snapshot()["cleanup_confirmed"])
        backend.close()  # Already joined: no second native close/replay.
        with self.assertRaises(IsolatedBackendUncertain):
            backend.initialize(cancel, startup_confirmed=True)

    def test_nonowner_thread_cannot_call_driver_rpc(self):
        backend, cancel, failures = self.make_backend(), threading.Event(), []
        backend.initialize(cancel, startup_confirmed=True)
        def other_thread():
            try:
                backend.read_snapshot(cancel)
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=other_thread)
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], RuntimeError)
        backend.close()

    def test_slow_native_call_cannot_block_parent_ram_status(self):
        ready, results, failures = threading.Event(), {}, []
        def owner():
            backend = self.make_backend(backend_options=dict(mode="slow_read", delay=.4))
            results["backend"] = backend
            try:
                backend.initialize(threading.Event(), startup_confirmed=True)
                ready.set()
                results["sample"] = backend.read_snapshot(threading.Event())
            except Exception as error:
                failures.append(error)
            finally:
                backend.close()
        worker = threading.Thread(target=owner)
        worker.start()
        self.assertTrue(ready.wait(3))
        backend = results["backend"]
        wait_until(lambda: backend.isolation_snapshot()["worker_state"] == "EXECUTING_READ_SNAPSHOT")
        started = time.monotonic()
        for unused in range(200):
            self.assertEqual(backend.resource_count, 2)
            self.assertEqual(backend.control_profile, "extended_ht_stop")
            self.assertIsInstance(backend.isolation_snapshot(), dict)
        self.assertLess(time.monotonic() - started, .2)
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(backend.resource_count, 0)

    def test_rejected_wire_value_does_not_create_phantom_native_call(self):
        backend, cancel = self.make_backend(), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        try:
            with self.assertRaises(IsolationProtocolError):
                backend.set_ht_voltage(float("nan"), cancel, operator_confirmed=True)
            self.assertIsNone(backend.isolation_snapshot()["active_request_id"])
            self.assertFalse(backend.isolation_snapshot()["ownership_uncertain"])
            self.assertNotIn("set_ht_voltage", backend.read_snapshot(cancel)["calls"])
        finally:
            backend.close()

    def test_cancellation_reaches_child_without_concurrent_ni_call(self):
        cancel, observations, parent_thread = threading.Event(), [], threading.current_thread().ident
        def observe(event):
            observations.append((threading.current_thread().ident, event))
            cancel.set()
        backend = self.make_backend(backend_options=dict(mode="cancel_start"), progress_observer=observe)
        backend.initialize(cancel, startup_confirmed=True)
        try:
            with self.assertRaises(ProcedureCancelled):
                backend.general_start(cancel, operator_confirmed=True)
            self.assertTrue(observations)
            self.assertEqual(observations[0][0], parent_thread)
            self.assertNotIn("sample", observations[0][1])  # Default progress-only.
            self.assertEqual(backend.procedure["state"], "CANCELLED")
            self.assertFalse(backend.isolation_snapshot()["ownership_uncertain"])
        finally:
            backend.close()

    def test_sampling_is_explicit_safe_and_same_owner(self):
        for mode, expected in (("normal", True), ("unsafe_progress", False)):
            observations, cancel = [], threading.Event()
            backend = self.make_backend(backend_options=dict(mode=mode), safe_sample_budget_seconds=2.,
                                        progress_observer=observations.append)
            initial = backend.initialize(cancel, startup_confirmed=True)
            try:
                backend.general_start(cancel, operator_confirmed=True)
                self.assertTrue(observations)
                self.assertEqual("sample" in observations[0], expected)
                if expected:
                    self.assertEqual(observations[0]["sample"]["owner_thread"], initial["owner_thread"])
                    self.assertGreaterEqual(observations[0]["sample_age_seconds"], 0.)
            finally:
                backend.close()

    def test_observer_exception_does_not_abandon_inflight_operation(self):
        def broken_observer(event):
            raise RuntimeError("Fixture observer failure")
        backend, cancel = self.make_backend(progress_observer=broken_observer), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        try:
            result = backend.general_start(cancel, operator_confirmed=True)
            self.assertIn("general_start", result["calls"])
            self.assertIn("Fixture observer failure", backend.isolation_snapshot()["progress_observer_error"])
        finally:
            backend.close()

    def test_timeout_is_unknown_no_restart_and_cleanup_cannot_race_call(self):
        backend, cancel = self.make_backend(backend_options=dict(mode="slow_read", delay=.3)), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        generation = backend.isolation_snapshot()["worker_generation"]
        backend._rpc_timeout = .06
        with self.assertRaises(IsolatedBackendUncertain):
            backend.read_snapshot(cancel)
        self.assertGreater(backend.resource_count, 0)
        self.assertTrue(backend.isolation_snapshot()["ownership_uncertain"])
        with self.assertRaises(IsolatedBackendUncertain):
            backend.close()
        with self.assertRaises(IsolatedBackendUncertain):
            backend.general_stop(operator_confirmed=True)
        wait_until(lambda: backend._response is not None)
        backend.close()  # Explicit release after late return, not a retry of the read.
        self.assertEqual(backend.resource_count, 0)
        self.assertEqual(backend.isolation_snapshot()["worker_generation"], generation)

    def test_partial_cleanup_retains_owner_until_explicit_retry_and_join(self):
        backend, cancel = self.make_backend(backend_options=dict(mode="partial_close")), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        with self.assertRaises(IsolatedBackendError):
            backend.close()
        self.assertEqual(backend.resource_count, 1)
        self.assertFalse(backend.isolation_snapshot()["cleanup_confirmed"])
        backend.close()
        self.assertEqual(backend.resource_count, 0)

    def test_late_successful_close_requires_explicit_join_confirmation(self):
        backend, cancel = self.make_backend(backend_options=dict(mode="late_close", delay=.3), close_timeout=.06), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        with self.assertRaises(IsolatedBackendUncertain):
            backend.close()
        self.assertGreater(backend.resource_count, 0)
        self.assertFalse(backend.isolation_snapshot()["cleanup_confirmed"])
        wait_until(lambda: backend._response is not None)
        backend.close()
        self.assertEqual(backend.resource_count, 0)
        self.assertTrue(backend.isolation_snapshot()["cleanup_confirmed"])

    def test_child_crash_never_reports_zero_resources_or_restarts(self):
        backend, cancel = self.make_backend(backend_options=dict(mode="crash_read")), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        pid = backend.isolation_snapshot()["worker_pid"]
        with self.assertRaises(IsolatedBackendUncertain):
            backend.read_snapshot(cancel)
        self.assertGreater(backend.resource_count, 0)
        self.assertTrue(backend.isolation_snapshot()["ownership_uncertain"])
        with self.assertRaises(IsolatedBackendUncertain):
            backend.close()
        self.assertEqual(backend._process.wait(timeout=2), 19)
        self.assertEqual(backend.isolation_snapshot()["worker_pid"], pid)
        # These streams belong only to the confirmed-dead RAM fixture process.
        backend._process.stdin.close()
        backend._process.stdout.close()
        backend._write_queue.put_nowait(None)

    def test_result_pipe_loss_during_active_call_quarantines_retained_owner(self):
        backend, cancel = self.make_backend(backend_options=dict(mode="disconnect_read")), threading.Event()
        backend.initialize(cancel, startup_confirmed=True)
        with self.assertRaises(IsolatedBackendUncertain):
            backend.read_snapshot(cancel)
        self.assertGreater(backend.resource_count, 0)
        self.assertFalse(backend.isolation_snapshot()["cleanup_confirmed"])
        # The private fixture inspects its main stack and exits23 only after
        # the worker entered retained-owner quarantine, with no close call.
        self.assertEqual(backend._process.wait(timeout=2), 23)
        backend._process.stdin.close()
        backend._process.stdout.close()
        backend._write_queue.put_nowait(None)

    def test_runtime_marker_released_only_after_zero_resources_and_child_join(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = dict(runtime_protocol_version=2, session_id="a" * 32, build_id="b" * 64)
            marker = OwnershipMarker(os.path.join(directory, "ownership.json"),
                                     identity["session_id"], identity["build_id"])
            backends = []
            def factory():
                backend = self.make_backend()
                backends.append(backend)
                return backend
            runtime = AcquisitionRuntime(factory, identity=identity, recovery_guard=marker, period=.02)
            runtime.start()
            try:
                runtime.initialize(startup_confirmed=True)
                wait_until(lambda: runtime.snapshot()["state"] == "RUNNING")
                self.assertTrue(os.path.isfile(marker.path))
                self.assertGreater(runtime.snapshot()["resource_count"], 0)
                runtime.request_shutdown()
                self.assertTrue(runtime.join(3))
                self.assertFalse(os.path.exists(marker.path))
                self.assertTrue(backends[0].isolation_snapshot()["cleanup_confirmed"])
                self.assertEqual(backends[0]._process.returncode, 0)
            finally:
                if runtime._thread.is_alive():
                    runtime.request_shutdown(electrical_off_confirmed=True)
                    runtime.join(3)

    def test_runtime_crash_preserves_marker_and_blocks_replacement_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = dict(runtime_protocol_version=2, session_id="c" * 32, build_id="d" * 64)
            marker = OwnershipMarker(os.path.join(directory, "ownership.json"),
                                     identity["session_id"], identity["build_id"])
            backends = []
            def factory():
                backend = self.make_backend(backend_options=dict(mode="crash_read"))
                backends.append(backend)
                return backend
            runtime = AcquisitionRuntime(factory, identity=identity, recovery_guard=marker, period=.02)
            runtime.start()
            try:
                runtime.initialize(startup_confirmed=True)
                wait_until(lambda: runtime.snapshot()["state"] == "FAULT")
                self.assertTrue(os.path.isfile(marker.path))
                self.assertGreater(runtime.snapshot()["resource_count"], 0)
                prior = OwnershipMarker(marker.path, "e" * 32, "f" * 64)
                self.assertTrue(prior.snapshot()["required"])
                with self.assertRaises(RuntimeError):
                    runtime.initialize(startup_confirmed=True)
                self.assertEqual(len(backends), 1)
            finally:
                # Test harness ends only its RAM runtime thread after this
                # deliberately crashed, driver-free child. No production
                # recovery/cleanup proof is forged; dirty marker remains.
                with runtime._lock:
                    runtime._state = "STOPPED"
                runtime._wake.set()
                self.assertTrue(runtime.join(3))
                backend = backends[0]
                self.assertEqual(backend._process.wait(timeout=2), 19)
                backend._process.stdin.close()
                backend._process.stdout.close()
                backend._write_queue.put_nowait(None)
            self.assertTrue(os.path.isfile(marker.path))


if __name__ == "__main__":
    unittest.main()
