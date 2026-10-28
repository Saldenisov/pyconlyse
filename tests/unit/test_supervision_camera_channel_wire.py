"""Preserve observed U32 channel metadata; no NI, socket, UI or clock I/O."""

import datetime
import unittest

from legacy.xp_acq_control.elyse_agent.federation_wire import (
    MAX_VIDEO_RAW_BYTES,
    owner_frame,
    validate_owner_frame,
    validate_video_frame,
)
from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import (
    BINARY_CAMERA_HEADER_BYTES,
    MAX_BINARY_CAMERA_BYTES,
    decode_vi_camera_binary,
    validate_vi_observation,
)

from tests.unit import test_supervision_vi_telemetry as fixture


class ObservedCameraChannelTests(unittest.TestCase):
    def decode(self, raw):
        return decode_vi_camera_binary(
            raw, now_seconds=fixture.NATIVE_NOW, now_ticks=100010
        )

    def test_native_u32_channel_survives_binary_json_and_owner_validation(self):
        for channel in (0, 3, 4, 65535, 4294967295):
            raw = fixture.native_camera(channel=channel)
            self.assertEqual(BINARY_CAMERA_HEADER_BYTES, 95)
            self.assertEqual(len(raw), 95 + 6)
            value = self.decode(raw)
            self.assertEqual(value["video_frame"]["channel"], channel)
            self.assertIs(type(value["video_frame"]["channel"]), int)
            self.assertFalse(value["video_frame"]["hardware_acknowledged"])
            validate_vi_observation(value)
            frame = owner_frame(
                "supervision", "a" * 32, 1, source_mode="LABVIEW_BRIDGE",
                video_frame=value["video_frame"],
                now=datetime.datetime(2026, 10, 27, 12, tzinfo=datetime.timezone.utc),
            )
            validate_owner_frame(frame)
            self.assertEqual(frame["video_frame"]["channel"], channel)

    def test_json_rejects_negative_overflow_boolean_and_noninteger_channels(self):
        for channel in (-1, 4294967296, True, False, 1.5, "4"):
            video = fixture.image()
            video["channel"] = channel
            with self.assertRaises(ValueError):
                validate_video_frame(video)

    def test_maximum_channel_does_not_expand_header_or_packet_budget(self):
        raw = fixture.native_camera(
            channel=4294967295, rows=1, columns=MAX_VIDEO_RAW_BYTES,
            pixels=b"x" * MAX_VIDEO_RAW_BYTES,
        )
        self.assertEqual(len(raw), MAX_BINARY_CAMERA_BYTES)
        decoded = self.decode(raw)
        self.assertEqual(decoded["video_frame"]["channel"], 4294967295)
        self.assertEqual(decoded["video_frame"]["width"], MAX_VIDEO_RAW_BYTES)

    def test_geometry_and_owned_payload_limits_stay_enforced(self):
        for raw in (
            fixture.native_camera(channel=4294967295, rows=0),
            fixture.native_camera(channel=4294967295, columns=-1),
            fixture.native_camera(channel=4294967295, rows=MAX_VIDEO_RAW_BYTES + 1),
            fixture.native_camera(channel=4294967295, pixels=b"short"),
        ):
            with self.assertRaises(ValueError):
                self.decode(raw)


if __name__ == "__main__":
    unittest.main()
