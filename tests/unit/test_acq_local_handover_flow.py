"""Local VI-to-Python handover acceptance; Python 3.4, temporary/synthetic only.

No live process inventory, XP, NI imports, native child, sockets, cards or
instrument commands. The only owner started by these tests is a RAM fixture.
"""
import copy
import json
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker, RecoveryRequired
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.handover_recovery import HANDOVER_CONFIRMATION, LocalHandoverVerifier
from tests.unit.test_acq_cold_recovery_bridge import synthetic_xml


class RamBackend(object):
    control_profile = "offline_ram_fixture"
    stage_controls_verified = False

    def __init__(self, events):
        self.events, self.resource_count = events, 0
        self.initialized = threading.Event()

    def initialize(self, cancel, startup_confirmed=False):
        if startup_confirmed is not True or cancel.is_set():
            raise AssertionError("RAM fixture requires qualified startup")
        self.events.append("RAM_INITIALIZE")
        self.resource_count = 1
        self.initialized.set()

    def read_snapshot(self, cancel):
        return dict(source="offline_ram_fixture", simulated=True, banks={})

    def close(self):
        self.events.append("RAM_CLOSE")
        self.resource_count = 0


class LocalHandoverFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "offline.ownership")
        self.prior = OwnershipMarker(self.path, "a" * 32, "b" * 64, process_id=88)
        self.prior.acquire()
        with open(self.path, "rb") as source:
            self.original = source.read()
        self.now, self.events, self.inventory_calls = [1000.0], [], []
        self.inventory_hook = None
        self.process_rows = [dict(pid=99, parent=4, name="pythonw.exe"),
                             dict(pid=100, parent=4, name="LabVIEW.exe")]

        def inventory():
            self.inventory_calls.append(len(self.inventory_calls) + 1)
            if self.inventory_hook is not None:
                self.inventory_hook(len(self.inventory_calls))
            return dict(pid=99, observed_monotonic=self.now[0],
                        processes=copy.deepcopy(self.process_rows))

        self.verifier = LocalHandoverVerifier(99, inventory, lambda: self.now[0])
        self.identity = dict(runtime_protocol_version=2, session_id="c" * 32, build_id="d" * 64)
        self.guard = OwnershipMarker(self.path, self.identity["session_id"],
                                     self.identity["build_id"], process_id=99,
                                     quiescence_checker=self.verifier)
        self.backend = RamBackend(self.events)

        def factory():
            # A marker approved for recovery is not itself NI initialization.
            # The runtime must acquire a NEW current-session token first.
            self.events.append("RAM_FACTORY")
            self.assertTrue(os.path.isfile(self.guard.snapshot()["recovery_audit"]))
            self.assertTrue(self.guard.snapshot()["owns_current_marker"])
            return self.backend

        self.runtime = AcquisitionControlRuntime(factory, recovery_guard=self.guard,
            handover_verifier=self.verifier, identity=self.identity, clock=lambda: self.now[0],
            period=.02)
        self.publisher = DualModeTelemetryPublisher(self.runtime, ("127.0.0.1", 1), b"r" * 32,
            clock=lambda: self.now[0])
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        if self.runtime._thread is not None:
            self.runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(self.runtime.join(3), "RAM owner failed to stop")
        self.publisher.close()
        self.folder.cleanup()

    def handover(self, **overrides):
        arguments = dict(startup_confirmed=True, electrical_off_confirmed=True,
                         confirmation=HANDOVER_CONFIRMATION, operator="synthetic local operator")
        arguments.update(overrides)
        return self.runtime.initialize_after_handover(**arguments)

    def assert_original_marker(self):
        with open(self.path, "rb") as source:
            self.assertEqual(source.read(), self.original)

    def audits(self):
        return [os.path.join(self.folder.name, name) for name in os.listdir(self.folder.name)
                if name.startswith("offline.ownership.recovery_") and name.endswith(".json")]

    def test_recent_vi_blocks_before_recovery_inventory_or_backend_factory(self):
        self.assertTrue(self.runtime.snapshot()["local_handover_available"])
        self.publisher.ingest(synthetic_xml(), "127.0.0.1")
        with self.assertRaisesRegex(RuntimeError, "LabVIEW telemetry is still arriving"):
            self.handover()
        self.assert_original_marker()
        self.assertEqual(self.inventory_calls, [])
        self.assertEqual(self.events, [])
        self.assertEqual(self.audits(), [])
        self.assertEqual(self.runtime.snapshot()["state"], "RECOVERY_REQUIRED")

    def test_silence_alone_never_recovers_prior_marker(self):
        self.publisher.ingest(synthetic_xml(), "127.0.0.1")
        self.now[0] += 60
        with self.assertRaises(RuntimeError):
            self.runtime.initialize(startup_confirmed=True)
        self.assert_original_marker()
        self.assertEqual(self.events, [])
        self.assertEqual(self.inventory_calls, [])

    def test_explicit_handover_archives_exact_marker_then_admits_ram_initialize(self):
        self.assertEqual(self.events, [])
        self.handover()
        state = self.runtime.snapshot()
        self.assertEqual(state["state"], "INITIALIZING")
        self.assertFalse(state["local_handover_available"])
        self.assertTrue(state["recovery"]["owns_current_marker"])
        self.assertEqual(self.inventory_calls, [1, 2])
        self.assertEqual(self.events, [])  # Admission is not native execution.
        self.assertEqual(len(self.audits()), 1)
        with open(self.audits()[0], "r", encoding="utf-8") as source:
            audit = json.load(source)
        self.assertEqual(audit["original_marker_utf8"].encode("utf-8"), self.original)
        self.assertFalse(audit["hardware_commands_sent"])
        self.assertTrue(audit["proof"]["operator_attestation"]["external_ni_tasks_released"])
        self.assertFalse(audit["proof"]["ni_task_release_independently_verified"])
        with open(self.path, "rb") as source:
            current = OwnershipMarker._decode(source.read())
        self.assertEqual(current["session_id"], self.identity["session_id"])
        self.assertEqual(current["owner_pid"], 99)

        self.runtime.start()  # RAM fixture only; no native child or hardware.
        self.assertTrue(self.backend.initialized.wait(2))
        end = time.monotonic() + 2
        while self.runtime.snapshot()["state"] != "RUNNING" and time.monotonic() < end:
            time.sleep(.005)
        self.assertEqual(self.runtime.snapshot()["state"], "RUNNING")
        self.assertEqual(self.events[:2], ["RAM_FACTORY", "RAM_INITIALIZE"])
        with self.assertRaisesRegex(ValueError, "INGRESS_DISABLED"):
            self.publisher.ingest(synthetic_xml(), "127.0.0.1")

    def test_all_current_local_confirmations_are_required_before_any_recovery(self):
        for override in (dict(startup_confirmed=False), dict(electrical_off_confirmed=False),
                         dict(confirmation=None), dict(confirmation="OFF"), dict(operator="")):
            with self.assertRaises(ValueError):
                self.handover(**override)
            self.assert_original_marker()
            self.assertEqual(self.runtime.snapshot()["state"], "RECOVERY_REQUIRED")
        self.assertEqual(self.inventory_calls, [])
        self.assertEqual(self.events, [])
        self.assertEqual(self.audits(), [])

    def test_retained_python_child_and_old_pid_reuse_each_refuse_recovery(self):
        for pid, name in ((102, "python.exe"), (102, "pythonw.exe"),
                          (88, "pythonw.exe"), (88, "unrelated.exe")):
            self.process_rows.append(dict(pid=pid, parent=88, name=name))
            with self.assertRaises(RecoveryRequired):
                self.handover()
            self.process_rows.pop()
            self.assert_original_marker()
            self.assertEqual(self.runtime.snapshot()["state"], "RECOVERY_REQUIRED")
        self.assertEqual(self.events, [])
        self.assertEqual(self.audits(), [])

    def test_current_native_owner_or_uncertain_cleanup_cannot_use_prior_handover(self):
        for field, value in (("_backend", self.backend), ("_marker_cleanup_uncertain", True),
                             ("_cold_prior_recovery_bridge", False), ("_pending", "close"),
                             ("_operation", "initialize"), ("_shutdown_requested", True),
                             ("_state", "FAULT")):
            original = getattr(self.runtime, field)
            setattr(self.runtime, field, value)
            try:
                self.assertFalse(self.runtime.snapshot()["local_handover_available"])
                with self.assertRaisesRegex(RuntimeError, "cold prior-owner recovery state"):
                    self.handover()
                self.assert_original_marker()
            finally:
                setattr(self.runtime, field, original)
        self.assertEqual(self.inventory_calls, [])
        self.assertEqual(self.events, [])

    def test_vi_resuming_during_audit_recheck_blocks_initialize_and_retains_backup(self):
        def resume_after_audit(call):
            if call == 2:
                self.publisher.ingest(synthetic_xml(), "127.0.0.1")
        self.inventory_hook = resume_after_audit
        with self.assertRaisesRegex(RuntimeError, "LabVIEW telemetry is still arriving"):
            self.handover()
        self.assertEqual(self.inventory_calls, [1, 2])
        self.assertEqual(self.events, [])
        self.assertIsNone(self.runtime._backend)
        self.assertIsNone(self.runtime._pending)
        self.assertEqual(self.runtime.snapshot()["state"], "IDLE")
        self.assertFalse(self.guard.snapshot()["owns_current_marker"])
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(len(self.audits()), 1)
        with open(self.audits()[0], "r", encoding="utf-8") as source:
            self.assertEqual(json.load(source)["original_marker_utf8"].encode("utf-8"), self.original)

    def test_concurrent_vi_seen_while_owner_lock_busy_still_blocks_post_audit_initialize(self):
        rejected = []
        def incoming_vi():
            try:
                self.publisher.ingest(synthetic_xml(), "127.0.0.1")
            except ValueError as error:
                rejected.append(str(error))
        def concurrent_receipt(call):
            if call == 2:
                worker = threading.Thread(target=incoming_vi)
                worker.start()
                worker.join(2)
                self.assertFalse(worker.is_alive(), "Synthetic VI ingress blocked on owner lock")
        self.inventory_hook = concurrent_receipt
        with self.assertRaisesRegex(RuntimeError, "LabVIEW telemetry is still arriving"):
            self.handover()
        self.assertEqual(rejected, ["OWNER_STATE_BUSY_VI_NOT_ADMITTED"])
        self.assertEqual(self.publisher.vi_accepted, 0)
        self.assertEqual(self.publisher.last_vi_seen, self.now[0])
        self.assertEqual(self.events, [])
        self.assertIsNone(self.runtime._backend)
        self.assertIsNone(self.runtime._pending)
        self.assertEqual(self.runtime.snapshot()["state"], "IDLE")
        self.assertEqual(len(self.audits()), 1)

    def test_new_python_during_second_check_preserves_original_marker_and_no_factory(self):
        def late_child(call):
            if call == 2:
                self.process_rows.append(dict(pid=102, parent=88, name="python.exe"))
        self.inventory_hook = late_child
        with self.assertRaises(RecoveryRequired):
            self.handover()
        self.assert_original_marker()
        self.assertEqual(self.runtime.snapshot()["state"], "RECOVERY_REQUIRED")
        self.assertEqual(self.events, [])
        self.assertEqual(len(self.audits()), 1)  # Approval record is not a completed recovery.

    def test_audit_disk_failure_preserves_prior_marker_and_blocks_initialize(self):
        with mock.patch("legacy.xp_acq_control.elyse_agent.acquisition_recovery.os.fsync",
                        side_effect=OSError("synthetic audit disk unavailable")):
            with self.assertRaisesRegex(RecoveryRequired, "audit persistence failed"):
                self.handover()
        self.assert_original_marker()
        self.assertEqual(self.inventory_calls, [1])
        self.assertEqual(self.runtime.snapshot()["state"], "RECOVERY_REQUIRED")
        self.assertEqual(self.events, [])

    def test_expired_confirmation_during_audit_preserves_marker(self):
        def expire(call):
            if call == 2:
                self.now[0] += 61
        self.inventory_hook = expire
        with self.assertRaisesRegex(RecoveryRequired, "expired"):
            self.handover()
        self.assert_original_marker()
        self.assertEqual(self.events, [])
        self.assertEqual(self.runtime.snapshot()["state"], "RECOVERY_REQUIRED")


if __name__ == "__main__":
    unittest.main()
