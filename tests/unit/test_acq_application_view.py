"""Real-Python-3.4 tests. RAM fakes only; no NI/XP/live server is contacted."""
import copy
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView, ApplicationShutdown
from legacy.xp_acq_control.elyse_agent.command_broker import CommandBroker


class FakeRuntime(object):
    def __init__(self):
        self._identity = dict(session_id="a" * 32, build_id="b" * 64)
        self._lock = threading.RLock()
        self._clock = time.monotonic
        self.calls = []
        self.entered, self.release = threading.Event(), threading.Event()
        self.value = dict(self._identity, state="IDLE", state_revision=0, resource_count=0,
            error="", latest=None, age_seconds=.1, everest_read_age_seconds=.2,
            stale=False, control=dict(enabled=True, capabilities={"x": dict(enabled=True)}))

    def snapshot(self):
        return copy.deepcopy(self.value)

    def initialize(self, startup_confirmed=False):
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("Test release missing")
        self.calls.append(startup_confirmed)


class ApplicationViewTests(unittest.TestCase):
    def test_cold_view_never_calls_runtime_or_claims_idle(self):
        runtime = FakeRuntime()
        runtime.snapshot = lambda: self.fail("Cold read entered runtime")
        value = ApplicationView(runtime).snapshot()
        self.assertEqual(value["state"], "UNKNOWN")
        self.assertFalse(value["application_view_current"])
        self.assertTrue(value["stale"])

    def test_capture_latency_and_retained_samples_age_without_refresh(self):
        runtime, now = FakeRuntime(), [10.]
        original = runtime.snapshot
        def slow():
            value = original()
            now[0] += 3
            return value
        runtime.snapshot = slow
        view = ApplicationView(runtime, clock=lambda: now[0])
        view.capture_once()
        value = view.snapshot()
        self.assertAlmostEqual(value["age_seconds"], 3.1)
        self.assertFalse(value["application_view_current"])
        self.assertFalse(value["control"]["enabled"])
        self.assertFalse(value["control"]["capabilities"]["x"]["enabled"])
        value["state"] = "tampered"
        self.assertEqual(view.snapshot()["state"], "IDLE")

    def test_blocked_capture_never_blocks_status_reader_or_gets_replaced(self):
        runtime, entered, release = FakeRuntime(), threading.Event(), threading.Event()
        def blocked():
            entered.set()
            assert release.wait(3)
            return copy.deepcopy(runtime.value)
        runtime.snapshot = blocked
        view = ApplicationView(runtime)
        view.start()
        try:
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            self.assertEqual(view.snapshot()["state"], "UNKNOWN")
            self.assertLess(time.monotonic() - start, .2)
            self.assertRaises(RuntimeError, view.close, .01)
            self.assertRaises(RuntimeError, view.start)
        finally:
            release.set()
            view.close()

    def test_lifecycle_is_queued_once_and_shutdown_retains_blocked_worker(self):
        runtime, view = FakeRuntime(), None
        view = ApplicationView(runtime)
        view.start()
        try:
            start = time.monotonic()
            view.initialize(True)
            self.assertLess(time.monotonic() - start, .2)
            self.assertTrue(runtime.entered.wait(1))
            self.assertEqual(view.snapshot()["local_request_pending"], "initialize")
            self.assertRaises(RuntimeError, view.initialize, True)
            self.assertRaises(RuntimeError, view.close, .01)
        finally:
            runtime.release.set()
            view.close()
        self.assertEqual(runtime.calls, [True])

    def test_signed_read_liveness_and_lease_never_wait_for_runtime_lock(self):
        runtime, entered, release = FakeRuntime(), threading.Event(), threading.Event()
        broker = CommandBroker(runtime, enabled=True)
        view = ApplicationView(runtime)
        def hold():
            with runtime._lock:
                entered.set()
                assert release.wait(3)
        worker = threading.Thread(target=hold)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            self.assertFalse(view.note_everest_read())
            self.assertIsNone(broker.issue_lease_nonblocking())
            self.assertLess(time.monotonic() - start, .2)
        finally:
            release.set()
            worker.join(1)

    def test_shutdown_work_runs_outside_calling_thread_and_can_retry_same_resources(self):
        entered, release, calls = threading.Event(), threading.Event(), []
        class Resource(object):
            def join(self, timeout): return True
            def shutdown(self):
                entered.set()
                assert release.wait(3)
            def server_close(self): calls.append("server")
            def close(self): calls.append("view")
        resource = Resource()
        closer = ApplicationShutdown(resource, resource, resource)
        start = time.monotonic()
        closer.start()
        self.assertLess(time.monotonic() - start, .2)
        try:
            self.assertTrue(entered.wait(1))
            worker = closer.worker
            closer.start()
            self.assertIs(closer.worker, worker)
            self.assertFalse(closer.completed)
        finally:
            release.set()
            closer.worker.join(1)
        self.assertTrue(closer.completed)
        self.assertEqual(calls, ["server", "view"])


if __name__ == "__main__":
    unittest.main()
