"""FAULT diagnostic samples stay observable without reviving control state.

Python 3.4, RAM fixtures only. No NI tasks, commands or network connections.
"""
import copy
import json
import unittest

from legacy.xp_acq_control.elyse_agent.standard_banks import (
    INPUTS, COMMANDS, SOFTWARE_STATUSES, standard_packet,
    validate_standard_packet, packet_age_seconds,
    fault_diagnostic_measurement_current,
)
from legacy.xp_acq_control.elyse_agent.telemetry_publisher import StandardTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.acquisition_control_gui import input_read_text
from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView


def diagnostic_state():
    banks = {}
    for source, kind, device, count, field, scalar in INPUTS.values():
        values = [False] * count if scalar == "Boolean" else [1.] * count
        banks[source] = dict(kind=kind, device=device, values=values)
        banks[source][field] = values
    latest = dict(source="python_daqmx_acquisition", simulated=False, banks=banks,
                  commanded_digital={}, commanded_analog_logical={},
                  stage_state=dict(software_status_valid=True, local_banks={
                      "EPS": [True] * 77, "DPS": [True] * 29}))
    for section, source, count, kind in COMMANDS.values():
        latest[section][source] = [False if kind == "Boolean" else 6.5] * count
    return dict(state="FAULT", session_id="a" * 32, sequence=3, state_revision=8,
                stale=True, error="General stop partial failure", age_seconds=.25,
                measurement_current=False, software_state_current=False, latest=latest,
                native_isolation=dict(worker_state="IDLE_OWNED", resource_count=21,
                    worker_generation="b" * 32, ownership_uncertain=False,
                    active_request_id=None),
                fault_diagnostic_measurement=dict(current=True,
                    source="settled_fault_owner_readback", command_admission=False,
                    session_id="a" * 32, sequence=3, age_seconds=.25,
                    worker_generation="b" * 32))


def records(value):
    packet = standard_packet(value, 1)
    validate_standard_packet(packet)
    return {item["publication"]: item for item in packet["data"]["banks"]}


class FaultTelemetryTests(unittest.TestCase):
    def test_cached_http_projection_ages_completed_read_consistently(self):
        value, now = diagnostic_state(), [10.]
        class Runtime(object):
            def snapshot(self):
                return copy.deepcopy(value)
        view = ApplicationView(Runtime(), clock=lambda: now[0])
        view.capture_once()
        now[0] += .125
        current = view.snapshot()
        self.assertEqual(current["age_seconds"], .375)
        self.assertEqual(current["fault_diagnostic_measurement"]["age_seconds"], .375)
        self.assertTrue(fault_diagnostic_measurement_current(current))
        self.assertIsNotNone(records(current)["C4_IN_DIO96"]["data"])
        view._active = "deinitialize"
        self.assertFalse(view.snapshot()["fault_diagnostic_measurement"]["current"])
        view._active = None
        now[0] += 2.
        self.assertFalse(view.snapshot()["fault_diagnostic_measurement"]["current"])

    def test_gui_distinguishes_fault_readback_from_fresh_control_readiness(self):
        value = diagnostic_state()
        self.assertIn("FAULT diagnostic readback | sample 3 | age 0.2s", input_read_text(value))
        value["fault_diagnostic_measurement"].update(current=False, error="read deadline exceeded")
        self.assertEqual(input_read_text(value), "NI inputs: not current | read deadline exceeded")

    def test_fresh_fault_readback_publishes_only_inputs_and_keeps_fault(self):
        value = diagnostic_state()
        before = copy.deepcopy(value)
        result = records(value)
        self.assertEqual(len(result), 27)
        self.assertEqual(set(key for key, item in result.items()
                             if item["data"] is not None), set(INPUTS))
        for key in set(COMMANDS) | set(SOFTWARE_STATUSES):
            self.assertIsNone(result[key]["data"])
            self.assertTrue(result[key]["error"]["status"])
        self.assertEqual(value, before)
        self.assertEqual(packet_age_seconds(value, standard_packet(value, 1)), .25)

    def test_pre_fault_cached_sample_without_explicit_read_evidence_is_unknown(self):
        value = diagnostic_state()
        del value["fault_diagnostic_measurement"]
        self.assertTrue(all(item["data"] is None for item in records(value).values()))

    def test_expired_or_unmatched_diagnostic_cannot_replay_inputs(self):
        mutations = (
            ("state", "IDLE"), ("telemetry_view_current", False),
            ("sequence", 4), ("age_seconds", 2.), ("age_seconds", -.1),
            ("age_seconds", float("nan")), ("session_id", "c" * 32),
        )
        for key, candidate in mutations:
            with self.subTest(key=key, candidate=candidate):
                value = diagnostic_state()
                value[key] = candidate
                self.assertFalse(fault_diagnostic_measurement_current(value))
                self.assertTrue(all(item["data"] is None for item in records(value).values()))

    def test_pending_uncertain_or_different_owner_invalidates_diagnostics(self):
        for key, candidate in (("worker_state", "EXECUTING_READ_SNAPSHOT"),
                ("ownership_uncertain", True), ("resource_count", 0),
                ("active_request_id", "pending"), ("worker_generation", "c" * 32)):
            with self.subTest(key=key):
                value = diagnostic_state()
                value["native_isolation"][key] = candidate
                self.assertFalse(fault_diagnostic_measurement_current(value))
                self.assertTrue(all(item["data"] is None for item in records(value).values()))

    def test_invalid_read_attestation_never_means_current(self):
        for key, candidate in (("current", False), ("command_admission", True),
                ("source", "execution_heartbeat"), ("sequence", True),
                ("age_seconds", .1), ("session_id", "c" * 32),
                ("worker_generation", "c" * 32)):
            with self.subTest(key=key):
                value = diagnostic_state()
                value["fault_diagnostic_measurement"][key] = candidate
                self.assertFalse(fault_diagnostic_measurement_current(value))

    def test_missing_input_stays_unknown_without_losing_other_diagnostics(self):
        value = diagnostic_state()
        del value["latest"]["banks"]["C3_DIO96_DI"]
        result = records(value)
        self.assertIsNone(result["C3_IN_DIO96"]["data"])
        self.assertIsNotNone(result["C4_IN_DIO96"]["data"])

    def test_publisher_emits_new_fault_sample_and_expiry_without_replaying_memory(self):
        value = diagnostic_state()
        class Runtime(object):
            def snapshot(self):
                return copy.deepcopy(value)
        publisher = StandardTelemetryPublisher(Runtime(), ("127.0.0.1", 8767),
            b"test-only-fault-diagnostic-telemetry-key-000000")
        packets = []
        publisher.outbox.enqueue = lambda encoded, stamp, age_seconds: packets.append(
            (json.loads(encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded), age_seconds))
        try:
            self.assertTrue(publisher.publish_once())
            self.assertFalse(publisher.publish_once())
            value["sequence"] += 1
            value["fault_diagnostic_measurement"]["sequence"] += 1
            value["latest"]["banks"]["C4_DIO96_DI"]["values"][19] = True
            self.assertTrue(publisher.publish_once())
            value["fault_diagnostic_measurement"]["current"] = False
            value["age_seconds"] = 2.
            value["fault_diagnostic_measurement"]["age_seconds"] = 2.
            self.assertTrue(publisher.publish_once())
            self.assertEqual(len(packets), 3)
            self.assertTrue(all(item["data"] is None
                for item in packets[-1][0]["data"]["banks"]))
        finally:
            publisher.close()


if __name__ == "__main__":
    unittest.main()
