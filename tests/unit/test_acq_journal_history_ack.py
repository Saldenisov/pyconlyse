"""Local history review is durable, non-destructive and not an I/O bypass.

Driver/network-free Python 3.4 stdlib tests.
"""
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent import cooling_safety
from legacy.xp_acq_control.elyse_agent.cooling_safety import AlarmJournal, CoolingSafety, utc
from legacy.xp_acq_control.elyse_agent.journal_worker import JournalWorker


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("Offline journal acknowledgment condition not reached")


def dirty_history(path, state=None):
    journal = AlarmJournal(path, "test")
    try:
        journal.begin_session()
        if state is not None:
            journal.append(state, dict(kind="CIRCULATION_LOST", journal_event_id="old-incident"))
    finally:
        # Deliberately omit end_session: fixture for a prior unclean session.
        journal.close()


def open_alarm(path, storage_class=AlarmJournal):
    worker = JournalWorker(lambda: storage_class(path, "test"),
        validate_loaded=CoolingSafety._validate_saved, retry_seconds=.01)
    return CoolingSafety(journal=worker, clock=lambda: 20., wall_clock=lambda: 1100.)


def acknowledge(alarm, state=None):
    state = state or alarm.snapshot()
    return alarm.acknowledge_journal_history(qualified_local=True,
        operator="local operator", reason="Historical uncertainty reviewed; missing events not reconstructed",
        expected_revision=state["journal_revision"])


