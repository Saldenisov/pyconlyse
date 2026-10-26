"""Actual XP Python 3.4 codec tests: no DeviceServers/Tango/network imports."""
import copy
import json
import unittest
import base64

from legacy.xp_acq_control.elyse_agent.federation_wire import (
    owner_frame, validate_owner_frame, expand_owner_frame, OWNED_BANKS,
)
from legacy.xp_acq_control.elyse_agent.standard_banks import schemas


def record(name, value):
    return dict(publication=name, data=value, lv_type=copy.deepcopy(schemas()[name]),
                error=dict(status=False, code=0, source=""), source_age_seconds=.1)


class FederationWireTests(unittest.TestCase):
    def test_native_machine_subset_roundtrips_without_driver_imports(self):
        value = owner_frame("acquisition", "a" * 32, 1,
            {"C1NI6071E": record("C1NI6071E", [20.] * 64)}, "PYTHON_NATIVE")
        encoded = validate_owner_frame(value)
        self.assertEqual(json.loads(encoded.decode("ascii")), value)
        self.assertEqual(set(expand_owner_frame(value)), set(OWNED_BANKS["acquisition"]))

    def test_missing_banks_remain_explicitly_unavailable(self):
        value = owner_frame("acquisition", "a" * 32, 1)
        self.assertTrue(all(item["data"] is None and item["error"]["status"] for item in value["banks"]))
        self.assertIsNone(value["counter_part"])

    def test_foreign_bank_and_untyped_records_are_rejected(self):
        self.assertRaises(ValueError, owner_frame, "acquisition", "a" * 32, 1,
                          {"C12NI1409": record("C12NI1409", "img0")}, "LABVIEW_BRIDGE")
        for records in ([], False, ""):
            self.assertRaises(ValueError, owner_frame, "acquisition", "a" * 32, 1, records)

    def test_camera_is_bounded_opaque_string_not_a_pixel_array(self):
        value = owner_frame("supervision", "b" * 32, 1,
            {"C12NI1409": record("C12NI1409", "img0")}, "PYTHON_NATIVE")
        self.assertEqual(expand_owner_frame(value)["C12NI1409"]["data"], "img0")
        for camera in ([0, 1], "x" * 4097):
            self.assertRaises(ValueError, owner_frame, "supervision", "b" * 32, 1,
                              {"C12NI1409": record("C12NI1409", camera)}, "PYTHON_NATIVE")

    def test_counter_part_is_explicit_16_values_plus_selector_semantics(self):
        part = dict(values=[1.] * 16, source_age_seconds=.1,
            source="last_successful_counter_command_memory", selector=-1., pending_selector=False)
        value = owner_frame("supervision", "b" * 32, 1, source_mode="PYTHON_NATIVE", counter_part=part)
        self.assertEqual(value["counter_part"], part)
        for field, wrong in (("selector", 0), ("pending_selector", 0), ("source_age_seconds", float("inf"))):
            changed = copy.deepcopy(part)
            changed[field] = wrong
            self.assertRaises(ValueError, owner_frame, "supervision", "b" * 32, 2,
                              source_mode="PYTHON_NATIVE", counter_part=changed)

    def test_unavailable_source_cannot_claim_valid_payload(self):
        self.assertRaises(ValueError, owner_frame, "supervision", "b" * 32, 1,
                          {"C12NI1409": record("C12NI1409", "img0")})

    def test_raw_u8_camera_frame_codec_is_separate_from_string_bank(self):
        from legacy.xp_acq_control.elyse_agent.federation_wire import validate_video_frame
        frame = dict(source="python_supervision_ni1409", simulated=False, sequence=1,
            sequence_interpretation="software grab observation, not hardware frame counter",
            capture_session_id="c" * 32, observed_utc="2026-10-26T12:00:00+00:00",
            sample_elapsed_seconds=.1, width=2, height=2, pixel_type="U8",
            encoding="base64_raw_row_major", data=base64.b64encode(b"abcd").decode("ascii"),
            channel=2, processing="raw_grab_before_legacy_interlace_bcg_profiles",
            hardware_acknowledged=False, source_age_seconds=.1)
        validate_video_frame(frame)
        value = owner_frame("supervision", "b" * 32, 1, source_mode="PYTHON_NATIVE", video_frame=frame)
        self.assertEqual(json.loads(validate_owner_frame(value).decode("ascii"))["video_frame"], frame)
        self.assertIsNone(value["banks"][0]["data"])
        frame["width"] = 3
        self.assertRaises(ValueError, validate_video_frame, frame)


if __name__ == "__main__":
    unittest.main()
