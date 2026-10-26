"""Synthetic VI observations in RAM only; no socket, NI, VI or XP operation."""
import base64
import copy
import json
import sys
import threading
import unittest
from xml.sax.saxutils import escape

from legacy.xp_acq_control.elyse_agent.federation_wire import (
    MAX_VIDEO_RAW_BYTES, owner_frame, validate_owner_frame,
)
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS
from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import (
    PUBLICATION, MAX_VI_BYTES, SupervisionTelemetryPublisher,
    decode_vi_observation, validate_vi_observation,
)
from legacy.xp_acq_control.elyse_agent.telemetry_relay import canonical, sign, MAX_RELAY_FRAME

MODERN = sys.version_info >= (3, 8)
if MODERN:
    from DeviceServers.control.elyse_acq.federated_telemetry import FederatedTelemetryStore

KEYS = dict(acquisition=b"acq-offline-test-key-00000000000000000000",
            supervision=b"sup-offline-test-key-00000000000000000000")


def image(sequence=1, age=.1, capture="9" * 32, source="b" * 32, size=4):
    return dict(source="labview_supervision_ni1409", source_session_id=source,
        simulated=False, sequence=sequence,
        sequence_interpretation="software grab observation, not hardware frame counter",
        capture_session_id=capture, observed_utc="2026-10-26T12:00:00.000001+00:00",
        sample_elapsed_seconds=.01, width=2 if size == 4 else size, height=2 if size == 4 else 1,
        pixel_type="U8", encoding="base64_raw_row_major",
        data=base64.b64encode(b"x" * size).decode("ascii"), channel=2,
        processing="raw_grab_before_legacy_interlace_bcg_profiles", hardware_acknowledged=False,
        source_age_seconds=age)


def part(age=.2):
    return dict(values=[20. + index / 10. for index in range(16)], source_age_seconds=age,
        source="observed_labview_control_memory", selector=-1., pending_selector=False)


def observation(sequence=1, counter=None, video=None, source="b" * 32):
    return dict(schema_version=1, publication=PUBLICATION, source_session_id=source,
                sequence=sequence, source_running=True, counter_part=counter, video_frame=video)


def encoded(value):
    return json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")


def xml(camera_error=False):
    rows = []
    for bank in BANKS:
        if bank == "C12NI1409":
            payload = '<String><Name>C12NI1409</Name><Val>img-fixture</Val></String>'
        elif bank == "C1011NI6602":
            values = [10. + index / 10. for index in range(16)] + part()["values"] + [-1.]
            payload = '<Cluster><Name>C10-11 NI6602</Name><NumElts>33</NumElts>' + ''.join(
                '<DBL><Name>field{0}</Name><Val>{1}</Val></DBL>'.format(index, value)
                for index, value in enumerate(values)) + '</Cluster>'
        else:
            payload = '<DBL><Name>fixture</Name><Val>0</Val></DBL>'
        rows.append('<Cluster><Name></Name><NumElts>3</NumElts>'
            '<String><Name>bank</Name><Val>{0}</Val></String>'
            '<LvVariant><Name>Get Control Value Variant</Name>{1}</LvVariant>'
            '<Cluster><Name>error</Name><NumElts>3</NumElts>'
            '<Boolean><Name>status</Name><Val>{2}</Val></Boolean><I32><Name>code</Name><Val>{3}</Val></I32>'
            '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(escape(bank), payload,
                int(camera_error and bank == "C12NI1409"), -100 if camera_error and bank == "C12NI1409" else 0))
    return ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
            + ''.join(rows) + '</Array></LvVariant>').encode('ascii')


