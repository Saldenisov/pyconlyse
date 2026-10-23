"""Python 3.4-compatible native status projection; no driver/network imports.

EPS/DPS are complete software-local images. A command-progress update can
publish those images, but cannot refresh an old AI/DI sample by implication.
"""
import copy
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.standard_banks import (
    BANKS, INPUTS, COMMANDS, SOFTWARE_STATUSES, SOFTWARE_STATUS_SOURCE,
    UNAVAILABLE, standard_packet, validate_standard_packet,
    packet_age_seconds,
)
from legacy.xp_acq_control.elyse_agent.errors import CommandError


def sample_runtime():
    banks = {}
    latest = dict(source="python_daqmx_acquisition", simulated=False, banks=banks,
                  commanded_digital={}, commanded_analog_logical={})
    for unused, item in INPUTS.items():
        source, kind, device, count, field, scalar = item
        banks[source] = dict(kind=kind, device=device)
        banks[source][field] = [False if scalar == "Boolean" else 123.] * count
    for unused, item in COMMANDS.items():
        section, source, count, kind = item
        latest[section][source] = [False if kind == "Boolean" else 6.5] * count
    return dict(session_id="a" * 32, sequence=1, state_revision=2, state="RUNNING",
                stale=False, age_seconds=.3, error="", latest=latest)


def attach_software(runtime, age=.1):
    runtime.update(software_state_current=True, software_state_age_seconds=age,
                   software_state_sequence=4)
    runtime["software_state"] = dict(source=SOFTWARE_STATUS_SOURCE, simulated=False,
        session_id=runtime["session_id"], sequence=4, source_revision=8,
        local_banks={"EPS": [False] * 77, "DPS": [False] * 29},
        hardware_acknowledged=False, psp_delivery_acknowledged=False)
    runtime["software_state"]["local_banks"]["EPS"][8] = True
    runtime["software_state"]["local_banks"]["DPS"][2] = True
    return runtime


def records(runtime):
    packet = standard_packet(runtime, 1)
    validate_standard_packet(packet)
    return dict((item["publication"], item) for item in packet["data"]["banks"])