class JournalHistoryAcknowledgmentTests(unittest.TestCase):
    def test_cold_attach_retains_same_policy_and_starts_only_one_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            dirty_history(path)
            alarm = CoolingSafety(clock=lambda: 20., wall_clock=lambda: 1100.)
            self.assertIsNone(alarm.journal)
            self.assertIs(alarm.attach_owned_journal(path, "test"), alarm)
            try:
                wait_until(lambda: alarm.snapshot()["journal_write_ready"])
                self.assertTrue(alarm.snapshot()["journal_history_warning"])
                original_worker = alarm.journal
                with mock.patch.object(cooling_safety, "JournalWorker") as factory:
                    self.assertRaises(RuntimeError, alarm.attach_owned_journal, path, "test")
                    self.assertFalse(factory.called)
                self.assertIs(alarm.journal, original_worker)
            finally:
                self.assertTrue(alarm.close(3))

    def test_late_attach_refuses_even_unknown_observations_and_stop_changes(self):
        def observe_unknown(alarm):
            alarm.observe(dict(SECTION=dict(fault=None, quality="UNKNOWN", causes=[])), None)
            self.assertEqual(alarm.incidents, {})
            self.assertEqual(alarm.events, [])
            self.assertIsNone(alarm.machine_active)
            self.assertEqual(alarm.quality, "UNKNOWN")

        for change in (observe_unknown, lambda alarm: alarm.stop_result("stop failed"),
                       lambda alarm: alarm.tick(True)):
            alarm = CoolingSafety()
            change(alarm)
            with mock.patch.object(cooling_safety, "JournalWorker") as factory:
                self.assertRaises(RuntimeError, alarm.attach_owned_journal, "unused.sqlite", "test")
                self.assertFalse(factory.called)
            self.assertIsNone(alarm.journal)

    def test_with_journal_reuses_cold_attach_composition(self):
        with mock.patch.object(CoolingSafety, "attach_owned_journal", autospec=True,
                               return_value="attached-policy") as attach:
            self.assertEqual(CoolingSafety.with_journal("unused.sqlite", "test", journal_capacity=7),
                             "attached-policy")
        args, kwargs = attach.call_args
        self.assertIsInstance(args[0], CoolingSafety)
        self.assertIsNone(args[0].journal)
        self.assertEqual(args[1:], ("unused.sqlite", "test"))
        self.assertEqual(kwargs, dict(capacity=7))

    def test_new_journal_does_not_claim_acknowledgment(self):
        with tempfile.TemporaryDirectory() as directory:
            alarm = open_alarm(os.path.join(directory, "alarms.sqlite"))
            try:
                wait_until(lambda: alarm.snapshot()["journal_write_ready"])
                state = alarm.snapshot()
                self.assertEqual(state["journal_history_warning"], "")
                self.assertFalse(state["journal_history_acknowledge_available"])
                self.assertFalse(state["journal_history_acknowledged"])
                self.assertIsNone(state["journal_history_acknowledgment"])
                self.assertRaises(RuntimeError, acknowledge, alarm)
            finally:
                self.assertTrue(alarm.close(3))

    def test_commit_ack_retains_incident_and_survives_clean_restart_but_not_new_crash(self):
        entered, release = threading.Event(), threading.Event()

        class PausedCommit(AlarmJournal):
            def reconcile(self, state, event):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Offline paused acknowledgment not released")
                AlarmJournal.reconcile(self, state, event)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            incident = dict(circuit="SECTION", started_utc=utc(1000.),
                deadline_epoch=1120., deadline_utc=utc(1120.), causes=[])
            dirty_history(path, dict(incidents=dict(SECTION=incident), stop_state="NONE", stop_error=""))
            alarm = open_alarm(path, PausedCommit)
            try:
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledge_available"])
                before = alarm.snapshot()
                self.assertTrue(before["active"])
                self.assertEqual(before["remaining_seconds"], 20.)
                receipt = acknowledge(alarm, before)
                self.assertEqual(receipt, 1)
                self.assertTrue(entered.wait(2))
                pending = alarm.snapshot()
                self.assertTrue(pending["journal_history_warning"])
                self.assertFalse(pending["journal_history_acknowledge_available"])
                self.assertTrue(pending["journal_history_acknowledgment_pending"])
                self.assertFalse(pending["journal_history_acknowledged"])
                self.assertIsNone(pending["journal_history_acknowledgment"])
                self.assertEqual(pending["circuits"], before["circuits"])
                release.set()
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledged"])
                after = alarm.snapshot()
                self.assertEqual(after["journal_history_warning"], "")
                self.assertFalse(after["journal_history_acknowledgment_pending"])
                self.assertEqual(after["circuits"], before["circuits"])
                self.assertEqual(after["stop_state"], before["stop_state"])
                self.assertTrue(after["journal_history_acknowledgment"]["event_id"])
                self.assertFalse(after["journal_history_acknowledgment"]["missing_events_reconstructed"])
            finally:
                release.set()
                self.assertTrue(alarm.close(3))

            alarm = open_alarm(path)
            try:
                wait_until(lambda: alarm.snapshot()["journal_write_ready"])
                state = alarm.snapshot()
                self.assertTrue(state["journal_history_acknowledged"])
                self.assertEqual(state["journal_history_acknowledgment"],
                                 after["journal_history_acknowledgment"])
                self.assertEqual(state["circuits"], before["circuits"])
                audit = [row for row in state["journal"] if row["kind"] == "JOURNAL_HISTORY_RECONCILED"]
                self.assertEqual(len(audit), 1)
                self.assertFalse(audit[0]["missing_events_reconstructed"])
                self.assertTrue(audit[0]["prior_history_warning"])
                self.assertEqual(audit[0]["operator"], "local operator")
                self.assertEqual([row["kind"] for row in state["journal"]].count("CIRCULATION_LOST"), 1)
            finally:
                self.assertTrue(alarm.close(3))

            dirty_history(path)
            alarm = open_alarm(path)
            try:
                wait_until(lambda: alarm.snapshot()["journal_write_ready"])
                state = alarm.snapshot()
                self.assertTrue(state["journal_history_warning"])
                self.assertTrue(state["journal_history_acknowledge_available"])
                self.assertFalse(state["journal_history_acknowledged"])
                self.assertIsNone(state["journal_history_acknowledgment"])
                self.assertEqual(state["circuits"], before["circuits"])
                self.assertEqual(len([row for row in state["journal"]
                    if row["kind"] == "JOURNAL_HISTORY_RECONCILED"]), 1)
            finally:
                self.assertTrue(alarm.close(3))

    def test_failed_ack_commit_keeps_warning_and_current_failure_until_success(self):
        fail = threading.Event()
        fail.set()

        class FailedCommit(AlarmJournal):
            def reconcile(self, state, event):
                if fail.is_set():
                    raise IOError("injected acknowledgment commit failure")
                AlarmJournal.reconcile(self, state, event)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            dirty_history(path)
            alarm = open_alarm(path, FailedCommit)
            try:
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledge_available"])
                acknowledge(alarm)
                wait_until(lambda: "acknowledgment commit failure" in alarm.snapshot()["journal_storage_error"])
                state = alarm.snapshot()
                self.assertTrue(state["journal_history_warning"])
                self.assertTrue(state["journal_history_acknowledgment_pending"])
                self.assertFalse(state["journal_history_acknowledged"])
                self.assertEqual(state["journal_committed"], 0)
                self.assertFalse(state["journal_write_ready"])
                self.assertRaises(RuntimeError, acknowledge, alarm)
                fail.clear()
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledged"])
                self.assertEqual(alarm.snapshot()["journal_storage_error"], "")
                self.assertEqual(alarm.snapshot()["journal_committed"], 1)
            finally:
                fail.clear()
                self.assertTrue(alarm.close(3))

    def test_current_append_failure_cannot_be_acknowledged_as_old_history(self):
        fail = threading.Event()
        fail.set()

        class FailedAppend(AlarmJournal):
            def append(self, state, event):
                if fail.is_set():
                    raise IOError("injected current journal failure")
                AlarmJournal.append(self, state, event)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            dirty_history(path)
            alarm = open_alarm(path, FailedAppend)
            try:
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledge_available"])
                alarm.stop_result("retained current stop failure")
                wait_until(lambda: "current journal failure" in alarm.snapshot()["journal_storage_error"])
                state = alarm.snapshot()
                self.assertFalse(state["journal_history_acknowledge_available"])
                self.assertRaises(RuntimeError, acknowledge, alarm)
                self.assertEqual(alarm.snapshot()["stop_error"], "retained current stop failure")
                fail.clear()
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledge_available"])
                acknowledge(alarm)
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledged"])
                self.assertEqual(alarm.snapshot()["stop_error"], "retained current stop failure")
            finally:
                fail.clear()
                self.assertTrue(alarm.close(3))

    def test_local_review_and_current_revision_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            dirty_history(path)
            alarm = open_alarm(path)
            try:
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledge_available"])
                state = alarm.snapshot()
                self.assertRaises(ValueError, alarm.acknowledge_journal_history,
                    operator="operator", reason="reviewed", expected_revision=state["journal_revision"])
                self.assertRaises(ValueError, alarm.acknowledge_journal_history,
                    qualified_local=True, operator="", reason="reviewed",
                    expected_revision=state["journal_revision"])
                self.assertRaises(RuntimeError, alarm.acknowledge_journal_history,
                    qualified_local=True, operator="operator", reason="reviewed",
                    expected_revision=state["journal_revision"] - 1)
                self.assertTrue(alarm.snapshot()["journal_history_warning"])
                self.assertEqual(alarm.snapshot()["journal_submitted"], 0)
            finally:
                self.assertTrue(alarm.close(3))

    def test_lost_ack_after_commit_retries_single_durable_audit(self):
        calls = []

        class LostCommitAck(AlarmJournal):
            def reconcile(self, state, event):
                calls.append(event["journal_event_id"])
                AlarmJournal.reconcile(self, state, event)
                if len(calls) == 1:
                    raise IOError("injected lost history acknowledgment")

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite")
            dirty_history(path)
            alarm = open_alarm(path, LostCommitAck)
            try:
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledge_available"])
                acknowledge(alarm)
                wait_until(lambda: alarm.snapshot()["journal_history_acknowledged"])
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(set(calls)), 1)
            finally:
                self.assertTrue(alarm.close(3))
            journal = AlarmJournal(path, "test")
            try:
                audit = [row for row in journal.events() if row["kind"] == "JOURNAL_HISTORY_RECONCILED"]
                self.assertEqual(len(audit), 1)
                self.assertEqual(journal.history_acknowledgment()["event_id"], calls[0])
            finally:
                journal.close()


if __name__ == "__main__":
    unittest.main()