class SupervisionVITests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.runtime = SupervisionRuntime(identity=dict(runtime_protocol_version=2,
            session_id="a" * 32, build_id="c" * 64), clock=lambda: self.now)
        self.publisher = SupervisionTelemetryPublisher(self.runtime, ("127.0.0.1", 12345),
            KEYS["supervision"], clock=lambda: self.now)
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        self.publisher.close()

    def take(self):
        body = self.publisher.outbox.peek()
        self.publisher.outbox.acknowledge(body["relay_id"], body["message_id"])
        return body

    def submit(self, value):
        return self.publisher.ingest_observation(encoded(value), "127.0.0.1")

    def test_cold_runtime_accepts_existing_27_control_xml_and_only_forwards_local_part(self):
        self.assertTrue(self.runtime.try_telemetry_snapshot()["telemetry_bridge_mode"])
        result = self.publisher.ingest(xml(), "127.0.0.1")
        self.assertEqual(result["bank_count"], 27)
        packet = self.take()["packet"]
        self.assertEqual(packet["source_mode"], "LABVIEW_BRIDGE")
        self.assertEqual(packet["counter_part"]["values"], part()["values"])
        self.assertEqual(packet["counter_part"]["source"], "observed_labview_control_memory")
        self.assertEqual([row["publication"] for row in packet["banks"]], ["C12NI1409"])
        self.assertEqual(packet["banks"][0]["data"], "img-fixture")
        self.assertIsNone(packet["video_frame"])
        self.assertEqual(self.runtime._owners, {})
        self.assertIsNone(self.runtime._thread)

    def test_typed_frame_preserves_main_vi_and_camera_capture_identity(self):
        value = observation(counter=part(), video=image())
        self.assertEqual(decode_vi_observation(encoded(value)), value)
        receipt = self.submit(value)
        packet = self.take()["packet"]
        validate_owner_frame(packet)
        self.assertEqual(receipt["source_session_id"], "b" * 32)
        self.assertEqual(packet["video_frame"]["source_session_id"], "b" * 32)
        self.assertEqual(packet["video_frame"]["capture_session_id"], "9" * 32)
        self.assertEqual(packet["video_frame"]["sequence"], 1)
        self.assertEqual(packet["counter_part"]["source_age_seconds"], .2)
        self.assertEqual(packet["source_identity"], dict(source="labview_supervision_typed_local",
            session_id="b" * 32, sequence=1))
        self.assertIsNone(packet["banks"][0]["data"])
        self.assertFalse(receipt["hardware_writes"])

    def test_xml_camera_control_failure_does_not_hide_valid_counter_observation(self):
        self.publisher.ingest(xml(camera_error=True), "127.0.0.1")
        packet = self.take()["packet"]
        self.assertEqual(packet["counter_part"]["values"], part()["values"])
        self.assertIsNone(packet["banks"][0]["data"])
        self.assertEqual(packet["banks"][0]["error"]["code"], -100)
        self.assertTrue(packet["banks"][0]["error"]["source"])

    def test_video_does_not_freshen_xml_counter_and_xml_does_not_freshen_video(self):
        self.submit(observation(video=image()))
        self.take()
        self.now = .2
        self.publisher.ingest(xml(), "127.0.0.1")
        self.take()
        self.now = 1.1
        self.submit(observation(sequence=2, video=image(sequence=2, age=.3)))
        packet = self.take()["packet"]
        self.assertAlmostEqual(packet["counter_part"]["source_age_seconds"], .9)
        self.assertEqual(packet["video_frame"]["source_age_seconds"], .3)
        self.now = 1.6
        self.publisher.ingest(xml(), "127.0.0.1")
        packet = self.take()["packet"]
        self.assertEqual(packet["counter_part"]["source_age_seconds"], 0.)
        self.assertIsNone(packet["video_frame"])
        self.assertAlmostEqual(self.publisher._aged(self.publisher._vi_video)["source_age_seconds"], .8)

    def test_retry_and_same_image_in_new_message_do_not_reset_ages(self):
        value = observation(counter=part(), video=image())
        self.submit(value)
        self.take()
        self.now = .5
        retry = copy.deepcopy(value)
        retry["video_frame"]["source_age_seconds"] = .6
        self.assertTrue(self.submit(retry)["duplicate"])
        self.assertIsNone(self.publisher.outbox.peek())
        self.assertAlmostEqual(self.publisher._aged(self.publisher._vi_counter)["source_age_seconds"], .7)
        self.now = 1.1
        self.submit(observation(sequence=2, video=image(age=0.)))
        packet = self.take()["packet"]
        self.assertIsNone(packet["video_frame"])
        self.assertAlmostEqual(self.publisher._aged(self.publisher._vi_video)["source_age_seconds"], 1.2)
        self.assertAlmostEqual(packet["counter_part"]["source_age_seconds"], 1.3)

    def test_vi_source_and_camera_replays_are_rejected_without_cache_mutation(self):
        self.submit(observation(video=image()))
        self.take()
        changed = image()
        changed["data"] = base64.b64encode(b"yyyy").decode("ascii")
        self.assertRaises(ValueError, self.submit, observation(sequence=2, video=changed))
        self.assertEqual(self.publisher._typed_sequence, 1)
        self.now = 1.1
        self.submit(observation(sequence=2, video=image(capture="8" * 32)))
        self.take()
        self.assertRaises(ValueError, self.submit, observation(sequence=3, video=image(sequence=2)))
        self.submit(observation(video=image(source="d" * 32, capture="7" * 32), source="d" * 32))
        self.take()
        self.assertRaises(ValueError, self.submit, observation(sequence=4, video=image(sequence=3)))

    def test_stale_new_vi_source_cannot_retire_current_source(self):
        self.submit(observation(video=image()))
        self.take()
        self.assertRaises(ValueError, self.submit,
            observation(video=image(age=3., source="d" * 32, capture="7" * 32), source="d" * 32))
        self.assertEqual(self.publisher._typed_session, "b" * 32)
        self.assertEqual(self.publisher._aged(self.publisher._vi_video)["capture_session_id"], "9" * 32)

    def test_native_owners_or_lifecycle_transition_reject_all_vi_ingress(self):
        for state in ("INITIALIZING", "RUNNING", "EXECUTING", "DEINITIALIZING", "FAULT", "STOPPED"):
            self.runtime._state = state
            self.assertRaises(ValueError, self.publisher.ingest, xml(), "127.0.0.1")
            self.assertRaises(ValueError, self.submit, observation(video=image()))
        self.assertEqual(self.runtime._owners, {})
        self.assertEqual(self.publisher.typed_accepted, 0)
        self.runtime._state = "IDLE"
        self.runtime._pending = ("initialize", None)
        self.assertRaises(ValueError, self.submit, observation(video=image()))

    def test_recent_vi_fences_initialize_then_accepted_transition_discards_vi_cache(self):
        class FakeLifecycleThread(object):
            def is_alive(self):
                return True
        self.runtime._thread = FakeLifecycleThread()
        self.submit(observation(counter=part(), video=image()))
        self.take()
        self.assertRaises(RuntimeError, self.runtime.initialize, True)
        self.assertEqual(self.runtime.snapshot()["state"], "IDLE")
        self.now = 2.1
        self.runtime.initialize(startup_confirmed=True)
        self.assertEqual(self.runtime.snapshot()["state"], "INITIALIZING")
        self.assertIsNone(self.publisher._vi_counter)
        self.assertIsNone(self.publisher._vi_video)
        self.assertEqual(self.runtime._owners, {})
        self.assertRaises(ValueError, self.submit, observation(sequence=2, video=image(sequence=2)))
        self.runtime._thread = None
        self.runtime._state, self.runtime._pending, self.runtime._operation = "IDLE", None, None
        self.runtime._state_revision += 1
        self.assertTrue(self.publisher.publish_once())
        packet = self.take()["packet"]
        self.assertIsNone(packet["counter_part"])
        self.assertIsNone(packet["video_frame"])
        self.assertIsNone(self.publisher._typed_session)
        self.assertRaises(ValueError, self.submit, observation(sequence=99, video=image(sequence=99)))
        self.submit(observation(video=image(source="d" * 32), source="d" * 32))
        self.assertEqual(self.take()["packet"]["video_frame"]["source_session_id"], "d" * 32)

    def test_native_projection_does_not_call_publisher_status_while_runtime_lock_is_held(self):
        original = self.publisher.status
        acquired = []
        def checked_status():
            def probe():
                got = self.runtime._lock.acquire(False)
                acquired.append(got)
                if got:
                    self.runtime._lock.release()
            worker = threading.Thread(target=probe)
            worker.start()
            worker.join(1)
            return original()
        self.publisher.status = checked_status
        self.runtime.snapshot()
        self.assertEqual(acquired, [True])
        self.runtime.try_telemetry_snapshot()
        self.assertEqual(acquired, [True])  # Publisher status omitted from that projection.

    def test_native_component_capture_and_json_projection_have_no_nested_opposing_locks(self):
        observed = []
        def available_from_other_thread(lock):
            def probe():
                got = lock.acquire(False)
                observed.append(got)
                if got:
                    lock.release()
            worker = threading.Thread(target=probe)
            worker.start()
            worker.join(1)
        original_counter = self.runtime.counter_memory_part
        def counter():
            available_from_other_thread(self.publisher.lock)
            return original_counter()
        original_transform = self.publisher.packet_transform
        def transform(*args):
            available_from_other_thread(self.runtime._lock)
            return original_transform(*args)
        self.runtime.counter_memory_part = counter
        self.publisher.packet_transform = transform
        self.runtime._state = "RUNNING"
        self.assertTrue(self.publisher.publish_once())
        self.assertEqual(observed, [True, True])

    def test_native_supervision_runtime_keeps_raw_camera_and_counter_publication(self):
        from tests.unit.test_two_orchestrator_end_to_end import supervision_runtime_with_ram_owners
        runtime = supervision_runtime_with_ram_owners()
        endpoint = runtime._owners["video"]
        endpoint.input_snapshot = lambda: dict(current=True, age_seconds=.1,
            card_generation="9" * 32, sample=copy.deepcopy(endpoint.value["sample"]))
        source = SupervisionTelemetryPublisher(runtime, ("127.0.0.1", 12345), KEYS["supervision"],
                                               clock=lambda: 0.)
        runtime.telemetry_publisher = source
        try:
            self.assertTrue(source.publish_once())
            packet = source.outbox.peek()["packet"]
            self.assertEqual(packet["source_mode"], "PYTHON_NATIVE")
            self.assertEqual(packet["counter_part"]["values"], part()["values"])
            self.assertEqual(packet["video_frame"]["source"], "python_supervision_ni1409")
            self.assertEqual(packet["video_frame"]["capture_session_id"], "9" * 32)
            self.assertNotIn("source_session_id", packet["video_frame"])
            self.assertIsNone(packet["banks"][0]["data"])
            self.assertIsNone(runtime._thread)
        finally:
            source.close()

    def test_nonwaiting_runtime_projection_fails_closed_under_foreign_thread_lock(self):
        locked, release = threading.Event(), threading.Event()
        def hold():
            with self.runtime._lock:
                locked.set()
                release.wait(2)
        worker = threading.Thread(target=hold)
        worker.start()
        self.assertTrue(locked.wait(1))
        try:
            self.assertIsNone(self.runtime.try_telemetry_snapshot())
            self.assertRaises(ValueError, self.submit, observation(video=image()))
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_bounds_source_flags_strict_json_and_loopback_are_enforced(self):
        valid = observation(counter=part(), video=image())
        self.assertRaises(ValueError, self.publisher.ingest_observation, encoded(valid), "10.20.30.2")
        self.assertRaises(ValueError, self.publisher.ingest, xml(), "10.20.30.10")
        self.assertRaises(ValueError, decode_vi_observation, b"x" * (MAX_VI_BYTES + 1))
        duplicate = encoded(valid).replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1')
        self.assertRaises(ValueError, decode_vi_observation, duplicate)
        for change in (dict(source_running=False), dict(sequence=True), dict(counter_part=None, video_frame=None)):
            self.assertRaises(ValueError, validate_vi_observation, dict(valid, **change))
        mismatch = copy.deepcopy(valid)
        mismatch["video_frame"]["source_session_id"] = "f" * 32
        self.assertRaises(ValueError, validate_vi_observation, mismatch)

    def test_512kib_camera_request_and_forwarded_signed_body_fit_all_bounds(self):
        value = observation(video=image(size=MAX_VIDEO_RAW_BYTES))
        raw = validate_vi_observation(value)
        self.assertLess(len(raw), MAX_VI_BYTES)
        self.submit(value)
        body = self.take()
        signed = dict(body=body, nonce="5" * 32)
        signed["signature"] = sign(KEYS["supervision"], "ACQ-TELEMETRY-REQUEST-1", signed)
        self.assertLess(len(canonical(signed)), MAX_RELAY_FRAME)
        self.assertEqual(len(base64.b64decode(body["packet"]["video_frame"]["data"])), MAX_VIDEO_RAW_BYTES)


