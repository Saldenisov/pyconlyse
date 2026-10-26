"""Incident-specific operator confirmation; RAM clocks and local journal only."""
import copy
import os
import tempfile
import time
import unittest

from legacy.xp_acq_control.elyse_agent.cooling_safety import (
    AlarmJournal, CoolingSafety, POLICY_VERSION, RECOVERY_SECONDS, utc,
)


class Clock(object):
    def __init__(self):
        self.now = 0.
        self.wall = 1000.

    def monotonic(self):
        return self.now

    def epoch(self):
        return self.wall + self.now


def readings(red=(), quality="FRESH"):
    return dict((name, dict(fault=name in red, quality=quality,
        causes=[dict(signal="flow")] if name in red else [])) for name in ("CANON", "SECTION"))


def wait_until(predicate):
    until = time.monotonic() + 3
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("Offline journal did not settle")


def arm(policy, clock):
    policy.observe(readings(), True, 1)
    clock.now += RECOVERY_SECONDS
    policy.observe(readings(), True, 2)


def lose(policy, red=("CANON", "SECTION"), sequence=3):
    policy.observe(readings(red), True, sequence)
    return dict((entry["circuit"], entry["incident_id"])
                for entry in policy.snapshot()["confirmation_candidates"])


class CoolingConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.policy = CoolingSafety(clock=self.clock.monotonic, wall_clock=self.clock.epoch)

    def test_startup_red_never_prompts_or_counts_down_even_after_general_starts(self):
        for active in (False, None, True):
            self.policy.observe(readings(("CANON", "SECTION")), active, 1)
            self.clock.now += 121
            self.assertFalse(self.policy.tick(True))
            state = self.policy.snapshot()
            self.assertFalse(state["active"])
            self.assertFalse(state["confirmation_required"])
            self.assertFalse(state["countdown_required"])
            self.assertIsNone(state["remaining_seconds"])
        self.assertEqual(self.policy.events, [])

    def test_each_circuit_requires_distinct_fresh_green_baseline_while_general_active(self):
        self.policy.observe(readings(), False, 1)
        self.clock.now = 3.
        self.policy.observe(readings(), True, 2)
        self.policy.observe(readings(("CANON",)), True, 3)
        self.assertFalse(self.policy.snapshot()["active"])
        self.policy.observe(readings(), True, 4)
        self.clock.now += 2
        self.policy.observe(readings(), True, 4)  # Replayed sample cannot arm CANON.
        self.assertNotIn("CANON", self.policy.snapshot()["armed_circuits"])
        self.policy.observe(readings(), True, 5)
        ids = lose(self.policy, ("CANON",), 6)
        self.assertEqual(set(ids), {"CANON"})
        self.assertEqual(self.policy.snapshot()["remaining_seconds"], 120.)

    def test_transition_immediately_prompts_with_exact_incident_ids_and_120_second_deadline(self):
        arm(self.policy, self.clock)
        ids = lose(self.policy)
        state = self.policy.snapshot()
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["policy_version"], POLICY_VERSION)
        self.assertTrue(state["confirmation_required"])
        self.assertTrue(state["countdown_required"])
        self.assertEqual(len(set(ids.values())), 2)
        self.assertTrue(all(len(value) == 32 for value in ids.values()))
        self.assertTrue(all(set(entry) == {"incident_id", "circuit", "deadline_utc", "remaining_seconds"}
                            and entry["remaining_seconds"] == 120. for entry in state["confirmation_candidates"]))
        self.assertFalse(self.policy.tick(True))
        self.clock.now += 120
        self.assertTrue(self.policy.tick(True))
        self.assertFalse(self.policy.tick(True))
        self.assertEqual(self.policy.snapshot()["stop_state"], "REQUESTED")

    def test_confirmation_suppresses_only_selected_incident_and_keeps_red_alarm(self):
        arm(self.policy, self.clock)
        ids = lose(self.policy)
        deadline = self.policy.incidents["CANON"]["deadline_monotonic"]
        result = self.policy.confirm_circulation([ids["CANON"]], "authenticated_remote_operator")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertFalse(result["physical_circulation_verified"])
        self.assertFalse(result["deadline_extended"])
        self.assertEqual(self.policy.incidents["CANON"]["deadline_monotonic"], deadline)
        state = self.policy.snapshot()
        self.assertTrue(state["active"])
        self.assertTrue(state["countdown_required"])
        self.assertEqual([entry["incident_id"] for entry in state["confirmation_candidates"]], [ids["SECTION"]])
        confirmed = self.policy.incidents["CANON"]
        self.assertTrue(confirmed["confirmed"])
        self.assertEqual(confirmed["confirmed_by"], "authenticated_remote_operator")
        self.assertTrue(confirmed["confirmed_utc"])
        self.clock.now += 120
        self.assertTrue(self.policy.tick(True))  # SECTION remained unanswered.

    def test_confirmed_red_stays_visible_and_does_not_request_later_stop(self):
        arm(self.policy, self.clock)
        ids = lose(self.policy, ("CANON",))
        self.policy.confirm_circulation([ids["CANON"]], "operator")
        self.clock.now += 500
        self.policy.observe(readings(("CANON",)), True, 4)
        self.assertFalse(self.policy.tick(True))
        state = self.policy.snapshot()
        self.assertTrue(state["active"])
        self.assertFalse(state["confirmation_required"])
        self.assertFalse(state["countdown_required"])
        self.assertIsNone(state["remaining_seconds"])
        self.assertEqual(state["circuits"][0]["incident_id"], ids["CANON"])

    def test_confirmation_is_atomic_and_cannot_extend_expired_or_queued_stop(self):
        arm(self.policy, self.clock)
        ids = lose(self.policy)
        before = copy.deepcopy(self.policy.incidents)
        with self.assertRaises(RuntimeError):
            self.policy.confirm_circulation([ids["CANON"], "f" * 32], "operator")
        self.assertEqual(self.policy.incidents, before)
        self.assertFalse(any(event["kind"] == "CIRCULATION_CONFIRMED_BY_OPERATOR" for event in self.policy.events))
        for stop_state in ("REQUESTED", "FAILED", "COMPLETED", "UNAVAILABLE", "INTERRUPTED"):
            self.policy.stop_state = stop_state
            self.assertRaises(RuntimeError, self.policy.confirm_circulation, [ids["CANON"]], "operator")
        self.policy.stop_state = "NONE"
        self.clock.now += 120
        self.assertRaises(RuntimeError, self.policy.confirm_circulation, [ids["CANON"]], "operator")
        self.assertFalse(self.policy.snapshot()["confirmation_required"])

    def test_confirming_an_already_confirmed_or_malformed_selection_never_changes_state(self):
        arm(self.policy, self.clock)
        ids = lose(self.policy)
        self.policy.confirm_circulation([ids["CANON"]], "operator")
        before = copy.deepcopy(self.policy.incidents)
        self.assertRaises(RuntimeError, self.policy.confirm_circulation,
                          [ids["SECTION"], ids["CANON"]], "operator")
        for selected in ([], ids["CANON"], [ids["SECTION"]] * 2, [None], ["not-an-incident"]):
            self.assertRaises(ValueError, self.policy.confirm_circulation, selected, "operator")
        self.assertRaises(ValueError, self.policy.confirm_circulation, [ids["SECTION"]], " ")
        self.assertEqual(self.policy.incidents, before)

    def test_two_second_green_recovery_rearms_and_next_red_needs_new_confirmation(self):
        arm(self.policy, self.clock)
        first = lose(self.policy, ("CANON",))["CANON"]
        self.policy.confirm_circulation([first], "operator")
        self.policy.observe(readings(), True, 4)
        self.clock.now += 2
        self.policy.observe(readings(), True, 4)
        self.assertTrue(self.policy.snapshot()["active"])
        self.policy.observe(readings(), True, 5)
        self.assertFalse(self.policy.snapshot()["active"])
        second = lose(self.policy, ("CANON",), 6)["CANON"]
        self.assertNotEqual(first, second)
        self.assertRaises(RuntimeError, self.policy.confirm_circulation, [first], "operator")
        self.assertTrue(self.policy.snapshot()["confirmation_required"])

    def test_general_inactive_or_unknown_drops_armed_baseline(self):
        for active in (False, None):
            arm(self.policy, self.clock)
            self.policy.observe(readings(), active, 3)
            self.policy.observe(readings(("CANON", "SECTION")), True, 4)
            self.assertFalse(self.policy.snapshot()["active"])
            self.assertEqual(self.policy.snapshot()["armed_circuits"], [])

    def test_confirmation_uses_original_monotonic_deadline_despite_wall_clock_change(self):
        arm(self.policy, self.clock)
        ids = lose(self.policy, ("CANON",))
        deadline = self.policy.incidents["CANON"]["deadline_utc"]
        self.clock.wall -= 500
        self.clock.now += 120
        self.assertRaises(RuntimeError, self.policy.confirm_circulation, [ids["CANON"]], "operator")
        self.assertEqual(self.policy.incidents["CANON"]["deadline_utc"], deadline)


