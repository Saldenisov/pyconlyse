"""Synthetic clocks/readbacks only. No NI, Chroma, Tango or network calls."""
import os
import tempfile
import threading
import time
import unittest
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from legacy.xp_acq_agent.elyse_agent.cooling_safety import (
    AlarmJournal, CoolingSafety, decode_publications,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime


def publications():
    c3, c4, eps = [False] * 56, [False] * 64, [False] * 77
    for index in (1, 4, 7, 10):
        c3[index] = True
    eps[8] = True
    return {name: dict(data=values, stale=False, age_seconds=0,
                       error=dict(status=False, code=0))
            for name, values in (("C3_IN_DIO96", c3), ("C4_IN_DIO96", c4), ("EPS", eps))}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.now, self.wall = [0.0], [1700000000.0]
        self.policy = CoolingSafety(clock=lambda: self.now[0], wall_clock=lambda: self.wall[0])
        self.banks = publications()

    def observe(self, sequence=1, active=True):
        circuits, _ = decode_publications(self.banks)
        self.policy.observe(circuits, active, observation_id=sequence)

    def fault(self, circuit="SECTION"):
        self.banks["C3_IN_DIO96"]["data"][6 if circuit == "SECTION" else 0] = True
        self.observe()

    def test_documented_indications_and_each_circuit(self):
        readings, active = decode_publications(self.banks)
        self.assertTrue(active)
        self.assertFalse(readings["CANON"]["fault"])
        self.assertFalse(readings["SECTION"]["fault"])
        for name, index, circuit in (("C3_IN_DIO96", 0, "CANON"), ("C3_IN_DIO96", 6, "SECTION"),
                                     ("C4_IN_DIO96", 19, "CANON"), ("C4_IN_DIO96", 38, "SECTION")):
            with self.subTest(bank=name, index=index):
                banks = publications()
                banks[name]["data"][index] = True
                result, _ = decode_publications(banks)
                self.assertTrue(result[circuit]["fault"])
                self.assertFalse(result["SECTION" if circuit == "CANON" else "CANON"]["fault"])

    def test_cold_inactive_inputs_do_not_start_countdown(self):
        self.banks["C3_IN_DIO96"]["data"][6] = True
        self.observe(active=False)
        self.assertFalse(self.policy.snapshot()["active"])

    def test_exact_120_second_deadline_once_and_no_ack_reset(self):
        self.fault()
        first = self.policy.snapshot()["circuits"][0]["started_utc"]
        self.now[0] = 119.999
        self.observe(sequence=2)
        self.assertFalse(self.policy.tick(True))
        self.assertEqual(self.policy.snapshot()["circuits"][0]["started_utc"], first)
        self.now[0] = 120
        self.assertTrue(self.policy.tick(True))
        self.assertFalse(self.policy.tick(True))
        self.assertEqual([e["kind"] for e in self.policy.snapshot()["journal"]],
                         ["CIRCULATION_LOST", "SHUTDOWN_REQUESTED"])

    def test_second_circuit_cannot_extend_first_deadline(self):
        self.fault()
        self.now[0] = 30
        self.fault("CANON")
        self.assertEqual(self.policy.snapshot()["remaining_seconds"], 90)
        self.now[0] = 120
        self.assertTrue(self.policy.tick(True))

    def test_stale_and_driver_error_do_not_clear_or_pause_countdown(self):
        self.fault()
        self.banks = publications()
        self.banks["C3_IN_DIO96"]["stale"] = True
        self.now[0] = 119
        self.observe(sequence=2)
        self.assertTrue(self.policy.snapshot()["active"])
        self.now[0] = 120
        self.assertTrue(self.policy.tick(True))
        self.assertEqual(self.policy.snapshot()["quality"], "UNKNOWN")

    def test_recovery_needs_two_seconds_and_distinct_fresh_observation(self):
        self.fault()
        self.banks = publications()
        self.observe(sequence=2)
        self.now[0] = 2
        self.observe(sequence=2)
        self.assertTrue(self.policy.snapshot()["active"])
        self.observe(sequence=3)
        self.assertFalse(self.policy.snapshot()["active"])
        self.now[0] = 121
        self.assertFalse(self.policy.tick(True))
        self.assertEqual(self.policy.snapshot()["journal"][-1]["kind"], "CIRCULATION_RESTORED")

    def test_stale_between_healthy_samples_restarts_only_recovery_not_deadline(self):
        self.fault()
        self.banks = publications()
        self.observe(sequence=2)
        self.now[0] = 1
        self.banks["C4_IN_DIO96"]["stale"] = True
        self.observe(sequence=3)
        self.now[0] = 3
        self.banks["C4_IN_DIO96"]["stale"] = False
        self.observe(sequence=4)
        self.assertTrue(self.policy.snapshot()["active"])
        self.assertEqual(self.policy.snapshot()["remaining_seconds"], 117)

    def test_read_only_receiver_does_not_promise_or_execute_stop(self):
        self.fault()
        self.now[0] = 120
        self.assertFalse(self.policy.tick(False))
        self.assertEqual(self.policy.snapshot()["stop_state"], "UNAVAILABLE")

    def test_pending_expired_alarm_requests_stop_when_owner_becomes_available(self):
        self.fault()
        self.now[0] = 120
        self.assertFalse(self.policy.tick(False))
        self.now[0] = 125
        self.assertTrue(self.policy.tick(True))
        self.assertFalse(self.policy.tick(True))

    def test_backward_wall_clock_during_process_cannot_extend_monotonic_deadline(self):
        self.fault()
        self.wall[0] -= 3600
        self.now[0] = 120
        self.assertTrue(self.policy.tick(True))

    def test_interrupted_queued_stop_is_not_reported_completed_and_can_be_requeued(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite3")
            journal = AlarmJournal(path, "test")
            self.policy = CoolingSafety(clock=lambda: self.now[0], wall_clock=lambda: self.wall[0], journal=journal)
            self.fault()
            self.now[0] = 120
            self.wall[0] += 120
            self.assertTrue(self.policy.tick(True))
            journal.close()
            journal = AlarmJournal(path, "test")
            restored = CoolingSafety(clock=lambda: self.now[0], wall_clock=lambda: self.wall[0], journal=journal)
            self.assertEqual(restored.snapshot()["stop_state"], "INTERRUPTED")
            self.assertFalse(restored.tick(False))
            self.assertTrue(restored.tick(True))
            journal.close()

    def test_restart_restores_deadline_and_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "alarms.sqlite3")
            journal = AlarmJournal(path, "test")
            self.policy = CoolingSafety(clock=lambda: self.now[0], wall_clock=lambda: self.wall[0], journal=journal)
            self.fault()
            journal.close()
            self.wall[0] += 50
            self.now[0] = 0
            journal = AlarmJournal(path, "test")
            restored = CoolingSafety(clock=lambda: self.now[0], wall_clock=lambda: self.wall[0], journal=journal)
            self.assertEqual(restored.snapshot()["remaining_seconds"], 70)
            self.assertEqual(restored.snapshot()["journal"][0]["circuit"], "SECTION")
            self.now[0] = 70
            self.assertTrue(restored.tick(True))
            journal.close()

    def test_journal_failure_cannot_suppress_shutdown_request(self):
        class BrokenJournal:
            def load(self):
                return None
            def append(self, *args):
                raise OSError("disk full")
        self.policy = CoolingSafety(clock=lambda: self.now[0], journal=BrokenJournal())
        self.fault()
        self.assertIn("disk full", self.policy.snapshot()["journal_error"])
        self.now[0] = 120
        self.assertTrue(self.policy.tick(True))

    def test_receiver_ingress_detects_loss_without_browser_or_hardware_authority(self):
        from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore
        from legacy.xp_acq_agent.elyse_agent.telemetry_relay import sign
        key = b"cooling-unit-test-only-key-01234567890123456789"
        sink = TelemetrySinkStore(key, clock=lambda: self.now[0])
        self.banks["C3_IN_DIO96"]["data"][6] = True
        for index, name in enumerate(("C3_IN_DIO96", "C4_IN_DIO96", "EPS"), 1):
            packet = dict(session_id="test", publication=name, sequence=index,
                          producer_kind="fixture", source_seconds_1904=3870000000.0,
                          data=self.banks[name]["data"], error=dict(status=False, code=0, source=""))
            body = dict(schema_version=1, relay_id="b" * 32, message_id=index,
                        received_utc_on_xp="2026-10-21T10:00:00Z", age_seconds_on_xp=0,
                        packet=packet, hardware_writes=False)
            request = dict(body=body, nonce="a" * 32)
            request["signature"] = sign(key, "ACQ-TELEMETRY-REQUEST-1", request)
            sink.accept(request)
        self.assertTrue(sink.cooling.snapshot()["active"])
        self.assertEqual(sink.cooling.snapshot()["circuits"][0]["circuit"], "SECTION")
        self.now[0] = 120
        result = sink.snapshot()["cooling_safety"]
        self.assertEqual(result["stop_state"], "UNAVAILABLE")
        self.assertFalse(result["automatic_stop_available"])
        sink.close()


class FakeCards:
    control_profile = "extended_ht_stop"
    ht_feedback_verified = True
    focal_off = SimpleNamespace(resources_verified=True)

    def __init__(self):
        self.resource_count = 0
        self.banks = publications()
        self.calls = []
        self.fail_stop = False

    def initialize(self, cancel, startup_confirmed):
        self.resource_count = 2
    def read_snapshot(self, cancel):
        return {"banks": {"C3_DIO96_DI": {"values": self.banks["C3_IN_DIO96"]["data"]},
                          "C4_DIO96_DI": {"values": self.banks["C4_IN_DIO96"]["data"]}}}
    def general_start(self, cancel, operator_confirmed):
        self.calls.append(("start", threading.current_thread().name))
    def general_stop(self, operator_confirmed):
        self.calls.append(("stop", threading.current_thread().name))
        if self.fail_stop:
            raise RuntimeError("synthetic HT feedback error")
    def close(self):
        self.resource_count = 0


def wait_for(predicate):
    limit = time.monotonic() + 3
    while time.monotonic() < limit:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError("fake-runtime condition timed out")


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.cards = FakeCards()
        self.now = [0.0]
        self.runtime = AcquisitionRuntime(lambda: self.cards, period=.02, clock=lambda: self.now[0],
                                          cooling_polarity_verified=True)
        self.runtime.start()
        self.runtime.initialize(startup_confirmed=True)
        wait_for(lambda: self.runtime.snapshot()["state"] == "RUNNING")
        self.runtime.general_start(operator_confirmed=True)
        wait_for(lambda: self.cards.calls and self.runtime.snapshot()["state"] == "RUNNING")
        self.cards.banks["C3_IN_DIO96"]["data"][6] = True
        wait_for(lambda: self.runtime.snapshot()["cooling_safety"]["active"])

    def tearDown(self):
        self.runtime.request_shutdown(electrical_off_confirmed=True)
        self.assertTrue(self.runtime.join(3))

    def test_deadline_queues_existing_stop_on_same_owner_and_keeps_server_running(self):
        self.now[0] = 120
        self.runtime._tick_cooling()
        wait_for(lambda: self.runtime.snapshot()["cooling_safety"]["stop_state"] == "COMPLETED")
        self.assertEqual(self.cards.calls, [("start", "ACQ-card-owner"), ("stop", "ACQ-card-owner")])
        self.assertEqual(self.runtime.snapshot()["state"], "RUNNING")
        self.assertEqual(self.runtime.snapshot()["resource_count"], 2)

    def test_driver_stop_failure_retains_owner_and_reports_failure(self):
        self.cards.fail_stop = True
        self.now[0] = 120
        self.runtime._tick_cooling()
        wait_for(lambda: self.runtime.snapshot()["state"] == "FAULT")
        result = self.runtime.snapshot()
        self.assertEqual(result["resource_count"], 2)
        self.assertTrue(result["general_stop_required"])
        self.assertEqual(result["cooling_safety"]["stop_state"], "FAILED")
        self.assertIn("synthetic HT feedback error", result["cooling_safety"]["stop_error"])

    def test_unqualified_polarity_never_creates_hardware_authority(self):
        self.runtime._cooling_polarity_verified = False
        self.now[0] = 120
        self.runtime._tick_cooling()
        self.assertEqual(self.runtime.snapshot()["cooling_safety"]["stop_state"], "UNAVAILABLE")
        self.assertEqual(len(self.cards.calls), 1)


class PackageTests(unittest.TestCase):
    def test_alarm_levels_match_preserved_fluides_software_indications(self):
        from legacy.xp_acq_agent.elyse_agent.cooling_safety import CIRCUITS
        root = Path(__file__).resolve().parents[2]
        display = json.loads((root / "web/frontend/src/elyseLiveDisplayMap.json").read_text(encoding="utf-8"))
        panel = json.loads((root / "web/frontend/src/elyseFluidesPanel.json").read_text(encoding="utf-8"))
        rules = {rule["target_field"]: rule for rule in display["rules"] if rule["page"] == "fluides"}
        for circuit, fields in (("CANON", (15, 11, 14, 12)), ("SECTION", (17, 0, 18, 1))):
            for signal, field in zip(CIRCUITS[circuit], fields):
                bank, index, faulty, _label = signal
                self.assertEqual((rules[field]["bank"], rules[field]["index"]), (bank, index))
                self.assertEqual(panel["fields"][str(field)]["true_color" if faulty else "false_color"], "#FF3333")

    def test_new_candidate_contains_policy_but_never_enables_unverified_control(self):
        from tools.package_acquisition_runtime import build
        with tempfile.TemporaryDirectory() as directory:
            result = build(os.path.join(directory, "candidate"), control_profile="extended_ht_stop")
            with zipfile.ZipFile(result["archive"]) as archive:
                names = archive.namelist()
                self.assertIn("candidate/elyse_agent/cooling_safety.py", names)
                config = json.loads(archive.read("candidate/config.acquisition.json"))
                self.assertIs(config["cooling_safety"]["polarity_verified"], False)
                self.assertIs(config["ht_shutdown"]["feedback_verified"], False)
                manifest = json.loads(archive.read("candidate/manifest.json"))
                self.assertEqual(manifest["cooling_alarm_timeout_seconds"], 120)
                self.assertFalse(manifest["initialized_hardware_during_packaging"])
                self.assertFalse(any(name.endswith((".key", ".sqlite3")) for name in names))


if __name__ == "__main__":
    unittest.main()
