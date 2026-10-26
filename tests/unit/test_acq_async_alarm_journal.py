"""Driver-free bounded journal tests, executable on actual Python 3.4."""
import copy
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent import cooling_safety
from legacy.xp_acq_control.elyse_agent.cooling_safety import (
    AlarmJournal, CoolingSafety, JOURNAL_RECONCILIATION_CONFIRMATION, utc)
from legacy.xp_acq_control.elyse_agent.journal_worker import JournalWorker


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("Offline journal synchronization condition not reached")


class Clock(object):
    def __init__(self, value=0.):
        self.value = value

    def __call__(self):
        return self.value


def circuits(fault=True):
    return dict(SECTION=dict(fault=fault, quality="FRESH", causes=[]),
                CANON=dict(fault=False, quality="FRESH", causes=[]))


def lose_after_baseline(alarm):
    """Journal tests begin after a distinct two-second green active baseline."""
    original, now = alarm.clock, alarm.clock()
    try:
        alarm.clock = lambda: now - cooling_safety.RECOVERY_SECONDS
        alarm.observe(circuits(False), True, -2)
        alarm.clock = lambda: now
        alarm.observe(circuits(False), True, -1)
    finally:
        alarm.clock = original
    alarm.observe(circuits(), True, 1)


def saved_incident(deadline=1120.):
    return dict(incidents=dict(CANON=dict(circuit="CANON", started_utc=utc(deadline - 120),
                deadline_utc=utc(deadline), deadline_epoch=deadline,
                deadline_monotonic=99999., causes=[])), stop_state="REQUESTED", stop_error="")


class Storage(object):
    def __init__(self, saved=None, block_load=False, block_write=False):
        self.saved, self.rows = copy.deepcopy(saved), []
        self.load_entered, self.load_release = threading.Event(), threading.Event()
        self.write_entered, self.write_release = threading.Event(), threading.Event()
        self.fail_write = False
        self.fail_load = False
        self.closed = False
        self.threads = []
        if not block_load:
            self.load_release.set()
        if not block_write:
            self.write_release.set()

    def load(self):
        self.threads.append(threading.current_thread().name)
        self.load_entered.set()
        if not self.load_release.wait(5):
            raise RuntimeError("Offline paused load was not released")
        if self.fail_load:
            raise IOError("injected load failure")
        return copy.deepcopy(self.saved)

    def events(self):
        return []

    def append(self, state, event):
        self.threads.append(threading.current_thread().name)
        self.write_entered.set()
        if not self.write_release.wait(5):
            raise RuntimeError("Offline paused write was not released")
        if self.fail_write:
            raise IOError("injected disk failure")
        self.saved = copy.deepcopy(state)
        self.rows.append(copy.deepcopy(event))

    def close(self):
        self.threads.append(threading.current_thread().name)
        self.closed = True