class StatusProjectionTests(unittest.TestCase):
    def assert_unavailable(self, record):
        self.assertIsNone(record["data"])
        self.assertIs(record["error"]["status"], True)
        self.assertEqual(record["error"]["code"], UNAVAILABLE)
        self.assertTrue(record["error"]["source"])

    def test_complete_software_images_add_two_valid_banks_not_physical_feedback(self):
        runtime = attach_software(sample_runtime())
        actual = records(runtime)
        self.assertEqual(tuple(item["publication"] for item in
                               standard_packet(runtime, 1)["data"]["banks"]), BANKS)
        self.assertEqual(sum(item["error"]["status"] is False for item in actual.values()), 14)
        self.assertEqual(actual["EPS"]["data"], runtime["software_state"]["local_banks"]["EPS"])
        self.assertEqual(actual["DPS"]["data"], runtime["software_state"]["local_banks"]["DPS"])
        self.assertIs(runtime["software_state"]["hardware_acknowledged"], False)
        self.assertIs(runtime["software_state"]["psp_delivery_acknowledged"], False)

    def test_legacy_fixture_without_known_memory_stays_twelve_valid_banks(self):
        actual = records(sample_runtime())
        self.assertEqual(sum(item["error"]["status"] is False for item in actual.values()), 12)
        self.assert_unavailable(actual["EPS"])
        self.assert_unavailable(actual["DPS"])

    def test_fresh_owner_snapshot_can_carry_compatibility_image(self):
        runtime = sample_runtime()
        runtime["latest"]["stage_state"] = dict(software_status_valid=True,
            local_banks={"EPS": [True] * 77, "DPS": [False] * 29})
        actual = records(runtime)
        self.assertEqual(actual["EPS"]["data"], [True] * 77)
        self.assertEqual(actual["DPS"]["data"], [False] * 29)
        runtime["age_seconds"] = 2
        actual = records(runtime)
        self.assert_unavailable(actual["EPS"])
        self.assert_unavailable(actual["DPS"])

    def test_execution_real_measurements_remain_valid_with_same_freshness_rules(self):
        runtime = attach_software(sample_runtime())
        runtime.update(state="EXECUTING", measurement_current=True)
        actual = records(runtime)
        self.assertEqual(actual["C1NI6071E"]["data"], [123.] * 64)
        self.assertEqual(actual["C9NI6703"]["data"], [6.5] * 10)
        self.assertEqual(actual["EPS"]["data"][8], True)

    def test_execution_without_current_measurement_attestation_cannot_reuse_ai(self):
        for current in (None, False, 1, "true"):
            runtime = attach_software(sample_runtime())
            runtime.update(state="EXECUTING", measurement_current=current)
            actual = records(runtime)
            self.assert_unavailable(actual["C1NI6071E"])
            self.assertEqual(actual["EPS"]["data"][8], True)
        runtime = attach_software(sample_runtime())
        runtime["measurement_current"] = False
        self.assert_unavailable(records(runtime)["C1NI6071E"])

    def test_progress_memory_does_not_revive_expired_measurements(self):
        runtime = attach_software(sample_runtime())
        runtime.update(state="EXECUTING", age_seconds=29., stale=True)
        actual = records(runtime)
        self.assert_unavailable(actual["C1NI6071E"])
        self.assert_unavailable(actual["C4_IN_DIO96"])
        self.assert_unavailable(actual["C9NI6703"])
        self.assertEqual(actual["EPS"]["data"][8], True)
        self.assertEqual(actual["DPS"]["data"][2], True)
        self.assertEqual(runtime["age_seconds"], 29.)

    def test_persistent_literals_do_not_need_recent_hardware_sampling(self):
        runtime = attach_software(sample_runtime(), age=120.)
        runtime.update(age_seconds=120., stale=True)
        actual = records(runtime)
        self.assertEqual(actual["EPS"]["data"][8], True)
        self.assert_unavailable(actual["C1NI6071E"])

    def test_wire_age_is_oldest_populated_category_never_progress_time(self):
        runtime = attach_software(sample_runtime(), age=.1)
        runtime["age_seconds"] = .8
        self.assertEqual(packet_age_seconds(runtime, standard_packet(runtime, 1)), .8)
        runtime["software_state_age_seconds"] = 1.2
        self.assertEqual(packet_age_seconds(runtime, standard_packet(runtime, 1)), 1.2)
        runtime.update(age_seconds=29., state="EXECUTING", stale=True)
        runtime["software_state_age_seconds"] = .2
        self.assertEqual(packet_age_seconds(runtime, standard_packet(runtime, 1)), .2)
        self.assertEqual(runtime["age_seconds"], 29.)
        runtime.update(software_state_current=False)
        self.assertEqual(packet_age_seconds(runtime, standard_packet(runtime, 1)), 0.)

    def test_compatibility_status_uses_measurement_age_and_invalid_age_is_rejected(self):
        runtime = sample_runtime()
        runtime["latest"]["stage_state"] = dict(software_status_valid=True,
            local_banks={"EPS": [False] * 77, "DPS": [False] * 29})
        packet = standard_packet(runtime, 1)
        self.assertEqual(packet_age_seconds(runtime, packet), .3)
        runtime["age_seconds"] = float("nan")
        self.assertRaises(ValueError, packet_age_seconds, runtime, packet)
        runtime = attach_software(sample_runtime())
        packet = standard_packet(runtime, 1)
        runtime["software_state_age_seconds"] = True
        self.assertRaises(ValueError, packet_age_seconds, runtime, packet)

    def test_missing_wrong_type_and_partial_status_banks_are_not_synthetic_false(self):
        for name, (count, unused) in SOFTWARE_STATUSES.items():
            for candidate in (None, [False] * (count - 1), [False] * (count + 1),
                              [0] * count, [1] * count, [None] * count,
                              {0: False}):
                runtime = attach_software(sample_runtime())
                runtime["software_state"]["local_banks"][name] = candidate
                self.assert_unavailable(records(runtime)[name])
            runtime = attach_software(sample_runtime())
            del runtime["software_state"]["local_banks"][name]
            self.assert_unavailable(records(runtime)[name])

    def test_complete_native_tuple_vectors_normalize_to_strict_wire_lists(self):
        runtime = attach_software(sample_runtime())
        for section in ("commanded_digital", "commanded_analog_logical"):
            for name, values in runtime["latest"][section].items():
                runtime["latest"][section][name] = tuple(values)
        for name, values in runtime["software_state"]["local_banks"].items():
            runtime["software_state"]["local_banks"][name] = tuple(values)
        actual = records(runtime)
        self.assertEqual(sum(item["error"]["status"] is False for item in actual.values()), 14)
        for name in set(COMMANDS) | set(SOFTWARE_STATUSES):
            self.assertIs(type(actual[name]["data"]), list)
        packet = standard_packet(runtime, 1)
        packet["data"]["banks"][15]["data"] = tuple(packet["data"]["banks"][15]["data"])
        self.assertRaises((ValueError, CommandError), validate_standard_packet, packet)

    def test_actual_card_backend_fake_snapshot_projects_without_json_roundtrip(self):
        # Task objects are pure Python fakes. This exercises real CardBackend
        # snapshot shapes without NI imports, card initialization or IPC JSON.
        from tests.unit.test_acq_unaveraged_inputs import fake_backend
        backend, unused_owner, unused_events = fake_backend()
        # This fixture has manually injected owned tasks/startup images rather
        # than calling initialize. Attest the reviewed root-reset completion in
        # this fake only; production sets this solely after successful startup.
        backend._software_state_valid = True
        backend.commanded_digital = dict((name, tuple(values)) for name, values in backend.commanded_digital.items())
        backend.commanded_analog = dict((name, tuple(values)) for name, values in backend.commanded_analog.items())
        runtime = sample_runtime()
        runtime["latest"] = backend.read_snapshot(threading.Event())
        # The backend must expose validity separately from the literal image.
        self.assertIs(runtime["latest"]["stage_state"]["software_status_valid"], True)
        self.assertIs(type(runtime["latest"]["stage_state"]["local_banks"]["EPS"]), tuple)
        actual = records(runtime)
        self.assertEqual(sum(item["error"]["status"] is False for item in actual.values()), 14)
        self.assertEqual(len([item for item in actual.values() if item["data"] is None]), 13)
        for name in set(INPUTS) | set(COMMANDS) | set(SOFTWARE_STATUSES):
            self.assertIs(type(actual[name]["data"]), list)

    def test_cold_or_partial_reset_image_is_not_published_as_false_status(self):
        for valid in (None, False, 1):
            runtime = sample_runtime()
            runtime["latest"]["stage_state"] = dict(software_status_valid=valid,
                local_banks={"EPS": [False] * 77, "DPS": [False] * 29})
            actual = records(runtime)
            self.assert_unavailable(actual["EPS"])
            self.assert_unavailable(actual["DPS"])

    def test_untrusted_stale_cancelled_fault_or_other_lifetime_never_falls_back(self):
        changes = (dict(state="IDLE"), dict(state="INITIALIZING"),
                   dict(state="DEINITIALIZING"), dict(state="FAULT"),
                   dict(state="RECOVERY_REQUIRED"), dict(error="native fault"),
                   dict(software_state_current=False),
                   dict(software_state_age_seconds=None),
                   dict(software_state_age_seconds=-1),
                   dict(software_state_age_seconds=float("inf")),
                   dict(software_state_age_seconds=True),
                   dict(telemetry_view_current=False), dict(software_state_sequence=5))
        for change in changes:
            runtime = attach_software(sample_runtime())
            runtime["latest"]["stage_state"] = copy.deepcopy(runtime["software_state"])
            runtime.update(change)
            actual = records(runtime)
            self.assert_unavailable(actual["EPS"])
            self.assert_unavailable(actual["DPS"])
        for field, value in (("source", "copied_acquisition"), ("source", None),
                             ("session_id", "b" * 32), ("simulated", True),
                             ("sequence", True), ("sequence", -1),
                             ("source_revision", -1), ("source_revision", True),
                             ("hardware_acknowledged", True),
                             ("psp_delivery_acknowledged", True)):
            runtime = attach_software(sample_runtime())
            runtime["software_state"][field] = value
            actual = records(runtime)
            self.assert_unavailable(actual["EPS"])
            self.assert_unavailable(actual["DPS"])

    def test_projection_isolated_from_owner_and_packet_mutation(self):
        runtime = attach_software(sample_runtime())
        before = copy.deepcopy(runtime)
        actual = records(runtime)
        descriptor_name = actual["DPS"]["lv_type"]["name"]
        actual["EPS"]["data"][0] = True
        actual["DPS"]["lv_type"]["name"] = "changed"
        self.assertEqual(runtime, before)
        again = records(runtime)
        self.assertIs(again["EPS"]["data"][0], False)
        self.assertEqual(again["DPS"]["lv_type"]["name"], descriptor_name)

    def test_wire_validator_rejects_wrong_boolean_status_error_or_shape(self):
        for name in SOFTWARE_STATUSES:
            original = standard_packet(attach_software(sample_runtime()), 1)
            for field, value in (("data", [False]), ("data", [0] * SOFTWARE_STATUSES[name][0]),
                                 ("error", dict(status=True, code=UNAVAILABLE, source="unknown"))):
                packet = copy.deepcopy(original)
                record = next(item for item in packet["data"]["banks"] if item["publication"] == name)
                record[field] = value
                self.assertRaises(ValueError, validate_standard_packet, packet)
        packet = standard_packet(attach_software(sample_runtime()), 1)
        packet["producer_kind"] = "copied_acquisition"
        self.assertRaises(ValueError, validate_standard_packet, packet)


if __name__ == "__main__":
    unittest.main()
