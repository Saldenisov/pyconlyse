"""Bounded raw NI1409 payload projection; no camera, image editor or network."""
import base64
import copy
import json
import unittest

from legacy.xp_acq_control.elyse_agent.federation_wire import owner_frame, validate_video_frame
from DeviceServers.control.elyse_acq.federated_telemetry import FederatedTelemetryStore
from tests.unit.test_acq_federated_telemetry import KEYS, body, request, record, part


def video(sequence=1, capture="9" * 32, age=0.):
    return dict(source="python_supervision_ni1409", simulated=False, sequence=sequence,
        sequence_interpretation="software grab observation, not hardware frame counter",
        capture_session_id=capture, observed_utc="2026-10-26T12:00:00.000001+00:00",
        sample_elapsed_seconds=.01, width=2, height=2, pixel_type="U8",
        encoding="base64_raw_row_major", data=base64.b64encode(b"\x00\x01\x02\x03").decode("ascii"),
        channel=2, processing="raw_grab_before_legacy_interlace_bcg_profiles",
        hardware_acknowledged=False, source_age_seconds=age)


def source(sequence=1, image=None, session="b" * 32):
    return owner_frame("supervision", session, sequence,
        {"C12NI1409": record("C12NI1409", "img0")}, "PYTHON_NATIVE",
        counter_part=part(), video_frame=image)


class FederatedVideoTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.store = FederatedTelemetryStore(KEYS, clock=lambda: self.now)

    def tearDown(self):
        self.store.close()

    def test_raw_frame_has_independent_attribute_and_no_payload_in_27_bank_view(self):
        self.store.accept(request(body(source(image=video()))))
        result = self.store.video_snapshot()
        self.assertTrue(result["available"])
        self.assertEqual(base64.b64decode(result["frame"]["data"]), b"\x00\x01\x02\x03")
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot["publications"]["C12NI1409"]["data"], "img0")
        self.assertNotIn("data", snapshot["video_metadata"])
        self.assertNotIn("frame", snapshot["video_metadata"])
        self.assertEqual(len(snapshot["publications"]), 27)

    def test_status_heartbeat_cannot_freshen_same_capture_even_with_zero_claimed_age(self):
        self.store.accept(request(body(source(image=video()))))
        self.now = 1.
        self.store.accept(request(body(source(sequence=2, image=video()), message=2)))
        self.assertEqual(self.store.video_snapshot()["age_seconds"], 1.)
        self.now = 2.01
        self.store.accept(request(body(source(sequence=3), message=3)))
        result = self.store.video_snapshot()
        self.assertTrue(result["stale"])
        self.assertIsNone(result["frame"])
        self.assertTrue(self.store.snapshot()["owners"]["supervision"]["source_current"])

    def test_same_capture_identity_cannot_change_bytes_or_metadata(self):
        self.store.accept(request(body(source(image=video()))))
        changed = video()
        changed["data"] = base64.b64encode(b"\x04\x03\x02\x01").decode("ascii")
        self.assertRaises(ValueError, self.store.accept, request(body(source(sequence=2, image=changed), message=2)))
        self.assertEqual(self.store.snapshot()["received_this_process"], 1)

    def test_camera_restart_uses_new_capture_session_and_rejects_retired_capture(self):
        self.store.accept(request(body(source(image=video(sequence=7)))))
        self.store.accept(request(body(source(sequence=2, image=video(capture="8" * 32)), message=2)))
        self.assertEqual(self.store.video_snapshot()["capture_session_id"], "8" * 32)
        self.assertRaises(ValueError, self.store.accept,
            request(body(source(sequence=3, image=video(sequence=8)), message=3)))

    def test_stale_new_camera_cannot_replace_current_capture(self):
        self.store.accept(request(body(source(image=video()))))
        self.store.accept(request(body(source(sequence=2, image=video(capture="8" * 32, age=3.)), message=2)))
        self.assertEqual(self.store.video_snapshot()["capture_session_id"], "9" * 32)

    def test_orchestrator_restart_does_not_relabel_old_image_as_new_boot(self):
        self.store.accept(request(body(source(image=video()))))
        self.store.accept(request(body(source(session="f" * 32), relay="1" * 32)))
        result = self.store.video_snapshot()
        self.assertFalse(result["available"])
        self.assertIsNone(result["frame"])
        self.assertEqual(result["session_id"], "f" * 32)

    def test_queue_age_alone_can_expire_a_new_frame(self):
        self.store.accept(request(body(source(image=video()), age=2.1)))
        self.assertFalse(self.store.video_snapshot()["available"])

    def test_only_native_supervision_owner_may_send_raw_video(self):
        self.assertRaises(ValueError, owner_frame, "acquisition", "a" * 32, 1,
            source_mode="PYTHON_NATIVE", video_frame=video())
        self.assertRaises(ValueError, owner_frame, "supervision", "b" * 32, 1,
            source_mode="LABVIEW_BRIDGE", video_frame=video())

    def test_geometry_base64_type_and_size_fail_before_ingress(self):
        for key, wrong in (("width", 3), ("height", True), ("pixel_type", "U16"),
                           ("data", "@@@@"), ("capture_session_id", "unknown"),
                           ("source_age_seconds", float("inf")),
                           ("observed_utc", "not-a-time+00:00")):
            changed = video()
            changed[key] = wrong
            self.assertRaises(ValueError, validate_video_frame, changed)
        changed = video()
        changed.update(width=524289, height=1, data=base64.b64encode(b"x" * 524289).decode("ascii"))
        self.assertRaises(ValueError, validate_video_frame, changed)


if __name__ == "__main__":
    unittest.main()
