"""Offline cross-module acceptance; stdlib unittest, actual Python 3.4.

Only loopback sockets, RAM runtimes and temporary SQLite/source copies are used.
No owner thread is started, and no driver, XP host or live HDF5 is contacted.
"""
import hmac
import json
import os
import shutil
import socket
import struct
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock
from uuid import uuid4

from legacy.xp_acq_control.elyse_agent import cooling_safety
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import (
    AcquisitionControlRuntime, control_identity)
from legacy.xp_acq_control.elyse_agent.acquisition_http import (
    request_signature, response_signature)
from legacy.xp_acq_control.elyse_agent.application_view import (
    ApplicationView, StartupCleanup, cleanup_failed_start)
from legacy.xp_acq_control.elyse_agent.command_http import ControlHTTPServer
from legacy.xp_acq_control.elyse_agent.command_protocol import command_signature
from legacy.xp_acq_control.elyse_agent.cooling_safety import AlarmJournal, CoolingSafety
from legacy.xp_acq_control.elyse_agent.protocol import recv_message
from legacy.xp_acq_control.elyse_agent.shared_state_receiver import SharedStateServer


READ_KEY, COMMAND_KEY = b"r" * 32, b"w" * 32


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("Offline synchronization condition not reached")


def arm_cooling_baseline(alarm):
    """Establish fresh active green before testing loss persistence/cleanup."""
    original, now = alarm.clock, alarm.clock()
    green = dict((name, dict(fault=False, quality="FRESH", causes=[]))
                 for name in ("CANON", "SECTION"))
    try:
        alarm.clock = lambda: now - cooling_safety.RECOVERY_SECONDS
        alarm.observe(green, True, -2)
        alarm.clock = lambda: now
        alarm.observe(green, True, -1)
    finally:
        alarm.clock = original


class HTTPFixture(object):
    def __init__(self, view):
        self.server = ControlHTTPServer(("127.0.0.1", 0), view, READ_KEY, COMMAND_KEY)
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01))
        self.worker.daemon = True
        self.worker.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def exchange(self, path, value=None):
        nonce, key = uuid4().hex, READ_KEY if value is None else COMMAND_KEY
        raw = None if value is None else json.dumps(value).encode("utf-8")
        signature = (request_signature(key, path, nonce) if raw is None
                     else command_signature(key, nonce, raw))
        headers = {"X-ACQ-Nonce": nonce, "X-ACQ-Signature": signature}
        if raw is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.url + path, data=raw, headers=headers)
        try:
            response = self.opener.open(request, timeout=1)
        except urllib.error.HTTPError as error:
            response = error
        try:
            body = response.read()
            if not hmac.compare_digest(response_signature(key, nonce, body),
                                       response.headers.get("X-ACQ-Response-Signature", "")):
                raise AssertionError("HTTP response signature did not authenticate")
            return response.getcode(), json.loads(body.decode("utf-8"))
        finally:
            response.close()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(1)
        if self.worker.is_alive():
            raise AssertionError("Offline HTTP server did not stop")


class HoldingIngressStore(object):
    """Pause a real framed ingress handler after receipt, without network I/O."""
    def __init__(self):
        self.lock = threading.Lock()
        self.rejected, self.last_error = 0, ""
        self.condition, self.release = threading.Condition(), threading.Event()
        self.entered, self.active = 0, 0

    def ingest(self, data, peer):
        if data != b"offline-probe" or peer != "127.0.0.1":
            raise ValueError("Unexpected offline ingress payload")
        with self.condition:
            self.entered += 1
            self.active += 1
            self.condition.notify_all()
        try:
            if not self.release.wait(3):
                raise RuntimeError("Offline ingress pause was not released")
            return dict(accepted=True)
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()


