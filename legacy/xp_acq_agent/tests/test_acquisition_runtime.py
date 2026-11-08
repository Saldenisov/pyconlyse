"""Python 3.4-compatible, fake-driver/loopback tests. Never NI hardware."""
import ast
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend, DemoBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_http import RuntimeHTTPServer, request_signature, response_signature
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.elyse_agent.acquisition_startup import install_startup, MARKER, FILENAME
from legacy.xp_acq_agent.elyse_agent.hardware_tasks import LegacyCardTasks, TaskCleanupError


KEY = b"synthetic-runtime-test-key-not-production-000000"


def wait_state(runtime, state, seconds=2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if runtime.snapshot()["state"] == state:
            return
        time.sleep(0.005)
    raise AssertionError("Expected {0}, got {1}".format(state, runtime.snapshot()))


class FakeBackend(DemoBackend):
    def __init__(self):
        DemoBackend.__init__(self)
        self.close_calls = 0
        self.fail_read = False
        self.fail_close = False
        self.read_entered = None
        self.release_read = None

    @property
    def resource_count(self):
        return 2 if self.active else 0

    def read_snapshot(self, cancel):
        if self.read_entered is not None:
            self.read_entered.set()
            self.release_read.wait(2)
        if self.fail_read:
            raise RuntimeError("synthetic read error")
        return DemoBackend.read_snapshot(self, cancel)

    def close(self):
        self.close_calls += 1
        if self.fail_close:
            raise RuntimeError("synthetic close error")
        DemoBackend.close(self)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.factory = Mock(return_value=self.backend)
        self.runtime = AcquisitionRuntime(self.factory, period=0.02)
        self.runtime.start()

    def tearDown(self):
        self.backend.fail_close = False
        if self.backend.release_read is not None:
            self.backend.release_read.set()
        self.runtime.request_shutdown()
        self.assertTrue(self.runtime.join(3))

    def test_start_is_cold(self):
        time.sleep(0.03)
        self.factory.assert_not_called()
        result = self.runtime.snapshot()
        self.assertEqual(result["state"], "IDLE")
        self.assertEqual(result["resource_count"], 0)
        self.assertIsNone(result["latest"])
        self.assertTrue(result["stale"])
        self.assertFalse(result["auto_initialize"])

    def test_confirmation_required(self):
        with self.assertRaises(ValueError):
            self.runtime.initialize()
        self.factory.assert_not_called()

    def test_initialize_read_deinitialize_keeps_service_alive(self):
        self.runtime.initialize(startup_confirmed=True)
        wait_state(self.runtime, "RUNNING")
        end = time.monotonic() + 1
        while self.runtime.snapshot()["latest"] is None and time.monotonic() < end:
            time.sleep(0.005)
        self.assertFalse(self.runtime.snapshot()["stale"])
        self.runtime.deinitialize()
        wait_state(self.runtime, "IDLE")
        self.assertTrue(self.runtime.snapshot()["stale"])
        self.assertFalse(self.runtime.join(0))

    def test_double_initialization_rejected(self):
        self.runtime.initialize(startup_confirmed=True)
        with self.assertRaises(RuntimeError):
            self.runtime.initialize(startup_confirmed=True)

    def test_read_error_is_fault_not_fresh_zero(self):
        self.backend.fail_read = True
        self.runtime.initialize(startup_confirmed=True)
        wait_state(self.runtime, "FAULT")
        self.assertTrue(self.runtime.snapshot()["stale"])
        self.assertIn("synthetic read error", self.runtime.snapshot()["error"])
        self.assertEqual(self.backend.close_calls, 1)

    def test_cleanup_failure_retains_owner_and_can_retry(self):
        self.backend.fail_close = True
        self.runtime.initialize(startup_confirmed=True)
        wait_state(self.runtime, "RUNNING")
        self.runtime.deinitialize()
        wait_state(self.runtime, "FAULT")
        self.assertEqual(self.runtime.snapshot()["resource_count"], 2)
        with self.assertRaises(RuntimeError):
            self.runtime.initialize(startup_confirmed=True)
        self.backend.fail_close = False
        self.runtime.deinitialize()
        wait_state(self.runtime, "IDLE")
        self.assertEqual(self.runtime.snapshot()["resource_count"], 0)

    def test_shutdown_does_not_exit_after_failed_cleanup(self):
        self.backend.fail_close = True
        self.runtime.initialize(startup_confirmed=True)
        wait_state(self.runtime, "RUNNING")
        self.runtime.request_shutdown()
        wait_state(self.runtime, "FAULT")
        self.assertFalse(self.runtime.join(0))

    def test_no_concurrent_close_during_read(self):
        self.backend.read_entered, self.backend.release_read = threading.Event(), threading.Event()
        self.runtime.initialize(startup_confirmed=True)
        self.assertTrue(self.backend.read_entered.wait(1))
        self.runtime.deinitialize()
        time.sleep(0.03)
        self.assertEqual(self.backend.close_calls, 0)
        self.backend.release_read.set()
        wait_state(self.runtime, "IDLE")
        self.assertEqual(self.backend.close_calls, 1)

    def test_snapshots_are_copies(self):
        result = self.runtime.snapshot()
        result["state"] = "RUNNING"
        self.assertEqual(self.runtime.snapshot()["state"], "IDLE")


class BackendTests(unittest.TestCase):
    def fake_owner(self):
        owner = Mock()
        owner.tasks = {}
        for name in ("C1_NI6071E_AI", "C2_NI6071E_AI", "C11_NI6220_AI",
                     "C3_DIO96_DI", "C4_DIO96_DI", "C5_DIO96_DI"):
            task = Mock()
            if name.endswith("_DI"):
                task.read.return_value = [False] * (64 if name.startswith("C4") else 56)
            owner.tasks[name] = task
        owner.read_analog_means.side_effect = lambda name, **kw: [1.0] * (16 if name.startswith("C11") else 64)
        owner.start_legacy_counters.return_value = [0, 1, 2, 5, 6, 7]
        from legacy.xp_acq_agent.elyse_agent.hardware_plan import digital_startup_image
        owner.write_initial_images.return_value = {"digital": digital_startup_image(), "analog_volts": {}}
        return owner

    def test_constructor_and_missing_confirmation_do_not_call_driver(self):
        factory = Mock()
        backend = CardBackend(factory)
        factory.assert_not_called()
        with self.assertRaises(ValueError):
            backend.initialize(threading.Event())
        factory.assert_not_called()

    def test_startup_and_read_shapes_and_scaling(self):
        owner = self.fake_owner()
        backend = CardBackend(Mock(return_value=owner))
        backend.initialize(threading.Event(), startup_confirmed=True)
        self.assertEqual([call[0] for call in owner.method_calls[:2]],
                         ["start_legacy_counters", "write_initial_images"])
        result = backend.read_snapshot(threading.Event())
        self.assertEqual(len(result["banks"]), 6)
        bank = result["banks"]["C1_NI6071E_AI"]
        self.assertEqual(bank["values"][0], 1.0)
        self.assertEqual(bank["legacy_scaled_values"][0], 15.0)
        self.assertFalse(result["runtime_setpoint_commands_enabled"])
        for name in ("C1_NI6071E_AI", "C2_NI6071E_AI", "C11_NI6220_AI"):
            owner.tasks[name].start.assert_called_once_with()
            owner.tasks[name].stop.assert_called_once_with()

    def test_read_error_still_stops_finite_ai_task(self):
        owner = self.fake_owner()
        owner.read_analog_means.side_effect = RuntimeError("synthetic read failure")
        backend = CardBackend(Mock(return_value=owner))
        backend.initialize(threading.Event(), startup_confirmed=True)
        with self.assertRaises(RuntimeError):
            backend.read_snapshot(threading.Event())
        owner.tasks["C1_NI6071E_AI"].stop.assert_called_once_with()

    def test_nonfinite_raw_read_not_sent_as_json_nan(self):
        owner = self.fake_owner()
        owner.read_analog_means.side_effect = lambda name, **kw: [float("nan")] * 64
        backend = CardBackend(Mock(return_value=owner))
        backend.initialize(threading.Event(), startup_confirmed=True)
        with self.assertRaises(ValueError):
            backend.read_snapshot(threading.Event())

    def test_failed_task_close_is_retained_for_retry(self):
        good, bad = Mock(), Mock()
        bad.close.side_effect = RuntimeError("synthetic close failure")
        owner = LegacyCardTasks(None, {}, {"good": good, "bad": bad}, {})
        with self.assertRaises(TaskCleanupError):
            owner.close()
        self.assertEqual(list(owner.tasks), ["bad"])
        self.assertFalse(owner.closed)
        bad.close.side_effect = None
        owner.close()
        self.assertTrue(owner.closed)
        good.close.assert_called_once_with()


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.factory = Mock(return_value=DemoBackend())
        self.runtime = AcquisitionRuntime(self.factory)
        self.runtime.start()
        self.server = RuntimeHTTPServer(("127.0.0.1", 0), self.runtime, KEY)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.01))
        self.thread.daemon = True
        self.thread.start()
        self.url = "http://127.0.0.1:{0}".format(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.runtime.request_shutdown()
        self.assertTrue(self.runtime.join(2))

    def request(self, path="/snapshot", signed=True, method="GET"):
        nonce = "a" * 32
        headers = ({"X-ACQ-Nonce": nonce, "X-ACQ-Signature": request_signature(KEY, path, nonce)}
                   if signed else {})
        return urlopen(Request(self.url + path, headers=headers, method=method), timeout=2)

    def test_authenticated_status_and_signature_without_hardware(self):
        with self.request() as response:
            raw = response.read()
            self.assertEqual(response.headers["X-ACQ-Response-Signature"],
                             response_signature(KEY, "a" * 32, raw))
            self.assertEqual(json.loads(raw.decode("utf-8"))["state"], "IDLE")
        self.factory.assert_not_called()

    def test_no_initialization_even_through_signed_http_post(self):
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            with self.assertRaises(HTTPError) as caught:
                self.request(method=method)
            self.assertEqual(caught.exception.code, 405)
        self.factory.assert_not_called()

    def test_unsigned_requests_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.request(signed=False)
        self.assertEqual(caught.exception.code, 401)

    def test_status_omits_values(self):
        with self.request(path="/status") as response:
            self.assertNotIn("latest", json.loads(response.read().decode("utf-8")))

    def test_remote_init_path_does_not_exist(self):
        with self.assertRaises(HTTPError) as caught:
            self.request(path="/initialize", signed=False)
        self.assertEqual(caught.exception.code, 404)

    def test_remote_general_commands_have_no_route(self):
        for path in ("/general_start", "/general_stop"):
            with self.assertRaises(HTTPError) as caught:
                self.request(path=path, signed=False)
            self.assertEqual(caught.exception.code, 404)

    def test_wildcard_bind_rejected(self):
        with self.assertRaises(ValueError):
            RuntimeHTTPServer(("0.0.0.0", 0), self.runtime, KEY)


class StartupTests(unittest.TestCase):
    def test_installs_cold_launcher_only_and_can_update_own_file(self):
        with tempfile.TemporaryDirectory() as folder:
            entry, config, interpreter = [os.path.join(folder, name) for name in ("app.pyw", "cfg.json", "pythonw.exe")]
            for path in (entry, config, interpreter):
                with open(path, "w") as target:
                    target.write("")
            target = install_startup(entry, config, folder, interpreter)
            with open(target) as source:
                code = source.read()
            self.assertTrue(code.startswith(MARKER))
            self.assertNotIn("initialize", code.lower())
            ast.parse(code)
            self.assertEqual(target, install_startup(entry, config, folder, interpreter))

    def test_does_not_overwrite_unrelated_startup_file(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, name) for name in ("app.pyw", "cfg.json", "pythonw.exe", FILENAME)]
            for path in paths:
                with open(path, "w") as target:
                    target.write("unrelated")
            with self.assertRaises(ValueError):
                install_startup(paths[0], paths[1], folder, paths[2])


if __name__ == "__main__":
    unittest.main()