class CoolingConfirmationJournalTests(unittest.TestCase):
    def open(self, path, clock):
        policy = CoolingSafety.with_journal(path, "test", clock=clock.monotonic, wall_clock=clock.epoch)
        self.addCleanup(policy.close, 3)
        wait_until(lambda: policy.snapshot()["journal_write_ready"])
        return policy

    def test_confirmed_incident_survives_restart_without_arming_future_incidents(self):
        with tempfile.TemporaryDirectory() as folder:
            path, clock = os.path.join(folder, "alarms.sqlite"), Clock()
            policy = self.open(path, clock)
            arm(policy, clock)
            incident = lose(policy, ("CANON",))["CANON"]
            policy.confirm_circulation([incident], "operator")
            self.assertTrue(policy.close(3))
            policy = self.open(path, clock)
            state = policy.snapshot()
            self.assertEqual(state["armed_circuits"], [])
            self.assertTrue(state["active"])
            self.assertFalse(state["countdown_required"])
            self.assertEqual(state["circuits"][0]["confirmed_by"], "operator")
            self.assertEqual(state["circuits"][0]["incident_id"], incident)
            clock.now += 121
            policy.observe(readings(("CANON", "SECTION")), True, 9)
            self.assertFalse(policy.tick(True))
            self.assertEqual(set(policy.incidents), {"CANON"})
            self.assertTrue(policy.close(3))

    def test_old_220v_incident_becomes_durable_history_without_countdown_or_deleted_events(self):
        with tempfile.TemporaryDirectory() as folder:
            path, clock = os.path.join(folder, "alarms.sqlite"), Clock()
            old = AlarmJournal(path, "test")
            old.append(dict(incidents=dict(CANON=dict(circuit="CANON", started_utc=utc(900),
                deadline_epoch=1020., deadline_utc=utc(1020), causes=[dict(signal="220V")])),
                stop_state="REQUESTED", stop_error="prior interrupted stop"), dict(kind="CIRCULATION_LOST", circuit="CANON"))
            old.end_session(True)
            old.close()
            policy = self.open(path, clock)
            state = policy.snapshot()
            self.assertFalse(state["active"])
            self.assertFalse(state["countdown_required"])
            self.assertEqual(state["stop_state"], "NONE")
            self.assertEqual(len(state["historical_incidents"]), 1)
            self.assertEqual([event["kind"] for event in state["journal"]],
                             ["CIRCULATION_LOST", "LEGACY_220V_INCIDENT_RECLASSIFIED"])
            self.assertEqual(state["journal"][-1]["prior_stop_error"], "prior interrupted stop")
            clock.now += 500
            self.assertFalse(policy.tick(True))
            self.assertTrue(policy.close(3))
            policy = self.open(path, clock)
            self.assertEqual(len(policy.snapshot()["historical_incidents"]), 1)
            self.assertEqual(len(policy.snapshot()["journal"]), 2)
            self.assertTrue(policy.close(3))

    def test_old_non220v_incident_remains_conservative_and_cannot_be_operator_confirmed(self):
        with tempfile.TemporaryDirectory() as folder:
            path, clock = os.path.join(folder, "alarms.sqlite"), Clock()
            old = AlarmJournal(path, "test")
            old.append(dict(incidents=dict(SECTION=dict(circuit="SECTION", started_utc=utc(900),
                deadline_epoch=1020., deadline_utc=utc(1020), causes=[dict(signal="flow")])),
                stop_state="NONE", stop_error=""), dict(kind="CIRCULATION_LOST"))
            old.end_session(True)
            old.close()
            policy = self.open(path, clock)
            state = policy.snapshot()
            self.assertTrue(state["active"])
            self.assertTrue(state["countdown_required"])
            self.assertFalse(state["confirmation_required"])
            incident = state["circuits"][0]["incident_id"]
            self.assertRaises(RuntimeError, policy.confirm_circulation, [incident], "operator")
            clock.now += 20
            self.assertTrue(policy.tick(True))
            self.assertTrue(policy.close(3))

    def test_mixed_220v_and_flow_or_unknown_causes_never_reclassify(self):
        for causes in ([dict(signal="220V"), dict(signal="flow")],
                       [dict(signal="220V"), dict(signal="pressure")], []):
            with tempfile.TemporaryDirectory() as folder:
                path, clock = os.path.join(folder, "alarms.sqlite"), Clock()
                old = AlarmJournal(path, "test")
                old.append(dict(incidents=dict(CANON=dict(circuit="CANON", started_utc=utc(900),
                    deadline_epoch=1020., deadline_utc=utc(1020), causes=causes)),
                    stop_state="NONE", stop_error=""), dict(kind="CIRCULATION_LOST"))
                old.end_session(True)
                old.close()
                policy = self.open(path, clock)
                state = policy.snapshot()
                self.assertTrue(state["countdown_required"])
                self.assertEqual(state["historical_incidents"], [])
                self.assertFalse(state["confirmation_required"])
                self.assertTrue(policy.close(3))


if __name__ == "__main__":
    unittest.main()
