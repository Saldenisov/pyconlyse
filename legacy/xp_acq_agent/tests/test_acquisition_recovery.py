"""Persistent ownership/restart tests using fake backends and temp files only."""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_recovery import (
    OwnershipMarker, RecoveryRequired, MAX_MARKER_BYTES,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.elyse_agent.acquisition_gui import create_cold_runtime
from legacy.xp_acq_agent.tests.test_acquisition_runtime import FakeBackend, wait_state


def identity(session="a"):
    return dict(runtime_protocol_version=2, session_id=session * 32, build_id="b" * 64)


def proof(_record):
    return dict(verified=True, owner_process_absent=True, native_children_absent=True,
                ni_competitors_absent=True, method="OFFLINE_FAKE_QUIESCENCE_CHECKER")


class OwnershipMarkerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "installation.ownership")

    def tearDown(self):
        self.folder.cleanup()

    def marker(self, session="a", process_id=100, checker=None):
        return OwnershipMarker(self.path, session * 32, "b" * 64,
                               process_id=process_id, quiescence_checker=checker)

    def read(self):
        with open(self.path, "rb") as source:
            return source.read()

    def test_clean_cold_marker_creation_is_bounded_and_second_owner_cannot_overwrite(self):
        first, second = self.marker(), self.marker("c", 200)
        self.assertFalse(first.snapshot()["required"])
        first.acquire()
        raw = self.read()
        self.assertLess(len(raw), MAX_MARKER_BYTES)
        self.assertEqual(set(json.loads(raw.decode("utf-8"))),
                         {"kind", "session_id", "build_id", "owner_pid", "nonce"})
        self.assertFalse(first.snapshot()["required"])
        self.assertTrue(second.snapshot()["required"])
        with self.assertRaises(RecoveryRequired):
            second.acquire()
        self.assertEqual(self.read(), raw)
        self.assertFalse(second.release_after_cleanup())
        self.assertEqual(self.read(), raw)
        with self.assertRaises(ValueError):
            first.release_after_cleanup()
        self.assertEqual(self.read(), raw)
        self.assertTrue(first.release_after_cleanup(resources_quiescent=True))
        self.assertFalse(os.path.exists(self.path))

    def test_unrelated_malformed_or_oversized_marker_is_preserved(self):
        for raw in (b"unrelated", b"{}", b"x" * (MAX_MARKER_BYTES + 1)):
            with open(self.path, "wb") as target:
                target.write(raw)
            marker = self.marker("c", 200, proof)
            self.assertTrue(marker.snapshot()["required"])
            with self.assertRaises(RecoveryRequired):
                marker.recover(electrical_off_confirmed=True)
            self.assertEqual(self.read(), raw)

    def test_no_checker_or_parent_pid_absence_alone_never_clears_prior_marker(self):
        first = self.marker()
        first.acquire()
        raw = self.read()
        for checker in (None, lambda record: True,
                        lambda record: dict(verified=True, owner_process_absent=True, method="PID_ONLY")):
            second = self.marker("c", 200, checker)
            with self.assertRaises(RecoveryRequired):
                second.recover(electrical_off_confirmed=True)
            self.assertEqual(self.read(), raw)

    def test_local_recovery_requires_off_and_all_qualified_quiescence_facts(self):
        self.marker().acquire()
        second = self.marker("c", 200, proof)
        with self.assertRaises(ValueError):
            second.recover()
        result = second.recover(electrical_off_confirmed=True)
        self.assertFalse(result["required"])
        self.assertFalse(os.path.exists(self.path))
        self.assertIn("UNINITIALIZED", second.snapshot()["reason"])

    def test_current_session_or_current_process_marker_cannot_be_recovered(self):
        first = self.marker()
        first.acquire()
        for marker in (first, self.marker("c", 100, proof)):
            with self.assertRaises(RecoveryRequired):
                marker.recover(electrical_off_confirmed=True)
        self.assertTrue(os.path.exists(self.path))

    def test_replaced_marker_is_not_removed_by_cleanup_or_recovery(self):
        first = self.marker()
        first.acquire()
        unrelated = b"unrelated replacement"
        with open(self.path, "wb") as target:
            target.write(unrelated)
        with self.assertRaises(RecoveryRequired):
            first.release_after_cleanup(resources_quiescent=True)
        self.assertEqual(self.read(), unrelated)
        self.assertTrue(first.snapshot()["required"])

    def test_marker_change_during_checker_is_preserved(self):
        self.marker().acquire()
        def replacing_checker(record):
            with open(self.path, "wb") as target:
                target.write(b"changed during verification")
            return proof(record)
        marker = self.marker("c", 200, replacing_checker)
        with self.assertRaises(RecoveryRequired):
            marker.recover(electrical_off_confirmed=True)
        self.assertEqual(self.read(), b"changed during verification")


class GuardedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "installation.ownership")
        self.runtimes = []

    def tearDown(self):
        for runtime, backend in reversed(self.runtimes):
            if backend is not None:
                backend.fail_close = False
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(3))
        self.folder.cleanup()

    def runtime(self, session="a", backend=None, checker=None):
        backend = backend or FakeBackend()
        runtime_identity = identity(session)
        guard = OwnershipMarker(self.path, runtime_identity["session_id"], runtime_identity["build_id"],
                                process_id=100 if session == "a" else 200,
                                quiescence_checker=checker)
        factory = Mock(return_value=backend)
        runtime = AcquisitionRuntime(factory, period=.02, recovery_guard=guard, identity=runtime_identity)
        runtime.start()
        self.runtimes.append((runtime, backend))
        return runtime, backend, factory

    def test_dirty_prior_marker_is_reported_at_cold_boot_without_factory_or_replay(self):
        old = OwnershipMarker(self.path, "a" * 32, "b" * 64, process_id=100)
        old.acquire()
        with open(self.path, "rb") as source:
            raw = source.read()
        runtime, backend, factory = self.runtime("c")
        state = runtime.snapshot()
        self.assertEqual(state["state"], "RECOVERY_REQUIRED")
        self.assertTrue(state["recovery"]["required"])
        self.assertTrue(state["recovery"]["protection_active"])
        self.assertEqual(state["resource_count"], 0)
        self.assertIsNone(state["latest"])
        self.assertTrue(state["stale"])
        with self.assertRaises(RuntimeError):
            runtime.initialize(startup_confirmed=True)
        with self.assertRaises(RecoveryRequired):
            runtime.recover_local(electrical_off_confirmed=True)
        factory.assert_not_called()
        runtime.request_shutdown()
        wait_state(runtime, "STOPPED")
        with open(self.path, "rb") as source:
            self.assertEqual(source.read(), raw)

    def test_marker_is_created_before_factory_then_removed_only_after_successful_cleanup(self):
        runtime, backend, factory = self.runtime()
        def construct():
            self.assertTrue(os.path.exists(self.path))
            return backend
        factory.side_effect = construct
        runtime.initialize(startup_confirmed=True)
        wait_state(runtime, "RUNNING")
        self.assertTrue(os.path.exists(self.path))
        runtime.deinitialize()
        wait_state(runtime, "IDLE")
        self.assertEqual(backend.close_calls, 1)
        self.assertFalse(os.path.exists(self.path))

    def test_marker_changed_after_queue_is_rechecked_before_factory_effects(self):
        runtime_identity = identity()
        guard = OwnershipMarker(self.path, runtime_identity["session_id"], runtime_identity["build_id"], process_id=100)
        factory = Mock(return_value=FakeBackend())
        runtime = AcquisitionRuntime(factory, period=.02, recovery_guard=guard, identity=runtime_identity)
        self.runtimes.append((runtime, None))
        runtime.initialize(startup_confirmed=True)
        with open(self.path, "wb") as target:
            target.write(b"changed after accepted initialization")
        runtime.start()
        wait_state(runtime, "RECOVERY_REQUIRED")
        factory.assert_not_called()
        runtime.request_shutdown()
        wait_state(runtime, "STOPPED")
        with open(self.path, "rb") as source:
            self.assertEqual(source.read(), b"changed after accepted initialization")

    def test_failed_cleanup_keeps_dirty_marker_and_next_session_blocks(self):
        runtime, backend, factory = self.runtime()
        runtime.initialize(startup_confirmed=True)
        wait_state(runtime, "RUNNING")
        backend.fail_close = True
        runtime.deinitialize()
        wait_state(runtime, "FAULT")
        self.assertTrue(os.path.exists(self.path))
        blocked, other, other_factory = self.runtime("c")
        self.assertEqual(blocked.snapshot()["state"], "RECOVERY_REQUIRED")
        other_factory.assert_not_called()
        self.assertEqual(runtime.snapshot()["resource_count"], 2)

    def test_explicit_verified_recovery_returns_only_cold_idle(self):
        OwnershipMarker(self.path, "a" * 32, "b" * 64, process_id=100).acquire()
        runtime, backend, factory = self.runtime("c", checker=proof)
        before = runtime.snapshot()["state_revision"]
        runtime.recover_local(electrical_off_confirmed=True)
        state = runtime.snapshot()
        self.assertEqual(state["state"], "IDLE")
        self.assertFalse(state["recovery"]["required"])
        self.assertFalse(state["auto_initialize"])
        self.assertGreater(state["state_revision"], before)
        self.assertIsNone(state["latest"])
        factory.assert_not_called()

    def test_factory_exception_without_returned_owner_never_certifies_clean_release(self):
        runtime, backend, factory = self.runtime(checker=proof)
        factory.side_effect = RuntimeError("synthetic partial factory failure before owner return")
        runtime.initialize(startup_confirmed=True)
        wait_state(runtime, "RECOVERY_REQUIRED")
        self.assertTrue(os.path.exists(self.path))
        self.assertTrue(runtime.snapshot()["recovery"]["required"])
        with self.assertRaises(RecoveryRequired):
            runtime.recover_local(electrical_off_confirmed=True)
        self.assertTrue(runtime._marker_cleanup_uncertain)
        self.assertTrue(os.path.exists(self.path))
        runtime.request_shutdown()
        wait_state(runtime, "STOPPED")
        self.assertTrue(os.path.exists(self.path))
        # The real guard requires a new session/process plus qualified proof;
        # no same-current-owner recovery shortcut is introduced.
        restarted, other, other_factory = self.runtime("c", checker=proof)
        restarted.recover_local(electrical_off_confirmed=True)
        self.assertEqual(restarted.snapshot()["state"], "IDLE")
        other_factory.assert_not_called()
        restarted.initialize(startup_confirmed=True)
        wait_state(restarted, "RUNNING")
        restarted.deinitialize()
        wait_state(restarted, "IDLE")
        self.assertFalse(os.path.exists(self.path))

    def test_successful_guard_recovery_defensively_resets_stale_cleanup_bookkeeping(self):
        OwnershipMarker(self.path, "a" * 32, "b" * 64, process_id=100).acquire()
        runtime, backend, factory = self.runtime("c", checker=proof)
        # Synthetic stale bookkeeping, not permission to bypass the real
        # current-session/current-process marker refusal tested separately.
        runtime._marker_cleanup_uncertain = True
        runtime.recover_local(electrical_off_confirmed=True)
        self.assertFalse(runtime._marker_cleanup_uncertain)
        factory.assert_not_called()
        runtime.initialize(startup_confirmed=True)
        wait_state(runtime, "RUNNING")
        runtime.deinitialize()
        wait_state(runtime, "IDLE")
        self.assertFalse(os.path.exists(self.path))

    def test_recovery_latch_does_not_clear_when_someone_deletes_prior_marker(self):
        OwnershipMarker(self.path, "a" * 32, "b" * 64, process_id=100).acquire()
        runtime, backend, factory = self.runtime("c")
        os.unlink(self.path)  # Simulated external deletion is not quiescence proof.
        self.assertTrue(runtime.snapshot()["recovery"]["required"])
        self.assertEqual(runtime.snapshot()["state"], "RECOVERY_REQUIRED")
        with self.assertRaises(RuntimeError):
            runtime.initialize(startup_confirmed=True)
        factory.assert_not_called()

    def test_atomic_fence_rejects_old_session_old_revision_and_recovery_before_callback(self):
        runtime, backend, factory = self.runtime()
        callback = Mock()
        with self.assertRaises(RuntimeError):
            runtime.fenced_local_request("c" * 32, 0, callback)
        with self.assertRaises(RuntimeError):
            runtime.fenced_local_request("a" * 32, 1, callback)
        with self.assertRaises(ValueError):
            runtime.fenced_local_request("a" * 32, True, callback)
        callback.assert_not_called()
        runtime.fenced_local_request("a" * 32, 0, lambda: runtime.initialize(startup_confirmed=True))
        with self.assertRaises(RuntimeError):
            runtime.fenced_local_request("a" * 32, 0, callback)
        callback.assert_not_called()
        wait_state(runtime, "RUNNING")
        self.assertGreaterEqual(runtime.snapshot()["state_revision"], 2)

    def test_revision_changes_for_accepted_requests_completion_and_fault(self):
        runtime, backend, factory = self.runtime()
        initial = runtime.snapshot()["state_revision"]
        with self.assertRaises(ValueError):
            runtime.initialize()
        self.assertEqual(runtime.snapshot()["state_revision"], initial)
        runtime.initialize(startup_confirmed=True)
        wait_state(runtime, "RUNNING")
        running = runtime.snapshot()["state_revision"]
        self.assertGreaterEqual(running, initial + 2)
        backend.fail_read = True
        wait_state(runtime, "FAULT")
        self.assertGreater(runtime.snapshot()["state_revision"], running)

    def test_guard_does_not_claim_machine_wide_exclusivity_or_process_verification(self):
        runtime, backend, factory = self.runtime()
        state = runtime.snapshot()
        self.assertIn("installation_config_path_only", state["recovery"]["scope"])
        self.assertFalse(state["recovery"]["orphan_absence_verified"])
        json.dumps(state, allow_nan=False)

    def test_another_marker_observed_after_cold_construction_promotes_recovery_state(self):
        runtime, backend, factory = self.runtime("c")
        OwnershipMarker(self.path, "a" * 32, "b" * 64, process_id=100).acquire()
        state = runtime.snapshot()
        self.assertEqual(state["state"], "RECOVERY_REQUIRED")
        self.assertTrue(state["recovery"]["required"])
        self.assertGreater(state["state_revision"], 0)
        factory.assert_not_called()

    def test_unconfirmed_native_child_cleanup_keeps_ni_owner_and_marker(self):
        from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend
        from legacy.xp_acq_agent.tests.test_acquisition_stage_backend import FakeFocalCommand, fake_owner
        native, owner = FakeFocalCommand(), fake_owner()
        backend = CardBackend(Mock(return_value=owner), focal_command=native)
        runtime, backend, factory = self.runtime(backend=backend)
        runtime.initialize(startup_confirmed=True)
        wait_state(runtime, "RUNNING")
        native.blocked = True
        try:
            runtime.request_shutdown(electrical_off_confirmed=True)
            wait_state(runtime, "FAULT")
            self.assertTrue(os.path.exists(self.path))
            self.assertIs(backend.owner, owner)
            owner.close.assert_not_called()
            self.assertGreater(runtime.snapshot()["resource_count"], 0)
        finally:
            native.blocked = False

    def test_production_gui_factory_always_installs_guard_and_demo_labels_its_absence(self):
        path = os.path.join(self.folder.name, "config.json")
        factory = Mock()
        runtime = create_cold_runtime(factory, .2, path)
        self.assertTrue(runtime.snapshot()["recovery"]["protection_active"])
        self.assertEqual(runtime.snapshot()["state"], "IDLE")
        self.assertFalse(os.path.exists(path + ".ownership"))
        demo = create_cold_runtime(factory, .2, path, demo=True)
        self.assertFalse(demo.snapshot()["recovery"]["protection_active"])
        self.assertEqual(demo.snapshot()["runtime_protocol_version"], 2)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