class AsyncAlarmJournalTests(unittest.TestCase):
    def test_history_gap_warns_but_does_not_block_current_healthy_writer(self):
        from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            old = AlarmJournal(path, "test")
            old.begin_session()
            old.close()
            alarm = CoolingSafety.with_journal(path, "test")
            runtime = AcquisitionControlRuntime(lambda: None, cooling=alarm)
            runtime._stop_qualified = lambda: True  # RAM-only independent permit seam.
            try:
                wait_until(lambda: alarm.snapshot()["journal_write_ready"])
                state = alarm.snapshot()
                self.assertTrue(state["journal_recovery_required"])
                self.assertFalse(state["journal_durable"])
                self.assertEqual(state["journal_storage_error"], "")
                runtime._start_permit(general=True)
                # Current failures and actual incidents still block starts.
                with alarm.lock:
                    alarm.incidents["test"] = dict(circuit="test", deadline_monotonic=time.monotonic()+30)
                with self.assertRaises(RuntimeError):
                    runtime._start_permit(general=True)
            finally:
                self.assertTrue(alarm.close(3))

    def make(self, storage, capacity=64, clock=None, wall=None):
        worker = JournalWorker(lambda: storage, validate_loaded=CoolingSafety._validate_saved,
                               capacity=capacity, retry_seconds=.01)
        alarm = CoolingSafety(journal=worker, clock=clock, wall_clock=wall)
        self.addCleanup(self.cleanup_alarm, alarm, storage)
        return alarm, worker

    @staticmethod
    def cleanup_alarm(alarm, storage):
        storage.fail_load = storage.fail_write = False
        storage.load_release.set()
        storage.write_release.set()
        # A snapshot adopts the persisted state before draining buffered events.
        wait_until(lambda: alarm.snapshot()["journal_ready"])
        assert alarm.close(3)

    def test_observe_and_countdown_do_not_wait_for_disk_commit(self):
        storage, clock = Storage(block_write=True), Clock()
        alarm, worker = self.make(storage, clock=clock, wall=Clock(1000.))
        wait_until(lambda: alarm.snapshot()["journal_durable"])
        start = time.monotonic()
        lose_after_baseline(alarm)
        self.assertLess(time.monotonic() - start, .2)
        self.assertTrue(storage.write_entered.wait(2))
        state = alarm.snapshot()
        self.assertTrue(state["active"])
        self.assertEqual(state["remaining_seconds"], 120.)
        self.assertFalse(state["journal_durable"])
        self.assertEqual(state["journal_pending"], 1)
        clock.value = 120.
        self.assertTrue(alarm.tick(True))
        self.assertEqual(alarm.snapshot()["stop_state"], "REQUESTED")
        self.assertFalse(alarm.close(0))
        self.assertTrue(worker._thread.is_alive())
        storage.write_release.set()
        self.assertTrue(alarm.close(3))
        self.assertEqual([row["kind"] for row in storage.rows],
                         ["CIRCULATION_LOST", "SHUTDOWN_REQUESTED"])
        self.assertEqual(set(storage.threads), {"ACQ-alarm-journal"})

    def test_initial_load_never_claims_health_and_merges_before_writing(self):
        storage = Storage(saved_incident(1060.), block_load=True)
        clock, wall = Clock(), Clock(1000.)
        alarm, worker = self.make(storage, clock=clock, wall=wall)
        self.assertTrue(storage.load_entered.wait(2))
        self.assertFalse(alarm.snapshot()["journal_ready"])
        self.assertIn("initial load", alarm.snapshot()["journal_error"])
        lose_after_baseline(alarm)
        self.assertEqual(alarm.snapshot()["remaining_seconds"], 120.)
        self.assertEqual(storage.rows, [])
        clock.value, wall.value = 10., 1010.
        storage.load_release.set()
        wait_until(lambda: alarm.snapshot()["journal_durable"])
        state = alarm.snapshot()
        self.assertEqual(set(row["circuit"] for row in state["circuits"]), {"CANON", "SECTION"})
        self.assertEqual(state["remaining_seconds"], 50.)
        self.assertEqual(state["stop_state"], "INTERRUPTED")
        self.assertEqual(set(storage.saved["incidents"]), {"CANON", "SECTION"})
        self.assertEqual(storage.saved["stop_state"], "INTERRUPTED")

    def test_failed_load_does_not_cancel_new_fault_deadline(self):
        storage, clock = Storage(), Clock()
        storage.fail_load = True
        alarm, worker = self.make(storage, clock=clock, wall=Clock(1000.))
        wait_until(lambda: "load failed" in alarm.snapshot()["journal_error"])
        lose_after_baseline(alarm)
        clock.value = 120.
        self.assertTrue(alarm.tick(True))
        self.assertEqual(storage.rows, [])
        self.assertFalse(alarm.snapshot()["journal_durable"])
        storage.fail_load = False
        wait_until(lambda: alarm.snapshot()["journal_durable"])
        self.assertEqual(alarm.snapshot()["stop_state"], "REQUESTED")

    def test_invalid_persisted_state_is_not_overwritten_by_new_observation(self):
        storage = Storage(dict(incidents={}, stop_state="NOT_A_STATE"))
        alarm, worker = self.make(storage)
        wait_until(lambda: "Invalid persisted alarm state" in alarm.snapshot()["journal_error"])
        lose_after_baseline(alarm)
        self.assertFalse(alarm.snapshot()["journal_ready"])
        self.assertFalse(alarm.snapshot()["journal_durable"])
        self.assertEqual(storage.rows, [])
        self.assertEqual(storage.saved["stop_state"], "NOT_A_STATE")
        # Explicit fixture repair, never an automatic production repair.
        storage.saved = None
        wait_until(lambda: alarm.snapshot()["journal_durable"])
        self.assertTrue(alarm.snapshot()["active"])

    def test_backward_wall_clock_does_not_grant_new_grace(self):
        storage = Storage(saved_incident(1120.))
        alarm, worker = self.make(storage, clock=Clock(5.), wall=Clock(900.))
        wait_until(lambda: alarm.snapshot()["journal_ready"])
        self.assertEqual(alarm.snapshot()["remaining_seconds"], 0.)
        self.assertTrue(alarm.tick(True))

    def test_overflow_is_sticky_explicit_and_never_durable(self):
        storage = Storage(block_write=True)
        alarm, worker = self.make(storage, capacity=1)
        wait_until(lambda: alarm.snapshot()["journal_ready"])
        lose_after_baseline(alarm)
        self.assertTrue(storage.write_entered.wait(2))
        alarm.stop_result("injected stop result")
        state = alarm.snapshot()
        self.assertEqual(state["journal_overflow"], 1)
        self.assertIn("admission failed", state["journal_error"])
        self.assertEqual(state["stop_state"], "FAILED")
        storage.write_release.set()
        wait_until(lambda: alarm.snapshot()["journal_pending"] == 0)
        self.assertFalse(alarm.snapshot()["journal_durable"])
        self.assertTrue(alarm.close(3))

    def test_write_failure_retries_same_receipt_until_commit(self):
        storage = Storage()
        storage.fail_write = True
        alarm, worker = self.make(storage)
        wait_until(lambda: alarm.snapshot()["journal_ready"])
        lose_after_baseline(alarm)
        wait_until(lambda: "injected disk failure" in alarm.snapshot()["journal_error"])
        self.assertEqual(alarm.snapshot()["journal_committed"], 0)
        self.assertFalse(alarm.close(0))
        storage.fail_write = False
        self.assertTrue(alarm.close(3))
        self.assertEqual(len(storage.rows), 1)
        self.assertEqual(alarm.snapshot()["journal_committed"], 1)
        self.assertTrue(alarm.snapshot()["journal_durable"])

    def test_fresh_recovery_does_not_claim_durable_before_clear_commit(self):
        storage, clock = Storage(), Clock()
        alarm, worker = self.make(storage, clock=clock)
        wait_until(lambda: alarm.snapshot()["journal_ready"])
        lose_after_baseline(alarm)
        wait_until(lambda: alarm.snapshot()["journal_durable"])
        storage.write_release.clear()
        alarm.observe(circuits(False), True, 2)
        clock.value = 2.
        alarm.observe(circuits(False), True, 3)
        self.assertFalse(alarm.snapshot()["active"])
        self.assertFalse(alarm.snapshot()["journal_durable"])
        storage.write_release.set()
        wait_until(lambda: alarm.snapshot()["journal_durable"])

    def test_sqlite_receipts_and_unclean_restart_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            journal = AlarmJournal(path, "test")
            self.assertEqual(journal.begin_session(), "")
            saved = saved_incident()
            event = dict(kind="CIRCULATION_LOST", journal_event_id="receipt-1")
            journal.append(saved, event)
            journal.append(saved, event)
            self.assertEqual(len(journal.events()), 1)
            journal.close()  # Deliberately simulate an unclean prior owner.
            alarm = CoolingSafety.with_journal(path, "test", wall_clock=Clock(1100.))
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                state = alarm.snapshot()
                self.assertTrue(state["active"])
                self.assertEqual(state["remaining_seconds"], 20.)
                self.assertIn("did not close cleanly", state["journal_error"])
                self.assertFalse(state["journal_durable"])
            finally:
                self.assertTrue(alarm.close(3))

    def test_clean_sqlite_restart_preserves_incident_and_no_new_grace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            clock, wall = Clock(), Clock(1000.)
            alarm = CoolingSafety.with_journal(path, "test", clock=clock, wall_clock=wall)
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                lose_after_baseline(alarm)
                wait_until(lambda: alarm.snapshot()["journal_durable"])
            finally:
                self.assertTrue(alarm.close(3))

            alarm = CoolingSafety.with_journal(path, "test", wall_clock=Clock(1050.))
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                self.assertEqual(alarm.snapshot()["remaining_seconds"], 70.)
                self.assertTrue(alarm.snapshot()["journal_durable"])
            finally:
                self.assertTrue(alarm.close(3))

    def test_uncertain_commit_retry_does_not_duplicate_sqlite_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path, calls = os.path.join(directory, "alarms.sqlite"), []
            class UncertainCommit(AlarmJournal):
                def append(self, state, event):
                    calls.append(event["journal_event_id"])
                    AlarmJournal.append(self, state, event)
                    if len(calls) == 1:
                        raise IOError("injected lost commit acknowledgement")
            worker = JournalWorker(lambda: UncertainCommit(path, "test"),
                                   validate_loaded=CoolingSafety._validate_saved,
                                   retry_seconds=.01)
            alarm = CoolingSafety(journal=worker)
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                lose_after_baseline(alarm)
                wait_until(lambda: alarm.snapshot()["journal_durable"])
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(set(calls)), 1)
            finally:
                self.assertTrue(alarm.close(3))
            stored = AlarmJournal(path, "test")
            try:
                self.assertEqual(len(stored.events()), 1)
            finally:
                stored.close()

    def test_history_gap_survives_normal_close_until_qualified_reconciliation_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            storage = AlarmJournal(path, "test")
            storage.begin_session()
            storage.append(saved_incident(), dict(kind="CIRCULATION_LOST"))
            storage.close()  # Simulated crash: current writer marker is dirty.

            alarm = CoolingSafety.with_journal(path, "test", wall_clock=Clock(1100.))
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                self.assertTrue(alarm.snapshot()["journal_recovery_required"])
            finally:
                self.assertTrue(alarm.close(3))
            storage = AlarmJournal(path, "test")
            try:
                clean = storage.db.execute("SELECT clean FROM cooling_writer_state WHERE name='test'").fetchone()[0]
                self.assertEqual(clean, 1)  # This writer closed normally.
            finally:
                storage.close()

            entered, release = threading.Event(), threading.Event()
            class PausedReconciliation(AlarmJournal):
                def reconcile(self, state, event):
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError("Offline reconciliation was not released")
                    AlarmJournal.reconcile(self, state, event)
            worker = JournalWorker(lambda: PausedReconciliation(path, "test"),
                                   validate_loaded=CoolingSafety._validate_saved,
                                   retry_seconds=.01)
            alarm = CoolingSafety(journal=worker, clock=Clock(), wall_clock=Clock(1100.))
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                before = alarm.snapshot()
                self.assertTrue(before["journal_recovery_required"])
                self.assertFalse(before["journal_durable"])
                self.assertRaises(ValueError, alarm.reconcile_journal,
                                  "wrong", True, "qualified operator", "reviewed old incidents", before["journal_revision"])
                self.assertRaises(ValueError, alarm.reconcile_journal,
                                  JOURNAL_RECONCILIATION_CONFIRMATION, False, "operator", "reviewed", before["journal_revision"])
                self.assertRaises(RuntimeError, alarm.reconcile_journal,
                                  JOURNAL_RECONCILIATION_CONFIRMATION, True, "operator", "reviewed", -1)
                receipt = alarm.reconcile_journal(JOURNAL_RECONCILIATION_CONFIRMATION,
                    qualified_local=True, operator="qualified operator", reason="reviewed retained incidents and history gap",
                    expected_revision=before["journal_revision"])
                self.assertEqual(receipt, 1)
                self.assertTrue(entered.wait(2))
                pending = alarm.snapshot()
                self.assertTrue(pending["journal_recovery_required"])
                self.assertTrue(pending["journal_reconciliation_pending"])
                self.assertFalse(pending["journal_durable"])
                self.assertEqual(before["circuits"], pending["circuits"])
                release.set()
                wait_until(lambda: alarm.snapshot()["journal_durable"])
                self.assertFalse(alarm.snapshot()["journal_recovery_required"])
                self.assertEqual(before["circuits"], alarm.snapshot()["circuits"])
            finally:
                release.set()
                self.assertTrue(alarm.close(3))
            alarm = CoolingSafety.with_journal(path, "test", wall_clock=Clock(1100.))
            try:
                wait_until(lambda: alarm.snapshot()["journal_ready"])
                state = alarm.snapshot()
                self.assertFalse(state["journal_recovery_required"])
                self.assertTrue(state["journal_durable"])
                audit = [event for event in state["journal"] if event["kind"] == "JOURNAL_HISTORY_RECONCILED"]
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0]["operator"], "qualified operator")
            finally:
                self.assertTrue(alarm.close(3))

    def test_policy_constructor_failure_never_starts_journal_worker(self):
        class BrokenPolicy(CoolingSafety):
            def __init__(self, **kwargs):
                raise ValueError("injected constructor failure")
        with mock.patch.object(cooling_safety, "JournalWorker") as worker:
            self.assertRaises(ValueError, BrokenPolicy.with_journal, "unused.sqlite", "test")
            self.assertFalse(worker.called)
        with mock.patch.object(cooling_safety, "JournalWorker") as worker:
            self.assertRaises(ValueError, CoolingSafety.with_journal, "unused.sqlite", "test", clock=object())
            self.assertFalse(worker.called)

    def test_sqlite_setup_failure_closes_connection_and_writer_drains(self):
        closed, threads = threading.Event(), []
        class BrokenConnection(object):
            def execute(self, *args):
                raise IOError("injected schema setup failure")
            def close(self):
                threads.append(threading.current_thread().name)
                closed.set()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(cooling_safety.sqlite3, "connect", return_value=BrokenConnection()):
                alarm = CoolingSafety.with_journal(os.path.join(directory, "alarms.sqlite"), "test")
                try:
                    wait_until(lambda: "injected schema setup failure" in alarm.snapshot()["journal_error"])
                    self.assertTrue(closed.is_set())
                    self.assertFalse(alarm.snapshot()["journal_ready"])
                    self.assertFalse(alarm.snapshot()["journal_durable"])
                finally:
                    self.assertTrue(alarm.close(3))
                self.assertTrue(alarm.journal.status()["stopped"])
        self.assertEqual(set(threads), {"ACQ-alarm-journal"})

    def test_load_failure_with_retryable_close_error_retains_same_worker(self):
        storage, close_calls = Storage(), []
        storage.fail_load = True
        def close():
            close_calls.append(threading.current_thread().name)
            if len(close_calls) == 1:
                raise IOError("injected close failure")
            storage.closed = True
        storage.close = close
        worker = JournalWorker(lambda: storage, validate_loaded=CoolingSafety._validate_saved,
                               retry_seconds=.01)
        alarm = CoolingSafety(journal=worker)
        try:
            wait_until(lambda: "injected load failure" in alarm.snapshot()["journal_error"])
            self.assertTrue(alarm.close(3))
            self.assertEqual(close_calls, ["ACQ-alarm-journal", "ACQ-alarm-journal"])
            self.assertTrue(storage.closed)
            self.assertFalse(alarm.snapshot()["journal_durable"])
        finally:
            storage.fail_load = False
            alarm.close(3)


if __name__ == "__main__":
    unittest.main()