class NonblockingIntegrationTests(unittest.TestCase):
    def runtime(self, clock=None, cooling=None):
        calls = []
        def forbidden_backend():
            calls.append("backend factory")
            raise AssertionError("Integration test must never create a NI backend")
        runtime = AcquisitionControlRuntime(forbidden_backend, remote_enabled=True,
                                            clock=clock, cooling=cooling)
        return runtime, calls

    @staticmethod
    def command(state):
        return dict(command_id=uuid4().hex, session_id=state["session_id"],
                    expected_revision=state["state_revision"],
                    operation="modulator.general.start", operator_confirmed=True, value=None)

    def test_signed_http_get_is_bounded_while_runtime_lock_and_capture_are_blocked(self):
        now, entered, capture_entered, release = [100.], threading.Event(), threading.Event(), threading.Event()
        runtime, calls = self.runtime(clock=lambda: now[0])
        view = ApplicationView(runtime, clock=lambda: now[0])
        view.capture_once()
        now[0] += .1
        original_snapshot = runtime.snapshot
        def snapshot():
            capture_entered.set()
            return original_snapshot()  # Actual runtime RLock is the blocker.
        runtime.snapshot = snapshot
        def hold_runtime():
            with runtime._lock:
                entered.set()
                release.wait(3)
        holder = threading.Thread(target=hold_runtime)
        holder.start()
        http = None
        try:
            self.assertTrue(entered.wait(1))
            view.start()
            self.assertTrue(capture_entered.wait(1))
            http = HTTPFixture(view)
            start = time.monotonic()
            code, state = http.exchange("/snapshot")
            self.assertLess(time.monotonic() - start, .5)
            self.assertEqual(code, 200)
            self.assertEqual(state["state"], "IDLE")
            self.assertTrue(state["application_view_current"])
            self.assertIsNone(state["control"]["lease"])
            self.assertAlmostEqual(state["application_view_age_seconds"], .1)
            # The same blocked capture must not renew old metadata later.
            now[0] = 103.
            start = time.monotonic()
            code, state = http.exchange("/snapshot")
            self.assertLess(time.monotonic() - start, .5)
            self.assertEqual(code, 200)
            self.assertFalse(state["application_view_current"])
            self.assertTrue(state["stale"])
            self.assertIsNone(state["control"]["lease"])
            self.assertEqual(state["application_view_age_seconds"], 3.)
            self.assertTrue(holder.is_alive())
            self.assertEqual(calls, [])
        finally:
            release.set()
            holder.join(1)
            view.close()
            if http is not None:
                http.close()

    def test_fresh_cached_view_issues_lease_but_stale_revision_never_dispatches(self):
        runtime, calls = self.runtime()
        view = ApplicationView(runtime)
        view.capture_once()
        http = HTTPFixture(view)
        try:
            code, state = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertTrue(state["application_view_current"])
            self.assertIsNotNone(state["control"]["lease"])
            request = self.command(state)
            with runtime._lock:
                runtime._state_revision += 1
            code, result = http.exchange("/commands", dict(request=request, lease=state["control"]["lease"]))
            self.assertIn(code, (200, 409))
            if code == 200:
                self.assertEqual(result["outcome"], "REJECTED")
            self.assertIn("revision", result.get("error", "").lower())
            self.assertIsNone(runtime._pending)
            self.assertIsNone(runtime._thread)
            self.assertEqual(calls, [])
        finally:
            http.close()
            view.close()

    def test_lease_expires_with_metadata_not_two_seconds_after_late_cached_read(self):
        now = [100.]
        runtime, calls = self.runtime(clock=lambda: now[0])
        view = ApplicationView(runtime, clock=lambda: now[0])
        view.capture_once()
        http = HTTPFixture(view)
        try:
            now[0] = 101.9
            code, state = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertTrue(state["application_view_current"])
            self.assertIsNotNone(state["control"]["lease"])
            self.assertAlmostEqual(state["control"]["lease_seconds"], .1)
            now[0] = 102.01
            code, result = http.exchange("/commands", dict(request=self.command(state),
                                                          lease=state["control"]["lease"]))
            self.assertEqual(code, 409)
            self.assertIn("LEASE_EXPIRED", result["error"])
            self.assertFalse(view.snapshot()["application_view_current"])
            self.assertIsNone(runtime._pending)
            self.assertEqual(calls, [])
        finally:
            http.close()
            view.close()

    def test_issued_lease_cannot_be_rebased_to_a_later_runtime_revision(self):
        runtime, calls = self.runtime()
        view = ApplicationView(runtime)
        view.capture_once()
        http = HTTPFixture(view)
        try:
            code, state = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertIsNotNone(state["control"]["lease"])
            request = self.command(state)
            with runtime._lock:
                runtime._state_revision += 1
                request["expected_revision"] = runtime._state_revision
            code, result = http.exchange("/commands", dict(request=request, lease=state["control"]["lease"]))
            self.assertEqual(code, 409)
            self.assertEqual(result["error"], "COMMAND_LEASE_CONTEXT_CHANGED")
            self.assertEqual(runtime.broker.records, {})
            self.assertIsNone(runtime._pending)
            self.assertEqual(calls, [])
        finally:
            http.close()
            view.close()

    def snapshot_lease_expiry_interleaving(self, boundary):
        now = [100.]
        runtime, calls = self.runtime(clock=lambda: now[0])
        view = ApplicationView(runtime, clock=lambda: now[0])
        view.capture_once()
        observed = []
        if boundary == "after_snapshot":
            original_snapshot = view.snapshot
            def delayed_snapshot():
                body = original_snapshot()
                observed.append(body["application_view_age_seconds"])
                # The HTTP body was built while fresh, but issuance is later.
                now[0] = 102.01
                return body
            view.snapshot = delayed_snapshot
        elif boundary == "before_broker":
            original_issue = runtime.broker.issue_lease_nonblocking
            def delayed_issue(*args, **kwargs):
                observed.append(now[0])
                # Simulate descheduling between view validation and broker.
                now[0] = 102.01
                return original_issue(*args, **kwargs)
            runtime.broker.issue_lease_nonblocking = delayed_issue
        else:
            self.fail("Unknown offline interleaving")
        http = HTTPFixture(view)
        try:
            now[0] = 101.9
            code, state = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertEqual(len(observed), 1)
            self.assertIsNone(state["control"]["lease"])
            self.assertEqual(state["control"]["lease_seconds"], 0)
            self.assertEqual(runtime.broker.leases, {})
            self.assertIsNone(runtime._pending)
            self.assertEqual(calls, [])
        finally:
            http.close()
            view.close()

    def test_http_never_issues_lease_if_metadata_expires_after_snapshot(self):
        self.snapshot_lease_expiry_interleaving("after_snapshot")

    def test_http_never_extends_view_deadline_if_broker_is_descheduled(self):
        self.snapshot_lease_expiry_interleaving("before_broker")

    def test_http_never_issues_lease_for_replaced_cached_generation(self):
        now = [100.]
        runtime, calls = self.runtime(clock=lambda: now[0])
        view = ApplicationView(runtime, clock=lambda: now[0])
        view.capture_once()
        original_snapshot, observed = view.snapshot, []
        def replaced_snapshot():
            body = original_snapshot()
            observed.append(body)
            # A newer cache image supersedes this HTTP body before issuance.
            # Raw runtime revision deliberately stays unchanged.
            view.capture_once()
            return body
        view.snapshot = replaced_snapshot
        http = HTTPFixture(view)
        try:
            code, state = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertEqual(len(observed), 1)
            self.assertIsNone(state["control"]["lease"])
            self.assertEqual(state["control"]["lease_seconds"], 0)
            self.assertEqual(runtime.broker.leases, {})
            self.assertEqual(runtime._state_revision, 0)
            self.assertEqual(calls, [])
        finally:
            http.close()
            view.close()

    def test_pending_local_lifecycle_revokes_old_lease_without_changing_revision(self):
        runtime, calls = self.runtime()
        entered, release = threading.Event(), threading.Event()
        lock_entered, lock_release = threading.Event(), threading.Event()
        def declined_initialize(startup_confirmed=False):
            # A lifecycle refusal need not increment the runtime revision.
            entered.set()
            if not release.wait(3):
                raise RuntimeError("Offline local request pause was not released")
            raise RuntimeError("Offline local Initialize was deliberately declined")
        runtime.initialize = declined_initialize
        view = ApplicationView(runtime)
        view.capture_once()
        http = HTTPFixture(view)
        holder = None
        try:
            code, state = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            lease, revision = state["control"]["lease"], state["state_revision"]
            self.assertIsNotNone(lease)
            def hold_runtime():
                with runtime._lock:
                    lock_entered.set()
                    lock_release.wait(3)
            holder = threading.Thread(target=hold_runtime)
            holder.start()
            self.assertTrue(lock_entered.wait(1))
            view.start()
            start = time.monotonic()
            view.initialize(True)
            self.assertLess(time.monotonic() - start, .2)
            self.assertTrue(entered.wait(1))
            code, pending = http.exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertEqual(pending["local_request_pending"], "initialize")
            self.assertIsNone(pending["control"]["lease"])
            self.assertFalse(pending["control"]["enabled"])
            lock_release.set()
            holder.join(1)
            request = self.command(state)
            code, result = http.exchange("/commands", dict(request=request, lease=lease))
            self.assertEqual(code, 409)
            self.assertEqual(result["error"], "LOCAL_LIFECYCLE_PENDING")
            release.set()
            wait_until(lambda: view.snapshot()["local_request_pending"] is None)
            view.capture_once()
            self.assertEqual(runtime._state_revision, revision)
            code, result = http.exchange("/commands", dict(request=request, lease=lease))
            self.assertEqual(code, 409)
            self.assertEqual(result["error"], "COMMAND_LEASE_CONTEXT_CHANGED")
            self.assertEqual(runtime.broker.records, {})
            self.assertIsNone(runtime._pending)
            self.assertEqual(calls, [])
        finally:
            lock_release.set()
            release.set()
            if holder is not None:
                holder.join(1)
            view.close()
            http.close()

    def test_fifth_vi_connection_is_refused_and_all_four_slots_recover(self):
        store, clients = HoldingIngressStore(), []
        server = SharedStateServer(("127.0.0.1", 0), store)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01))
        worker.daemon = True
        worker.start()
        def connect():
            client = socket.create_connection(server.server_address, timeout=1)
            clients.append(client)
            return client
        def occupy_four(total):
            group = []
            for unused in range(4):
                client = connect()
                client.sendall(struct.pack("!I", len(b"offline-probe")) + b"offline-probe")
                group.append(client)
            wait_until(lambda: store.entered == total and store.active == 4)
            return group
        def expect_refused(expected_rejections):
            start = time.monotonic()
            extra = connect()
            try:
                try:
                    received = extra.recv(1)
                except OSError:
                    received = b""  # Windows may report a reset instead of EOF.
                self.assertEqual(received, b"")
                self.assertLess(time.monotonic() - start, .5)
                wait_until(lambda: store.rejected == expected_rejections)
                self.assertEqual(store.last_error, "VI_INGRESS_HANDLER_LIMIT")
            finally:
                extra.close()
        def drain(group):
            store.release.set()
            for client in group:
                self.assertTrue(recv_message(client, 1024)["ok"])
                client.close()
            wait_until(lambda: store.active == 0)
            # Active count falls before the handler's final semaphore release.
            def all_slots_available():
                acquired = 0
                try:
                    for unused in range(4):
                        if not server._slots.acquire(False):
                            return False
                        acquired += 1
                    return True
                finally:
                    for unused in range(acquired):
                        server._slots.release()
            wait_until(all_slots_available)
        try:
            first = occupy_four(4)
            expect_refused(1)
            drain(first)
            store.release.clear()
            second = occupy_four(8)
            expect_refused(2)
            # Overload reporting itself must not wait for the store lock.
            with store.lock:
                extra = connect()
                start = time.monotonic()
                try:
                    received = extra.recv(1)
                except OSError:
                    received = b""
                self.assertEqual(received, b"")
                self.assertLess(time.monotonic() - start, .5)
                self.assertEqual(server.handler_limit_rejections, 3)
                self.assertEqual(store.rejected, 2)
                extra.close()
            drain(second)
            self.assertEqual(store.entered, 8)
        finally:
            store.release.set()
            for client in clients:
                client.close()
            wait_until(lambda: store.active == 0)
            server.shutdown()
            server.server_close()
            worker.join(1)
            self.assertFalse(worker.is_alive())

    def test_vi_server_close_joins_partial_frame_handler_before_replacement(self):
        entered, handlers = threading.Event(), []
        class TracedServer(SharedStateServer):
            def process_request_thread(self, request, address):
                handlers.append(threading.current_thread())
                entered.set()
                return SharedStateServer.process_request_thread(self, request, address)
        store = HoldingIngressStore()
        server = TracedServer(("127.0.0.1", 0), store)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01))
        worker.daemon = True
        worker.start()
        client = socket.create_connection(server.server_address, timeout=1)
        try:
            client.sendall(b"\x00")  # Handler waits for the remaining 3 header bytes.
            self.assertTrue(entered.wait(1))
            self.assertTrue(handlers[0].is_alive())
            server.shutdown()
            worker.join(1)
            start = time.monotonic()
            server.server_close()
            self.assertLess(time.monotonic() - start, 3)
            self.assertFalse(handlers[0].is_alive())
            self.assertEqual(store.entered, 0)
            self.assertEqual(store.rejected, 1)
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            for handler in handlers:
                handler.join(3)
                self.assertFalse(handler.is_alive())

    def test_runtime_join_does_not_claim_shutdown_while_watchdog_is_alive(self):
        runtime, calls = self.runtime()
        entered, release = threading.Event(), threading.Event()
        def blocked_watchdog():
            entered.set()
            release.wait(3)
        watchdog = threading.Thread(target=blocked_watchdog)
        watchdog.daemon = True
        runtime._watchdog = watchdog
        watchdog.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertFalse(runtime.join(.01))
            self.assertTrue(runtime._watchdog_stop.is_set())
            release.set()
            self.assertTrue(runtime.join(1))
            self.assertFalse(watchdog.is_alive())
            self.assertEqual(calls, [])
        finally:
            release.set()
            watchdog.join(1)

    def test_control_build_fingerprint_covers_execution_and_isolation_modules(self):
        source_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                                  "legacy", "xp_acq_control"))
        names = ("cooperative_execution.py", "isolated_backend.py", "isolated_wire.py", "isolated_worker.py",
                 "application_view.py", "journal_worker.py")
        with tempfile.TemporaryDirectory() as directory:
            root = os.path.join(directory, "source-copy")
            shutil.copytree(source_root, root)
            baseline = control_identity(root)["build_id"]
            for name in names:
                path = os.path.join(root, "elyse_agent", name)
                with open(path, "rb") as stream:
                    before = stream.read()
                try:
                    with open(path, "ab") as stream:
                        stream.write(b"\n# offline fingerprint mutation\n")
                    self.assertNotEqual(control_identity(root)["build_id"], baseline, name)
                finally:
                    with open(path, "wb") as stream:
                        stream.write(before)
                self.assertEqual(control_identity(root)["build_id"], baseline, name)

    def failed_start_drains_journal(self, use_startup_helper):
        entered, release = threading.Event(), threading.Event()
        original_journal = AlarmJournal
        class PausedJournal(original_journal):
            def append(self, state, event):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("Offline SQLite pause was not released")
                return original_journal.append(self, state, event)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            with mock.patch.object(cooling_safety, "AlarmJournal", PausedJournal):
                alarm = CoolingSafety.with_journal(path, "integration")
                runtime, calls = self.runtime(cooling=alarm)
                view = ApplicationView(runtime)
                listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                cleanup = None
                try:
                    wait_until(lambda: alarm.snapshot()["journal_ready"])
                    arm_cooling_baseline(alarm)
                    alarm.observe(dict(SECTION=dict(fault=True, quality="FRESH", causes=[]),
                                       CANON=dict(fault=False, quality="FRESH", causes=[])), True, 1)
                    self.assertTrue(entered.wait(1))
                    self.assertFalse(alarm.journal._thread.daemon)
                    self.assertIsNone(runtime._thread)
                    with self.assertRaises(OSError):
                        ControlHTTPServer(listener.getsockname(), view, READ_KEY, COMMAND_KEY)
                    resources = dict(runtime=runtime, view=view, cooling=alarm, timeout=1)
                    if use_startup_helper:
                        cleanup = StartupCleanup(**resources)
                        start = time.monotonic()
                        cleanup.start()
                        self.assertLess(time.monotonic() - start, .2)
                        self.assertFalse(cleanup.worker.daemon)
                        release.set()
                        cleanup.worker.join(2)
                        self.assertFalse(cleanup.worker.is_alive())
                        self.assertTrue(cleanup.completed, cleanup.errors)
                        self.assertEqual(cleanup.errors, [])
                    else:
                        release.set()
                        self.assertEqual(cleanup_failed_start(**resources), [])
                    self.assertTrue(alarm.journal.status()["stopped"])
                    self.assertFalse(alarm.journal._thread.is_alive())
                    self.assertEqual(alarm.snapshot()["journal_pending"], 0)
                    self.assertEqual(alarm.snapshot()["journal_committed"], 1)
                    self.assertEqual(calls, [])
                    stored = original_journal(path, "integration")
                    try:
                        self.assertEqual([row["kind"] for row in stored.events()], ["CIRCULATION_LOST"])
                        clean = stored.db.execute(
                            "SELECT clean FROM cooling_writer_state WHERE name='integration'").fetchone()[0]
                        self.assertEqual(clean, 1)
                    finally:
                        stored.close()
                finally:
                    release.set()
                    if cleanup is not None:
                        cleanup.worker.join(2)
                    self.assertTrue(alarm.close(3))
                    listener.close()
                    view.close()

    def test_cleanup_failed_start_after_bind_failure_drains_real_sqlite_writer(self):
        self.failed_start_drains_journal(False)

    def test_startup_cleanup_after_bind_failure_drains_real_sqlite_writer(self):
        self.failed_start_drains_journal(True)


if __name__ == "__main__":
    unittest.main()