@unittest.skipUnless(MODERN, "Everest store runs modern Python")
class SupervisionVIEverestTests(unittest.TestCase):
    take = SupervisionVITests.take
    submit = SupervisionVITests.submit

    def setUp(self):
        SupervisionVITests.setUp(self)
        self.store = FederatedTelemetryStore(KEYS, clock=lambda: self.now)

    def tearDown(self):
        self.store.close()
        SupervisionVITests.tearDown(self)

    def forward(self):
        body = self.take()
        value = dict(body=body, nonce="5" * 32)
        self.store.accept(dict(value, signature=sign(KEYS["supervision"], "ACQ-TELEMETRY-REQUEST-1", value)))

    def test_labview_frame_is_visible_but_never_native_command_authority(self):
        self.submit(observation(counter=part(), video=image()))
        self.forward()
        video = self.store.video_snapshot()
        self.assertTrue(video["available"])
        self.assertEqual(video["source_mode"], "LABVIEW_BRIDGE")
        self.assertEqual(video["source_session_id"], "b" * 32)
        self.assertEqual(self.store.snapshot()["owners"]["supervision"]["source_identity"]["sequence"], 1)
        self.assertTrue(self.store.owner_current("supervision"))
        self.assertFalse(self.store.owner_current("supervision", native=True))
        self.now = 2.1
        self.assertFalse(self.store.video_snapshot()["available"])

    def test_native_transition_cannot_relabel_cached_vi_camera_as_native(self):
        self.submit(observation(video=image()))
        self.forward()
        frame = owner_frame("supervision", "a" * 32, self.publisher.sequence + 1,
                            source_mode="PYTHON_NATIVE", counter_part=part())
        body = self.publisher.outbox.status()
        message = dict(schema_version=1, relay_id=body["relay_id"], message_id=2,
            received_utc_on_xp="2026-10-26T12:00:00+00:00", age_seconds_on_xp=0.,
            packet=frame, hardware_writes=False)
        value = dict(body=message, nonce="6" * 32)
        self.store.accept(dict(value, signature=sign(KEYS["supervision"], "ACQ-TELEMETRY-REQUEST-1", value)))
        self.assertFalse(self.store.video_snapshot()["available"])
        self.assertIsNone(self.store.video_snapshot()["frame"])
        frame = owner_frame("supervision", "a" * 32, self.publisher.sequence + 2,
                            source_mode="LABVIEW_BRIDGE", counter_part=part())
        message.update(message_id=3, packet=frame)
        value = dict(body=message, nonce="7" * 32)
        self.store.accept(dict(value, signature=sign(KEYS["supervision"], "ACQ-TELEMETRY-REQUEST-1", value)))
        self.assertIsNone(self.store.video_snapshot()["frame"])
        self.assertFalse(self.store.video_snapshot()["available"])

    def test_camera_capture_ids_are_namespaced_by_main_vi_source_run(self):
        self.submit(observation(video=image(sequence=5)))
        self.forward()
        self.now = 1.1
        self.submit(observation(video=image(source="d" * 32), source="d" * 32))
        self.forward()
        video = self.store.video_snapshot()
        self.assertEqual(video["source_session_id"], "d" * 32)
        self.assertEqual(video["capture_session_id"], "9" * 32)
        self.assertEqual(video["sequence"], 1)
        self.assertTrue(video["available"])


if __name__ == "__main__":
    unittest.main()
