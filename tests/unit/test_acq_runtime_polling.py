"""Synthetic reader/clock/event tests; no Tango, NI or external sockets."""
import threading
import unittest

from DeviceServers.control.elyse_acq.runtime_polling import RuntimePollingWorker
from tests.unit.test_acq_runtime_contract import runtime_snapshot


KEY = b"synthetic-runtime-polling-key-32-bytes"


class Clock:
    value = 100.0
    def __call__(self):
        return self.value


class RuntimePollingTests(unittest.TestCase):
    def test_constructor_is_inert_and_explicit_read_has_fixed_bounded_arguments(self):
        calls, clock = [], Clock()
        def read(key, **kwargs):
            calls.append((key, kwargs))
            clock.value += 0.1
            return runtime_snapshot()
        worker = RuntimePollingWorker(KEY, reader=read, clock=clock)
        self.assertEqual(calls, [])
        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.poll_once(), 1.0)
        self.assertEqual(calls, [(KEY, dict(port=8771, timeout=2.0))])
        result = worker.snapshot()
        self.assertEqual(result["quality"], "FRESH")
        self.assertAlmostEqual(result["source_age_seconds"], 0.2)
        self.assertFalse(result["execution_allowed"])

    def test_failed_read_drops_values_and_backoff_is_bounded_then_resets(self):
        mode = ["good"]
        def read(*args, **kwargs):
            if mode[0] == "bad":
                raise TimeoutError("synthetic timeout")
            return runtime_snapshot()
        worker = RuntimePollingWorker(KEY, reader=read, clock=Clock())
        worker.poll_once()
        self.assertIsNotNone(worker.snapshot()["runtime"]["latest"])
        mode[0] = "bad"
        self.assertEqual([worker.poll_once() for _ in range(5)], [2, 4, 8, 8, 8])
        view = worker.snapshot()
        self.assertEqual(view["quality"], "UNAVAILABLE")
        self.assertIsNone(view["runtime"])
        mode[0] = "good"
        self.assertEqual(worker.poll_once(), 1)
        self.assertEqual(worker.snapshot()["quality"], "FRESH")

    def test_bridge_and_source_elapsed_expire_separately(self):
        clock = Clock()
        worker = RuntimePollingWorker(KEY, reader=lambda *a, **k: runtime_snapshot(), clock=clock)
        worker.poll_once()
        clock.value += 2.0
        view = worker.snapshot()
        self.assertEqual(view["quality"], "STALE")
        self.assertFalse(view["bridge_stale"])
        self.assertTrue(view["source_stale"])
        self.assertIsNone(view["runtime"]["latest"])
        clock.value += 2.0
        self.assertTrue(worker.snapshot()["bridge_stale"])

    def test_new_session_cannot_reuse_old_values_and_revalidates_next_poll(self):
        current = [runtime_snapshot()]
        worker = RuntimePollingWorker(KEY, reader=lambda *a, **k: current[0], clock=Clock())
        worker.poll_once()
        current[0] = runtime_snapshot(session_id="2" * 32)
        current[0]["latest"]["banks"]["C1_NI6071E_AI"]["values"][0] = 9.0
        worker.poll_once()
        first = worker.snapshot()
        self.assertEqual(first["quality"], "STALE")
        self.assertTrue(first["session_changed"])
        self.assertIsNone(first["runtime"]["latest"])
        worker.poll_once()
        second = worker.snapshot()
        self.assertEqual(second["quality"], "FRESH")
        self.assertFalse(second["session_changed"])
        self.assertEqual(second["runtime"]["latest"]["banks"]["C1_NI6071E_AI"]["values"][0], 9.0)

    def test_wrong_identity_or_same_session_build_revision_change_is_incompatible(self):
        for wrong in (dict(runtime_protocol_version=1), dict(build_id="b" * 64), dict(state_revision=1)):
            current = [runtime_snapshot(state_revision=2)]
            worker = RuntimePollingWorker(KEY, reader=lambda *a, **k: current[0], clock=Clock())
            worker.poll_once()
            current[0] = runtime_snapshot(state_revision=2)
            current[0].update(wrong)
            worker.poll_once()
            self.assertEqual(worker.snapshot()["quality"], "INCOMPATIBLE", wrong)
            self.assertIsNone(worker.snapshot()["runtime"]["latest"])
            self.assertIsNone(worker._runtime["latest"])
            current[0] = runtime_snapshot(state_revision=3)
            worker.poll_once()
            self.assertEqual(worker.snapshot()["quality"], "FRESH")

    def test_recovery_state_and_no_synthetic_fallback(self):
        value = runtime_snapshot(state="RECOVERY_REQUIRED", latest=None,
                                 recovery=dict(required=True, reason="retained owner", protection_active=True))
        worker = RuntimePollingWorker(KEY, reader=lambda *a, **k: value, clock=Clock())
        worker.poll_once()
        result = worker.snapshot()
        self.assertEqual(result["quality"], "RECOVERY_REQUIRED")
        self.assertTrue(result["measurements_hidden"])
        self.assertIsNone(result["runtime"]["latest"])

    def test_no_overlapping_polls_even_when_reader_blocks(self):
        entered, release, calls = threading.Event(), threading.Event(), []
        def read(*args, **kwargs):
            calls.append(1)
            entered.set()
            self.assertTrue(release.wait(2))
            return runtime_snapshot()
        worker = RuntimePollingWorker(KEY, reader=read, clock=Clock())
        thread = threading.Thread(target=worker.poll_once)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            worker.poll_once()
            self.assertEqual(calls, [1])
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(worker.snapshot()["overlapping_polls_skipped"], 1)

    def test_stop_discards_late_reply_and_forbids_ghost_restart(self):
        entered, release = threading.Event(), threading.Event()
        def read(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return runtime_snapshot()
        worker = RuntimePollingWorker(KEY, reader=read, clock=Clock())
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertFalse(worker.stop(0.001))
            with self.assertRaises(RuntimeError):
                worker.start()
            self.assertIsNone(worker.snapshot()["runtime"])
        finally:
            release.set()
            self.assertTrue(worker.stop(2))
        self.assertIsNone(worker.snapshot()["runtime"])
        with self.assertRaises(RuntimeError):
            worker.start()

    def test_backoff_wait_is_interruptible_without_sleeping(self):
        class Stop:
            stopped = False
            delays = []
            def is_set(self):
                return self.stopped
            def wait(self, delay):
                self.delays.append(delay)
                self.stopped = True
                return True
            def set(self):
                self.stopped = True
        stop = Stop()
        def fail(*args, **kwargs):
            raise OSError("offline")
        worker = RuntimePollingWorker(KEY, reader=fail, clock=Clock(), stop_event=stop)
        worker.run()
        self.assertEqual(stop.delays, [2])
        self.assertIsNone(worker.snapshot()["runtime"])

    def test_copied_snapshot_and_reader_input_cannot_mutate_cache(self):
        source = runtime_snapshot()
        worker = RuntimePollingWorker(KEY, reader=lambda *a, **k: source, clock=Clock())
        worker.poll_once()
        source["latest"]["banks"].clear()
        view = worker.snapshot()
        self.assertEqual(view["quality"], "FRESH")
        view["runtime"]["latest"]["banks"].clear()
        self.assertEqual(worker.snapshot()["quality"], "FRESH")

    def test_constructor_rejects_unbounded_policy_without_calls(self):
        for kwargs in (dict(key=b"short"), dict(port=True), dict(timeout=10),
                       dict(period=0), dict(max_backoff=100), dict(period=float("nan"))):
            options = dict(key=KEY, reader=lambda *a, **k: self.fail("reader called"))
            options.update(kwargs)
            with self.assertRaises(ValueError):
                RuntimePollingWorker(**options)


if __name__ == "__main__":
    unittest.main()
