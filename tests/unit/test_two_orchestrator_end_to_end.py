"""Owner publisher -> signed RAM ingress -> 27-bank view, without sockets/NI.

XP-compatible publisher cases also run under CPython 3.4. Everest store and
web projection cases run only on the modern host; no device is instantiated.
All source values are synthetic fixtures, not measured accelerator data.
"""
import base64
import copy
import importlib
import json
import os
import sys
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.federation_wire import (
    MAX_OWNER_FRAME_BYTES, MAX_VIDEO_RAW_BYTES, OWNED_BANKS, validate_owner_frame,
)
from legacy.xp_acq_control.elyse_agent.orchestrator_publisher import OwnerTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS, MAX_XML_BYTES
from legacy.xp_acq_control.elyse_agent.standard_banks import INPUTS, standard_packet
from legacy.xp_acq_control.elyse_agent.telemetry_relay import MAX_RELAY_FRAME, canonical, sign


KEYS = dict(acquisition=b"integration-acquisition-key-000000000000000",
            supervision=b"integration-supervision-key-000000000000000")
MODERN_HOST = sys.version_info >= (3, 8)
if MODERN_HOST:
    from DeviceServers.control.elyse_acq.federated_telemetry import FederatedTelemetryStore


class Clock(object):
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now


def counter_memory(start, age=.25):
    return dict(values=[start + index / 10. for index in range(16)],
                source_age_seconds=age, source="last_successful_counter_command_memory",
                selector=-1., pending_selector=False)


def raw_video(raw=b"\x00\x01\x02\x03", width=2, height=2, age=.1):
    return dict(source="python_supervision_ni1409", simulated=False, sequence=1,
        sequence_interpretation="software grab observation, not hardware frame counter",
        capture_session_id="9" * 32, observed_utc="2026-10-26T12:00:00.000001+00:00",
        sample_elapsed_seconds=.01, width=width, height=height, pixel_type="U8",
        encoding="base64_raw_row_major", data=base64.b64encode(raw).decode("ascii"),
        channel=2, processing="raw_grab_before_legacy_interlace_bcg_profiles",
        hardware_acknowledged=False, source_age_seconds=age)


def supervision_runtime_with_ram_owners():
    """Real runtime.snapshot/broker with RAM-only endpoints, never initialized."""
    from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
    from legacy.xp_acq_control.elyse_agent.supervision_service import SYNC_TASKS, VIDEO_TASKS

    class RamEndpoint(object):
        def __init__(self, name):
            sync = name == "sync"
            self.value = dict(state="READY", error="", input_error="", unresolved_request=False,
                input_current=True, sample_age_seconds=.1, sample_sequence=1,
                tasks=SYNC_TASKS if sync else VIDEO_TASKS,
                native=dict(ownership_uncertain=False, resource_count=8 if sync else 2,
                    worker_generation=("6" if sync else "9") * 32,
                    worker_state="IDLE_OWNED", active_request_id=None),
                sample=dict(counter_memory=dict(timing_pairs_us=counter_memory(20.)["values"],
                    running_counters=list(range(8)), uncertain_counters=[])) if sync
                    else dict(video_frame=raw_video()))

        def status(self):
            return copy.deepcopy(self.value)

    runtime = SupervisionRuntime(identity=dict(runtime_protocol_version=2,
        session_id="f" * 32, build_id="e" * 64), remote_enabled=True,
        counter_timing_controls_verified=True, clock=lambda: 0.)
    runtime._owners = {name: RamEndpoint(name) for name in ("sync", "video")}
    runtime._state, runtime._state_revision, runtime._startup_complete = "RUNNING", 7, True
    class RamPublisher(object):
        def status(self):
            return dict(source_mode="PYTHON_NATIVE")
    runtime.telemetry_publisher = RamPublisher()
    return runtime


class RamRuntime(object):
    """Projection contract only; no worker/thread/native driver is started."""
    def __init__(self, role, clock, session=None, video=None):
        self._clock, self._lock = clock, threading.RLock()
        self._identity = dict(runtime_protocol_version=2,
            session_id=session or ("a" if role == "acquisition" else "b") * 32,
            build_id="8" * 64)
        self.role, self.video = role, video
        self.memory = counter_memory(10. if role == "acquisition" else 20.)
        self.value = dict(self._identity, state="RUNNING", sequence=1, state_revision=1,
            latest=None, age_seconds=.4, resource_count=21 if role == "acquisition" else 10,
            stale=False, error="", telemetry_view_current=True, measurement_current=False,
            telemetry_bridge_mode=False)
        if role == "acquisition":
            # One unrelated output-card error must not erase independent inputs.
            self.value.update(state="FAULT", stale=True, error="Fixture output card 9 failed")
            cards = {}
            for name, item in INPUTS.items():
                native_name, kind, device, count, unused_field, value_type = item
                values = ([index % 2 == 0 for index in range(count)] if value_type == "Boolean"
                          else [device / 10. + index / 1000. for index in range(count)])
                cards[str(device)] = dict(state="READY", input_current=True,
                    unresolved_request=False, sample_age_seconds=.4, sample_sequence=4,
                    native=dict(ownership_uncertain=False, worker_generation=str(device) * 32),
                    sample=dict(device=device, banks={native_name: dict(
                        device=device, kind=kind, values=values)}))
            cards["9"] = dict(state="FAULT", input_current=False, sample_sequence=0,
                native=dict(ownership_uncertain=False, worker_generation="9" * 32))
            self.value["card_processes"] = dict(transport_age_seconds=.2, cards=cards)
        else:
            self.value.update(server_variant="supervision_control_vnext", host_role="supervision",
                source_host="10.20.30.2", card_health=dict(all_required_ready=True),
                latest=dict(source="python_supervision_card_processes", simulated=False,
                            banks={}, counter_memory_current=True))

    def snapshot(self):
        value = copy.deepcopy(self.value)
        value["_publisher_counter_part"] = copy.deepcopy(self.memory)
        value["_publisher_video_frame"] = copy.deepcopy(self.video)
        return value

    def counter_memory_part(self):
        return copy.deepcopy(self.memory)

    def video_frame_snapshot(self):
        return copy.deepcopy(self.video)


def publisher(role, clock, session=None, video=None):
    runtime = RamRuntime(role, clock, session, video)
    value = OwnerTelemetryPublisher(runtime, ("127.0.0.1", 12345), KEYS[role],
                                    role=role, clock=clock)
    return runtime, value


def signed_request(body, role=None):
    signed = dict(body=body, nonce="7" * 32)
    return dict(signed, signature=sign(KEYS[role or body["packet"]["owner"]],
        "ACQ-TELEMETRY-REQUEST-1", signed))


def deliver(store, source):
    assert source.publish_once()
    body = source.outbox.peek()
    ack = store.accept(signed_request(body))
    source.outbox.acknowledge(body["relay_id"], body["message_id"])
    return body, ack


def bridge_packet(runtime, sequence=1):
    packet = standard_packet(runtime.snapshot(), sequence)
    packet["producer_kind"] = "copied_acquisition"
    packet["data"].update(capture_kind="sequential_local_controls",
                           timestamp_origin="xp_receipt_not_card_sample")
    values = {"C3_IN_DIO96": [True] * 56, "C12NI1409": "img-fixture",
              "C1011NI6602": [30. + index / 10. for index in range(16)]
                             + [40. + index / 10. for index in range(16)] + [-1.]}
    for record in packet["data"]["banks"]:
        if record["publication"] in values:
            record.update(data=values[record["publication"]],
                          error=dict(status=False, code=0, source=""))
    return packet


class XpOwnerPublisherEndToEndTests(unittest.TestCase):
    def test_native_projection_preserves_calibration_per_card_age_and_fixed_authority(self):
        clock = Clock()
        runtime, source = publisher("acquisition", clock)
        self.assertTrue(source.publish_once())
        body = source.outbox.peek()
        frame = body["packet"]
        validate_owner_frame(frame)
        self.assertEqual(set(row["publication"] for row in frame["banks"]),
                         set(OWNED_BANKS["acquisition"]))
        records = {row["publication"]: row for row in frame["banks"]}
        for name in ("C1NI6071E", "C2NI6071E"):
            scale, offset = source.calibration[(name, 0)]
            device = INPUTS[name][2]
            self.assertAlmostEqual(records[name]["data"][0], device / 10. * scale + offset)
            self.assertAlmostEqual(records[name]["source_age_seconds"], .6)
        self.assertEqual(records["C3_IN_DIO96"]["data"], [index % 2 == 0 for index in range(56)])
        self.assertIsNone(records["C9NI6703"]["data"])
        self.assertIsNone(records["EPS"]["data"])
        self.assertNotIn("C12NI1409", records)
        self.assertEqual(frame["source_mode"], "PYTHON_NATIVE")
        self.assertEqual(body["age_seconds_on_xp"], 0.)
        self.assertIsNone(source.worker)
        self.assertIsNone(source.server)

    def test_max_raw_camera_fits_real_owner_outbox_and_signed_relay_limit(self):
        clock = Clock()
        raw = bytes(bytearray(range(256))) * (MAX_VIDEO_RAW_BYTES // 256)
        runtime, source = publisher("supervision", clock,
                                    video=raw_video(raw, 1024, 512))
        self.assertTrue(source.publish_once())
        body = source.outbox.peek()
        request = signed_request(body)
        encoded = validate_owner_frame(body["packet"])
        self.assertEqual(base64.b64decode(body["packet"]["video_frame"]["data"]), raw)
        self.assertGreater(len(encoded), MAX_XML_BYTES)
        self.assertLessEqual(len(encoded), MAX_OWNER_FRAME_BYTES)
        self.assertEqual(source.outbox.max_encoded_bytes, 900 * 1024)
        self.assertLess(len(canonical(request)), MAX_RELAY_FRAME)
        self.assertEqual(len(body["packet"]["counter_part"]["values"]), 16)
        # A camera source does not fabricate the old opaque C12 String.
        self.assertIsNone(body["packet"]["banks"][0]["data"])

    def test_bridge_projector_never_includes_foreign_camera_bank(self):
        clock = Clock()
        runtime, source = publisher("acquisition", clock)
        source._enqueue(bridge_packet(runtime), age=.3, projection=runtime.snapshot())
        frame = source.outbox.peek()["packet"]
        self.assertEqual(frame["source_mode"], "LABVIEW_BRIDGE")
        self.assertNotIn("C12NI1409", [row["publication"] for row in frame["banks"]])
        self.assertEqual(frame["counter_part"]["values"],
                         [30. + index / 10. for index in range(16)])
        self.assertEqual(frame["counter_part"]["source_age_seconds"], .3)
        self.assertEqual(source.outbox.peek()["age_seconds_on_xp"], 0.)


@unittest.skipUnless(MODERN_HOST, "Everest DeviceServers package requires modern Python")
class TwoOrchestratorEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.store = FederatedTelemetryStore(KEYS, clock=self.clock)

    def tearDown(self):
        self.store.close()

    def test_native_start_orders_independent_keys_sessions_and_exact_counter_composite(self):
        for order in (("acquisition", "supervision"), ("supervision", "acquisition")):
            store = FederatedTelemetryStore(KEYS, clock=self.clock)
            try:
                sources = {role: publisher(role, self.clock, video=raw_video() if role == "supervision" else None)[1]
                           for role in order}
                for role in order:
                    body, unused_ack = deliver(store, sources[role])
                value = store.snapshot()
                self.assertEqual(len(value["publications"]), 27)
                self.assertEqual(set(value["publications"]), set(BANKS))
                self.assertEqual(value["owners"]["acquisition"]["session_id"], "a" * 32)
                self.assertEqual(value["owners"]["supervision"]["session_id"], "b" * 32)
                self.assertEqual(value["unavailable_owners"], [])
                combined = value["publications"]["C1011NI6602"]
                self.assertEqual(combined["data"], counter_memory(10.)["values"]
                    + counter_memory(20.)["values"] + [-1.])
                self.assertFalse(combined["hardware_acknowledged"])
                self.assertFalse(combined["atomic_across_owners"])
                self.assertEqual(store.video_snapshot()["owner"], "supervision")
                self.assertTrue(store.video_snapshot()["available"])
                forged = copy.deepcopy(body)
                self.assertRaises(ValueError, store.accept,
                                  signed_request(forged, "supervision" if body["packet"]["owner"] == "acquisition" else "acquisition"))
            finally:
                store.close()

    def test_acquisition_restart_does_not_replace_supervision_or_revive_old_boot(self):
        acq_runtime, acq = publisher("acquisition", self.clock)
        sup_runtime, sup = publisher("supervision", self.clock, video=raw_video())
        deliver(self.store, acq)
        deliver(self.store, sup)
        unused_new_runtime, new_acq = publisher("acquisition", self.clock, session="f" * 32)
        deliver(self.store, new_acq)
        value = self.store.snapshot()
        self.assertEqual(value["owners"]["acquisition"]["session_id"], "f" * 32)
        self.assertEqual(value["owners"]["supervision"]["session_id"], "b" * 32)
        self.assertEqual(self.store.video_snapshot()["capture_session_id"], "9" * 32)
        acq_runtime.value["sequence"] += 1
        self.assertTrue(acq.publish_once())
        self.assertRaises(ValueError, self.store.accept, signed_request(acq.outbox.peek()))

    def test_source_queue_and_receiver_ages_count_once_and_expire_independently(self):
        unused_runtime, source = publisher("acquisition", self.clock)
        self.assertTrue(source.publish_once())
        self.clock.now = .3
        body = source.outbox.peek()
        self.assertAlmostEqual(body["age_seconds_on_xp"], .3)
        self.store.accept(signed_request(body))
        self.clock.now = .7
        bank = self.store.snapshot()["publications"]["C1NI6071E"]
        self.assertAlmostEqual(bank["age_seconds"], .4 + .2 + .3 + .4)
        self.assertFalse(bank["stale"])
        unused_runtime, sup = publisher("supervision", self.clock, video=raw_video())
        deliver(self.store, sup)
        self.clock.now = 1.5
        value = self.store.snapshot()
        self.assertAlmostEqual(value["publications"]["C1NI6071E"]["age_seconds"], 2.1)
        self.assertTrue(value["publications"]["C1NI6071E"]["stale"])
        self.assertTrue(self.store.video_snapshot()["available"])
        # Command memory was captured later than the analog input sample.
        self.assertIsNotNone(value["publications"]["C1011NI6602"]["data"])
        self.clock.now = 1.76
        value = self.store.snapshot()
        self.assertIsNone(value["publications"]["C1011NI6602"]["data"])
        self.assertTrue(self.store.video_snapshot()["available"])

    def test_duplicate_camera_capture_cannot_be_freshened_by_owner_publication(self):
        runtime, source = publisher("supervision", self.clock, video=raw_video(age=0.))
        deliver(self.store, source)
        self.clock.now = 1.
        runtime.value["sequence"] += 1
        # Exercise a newly allowed camera publication without sleeping one second.
        source.last_video_sent = None
        deliver(self.store, source)
        self.assertEqual(self.store.video_snapshot()["age_seconds"], 1.)
        self.clock.now = 2.01
        runtime.value["sequence"] += 1
        source.last_video_sent = None
        deliver(self.store, source)
        image = self.store.video_snapshot()
        self.assertTrue(image["stale"])
        self.assertIsNone(image["frame"])

    def test_max_camera_reaches_store_without_entering_27_bank_json(self):
        raw = b"x" * MAX_VIDEO_RAW_BYTES
        unused_runtime, source = publisher("supervision", self.clock,
            video=raw_video(raw, 1024, 512))
        body, unused_ack = deliver(self.store, source)
        self.assertLess(len(canonical(signed_request(body))), MAX_RELAY_FRAME)
        frame = self.store.video_snapshot()["frame"]
        self.assertEqual(base64.b64decode(frame["data"]), raw)
        view = self.store.snapshot()
        self.assertLess(len(json.dumps(view)), MAX_XML_BYTES)
        self.assertNotIn("data", view["video_metadata"])
        self.assertNotIn("frame", view["video_metadata"])
        self.assertIsNone(view["publications"]["C12NI1409"]["data"])

    def test_bridge_filter_preserves_supervision_string_and_selects_correct_counter_halves(self):
        sources = {role: publisher(role, self.clock) for role in ("supervision", "acquisition")}
        for role in ("supervision", "acquisition"):
            runtime, source = sources[role]
            packet = bridge_packet(runtime)
            if role == "acquisition":
                for record in packet["data"]["banks"]:
                    if record["publication"] == "C12NI1409":
                        record["data"] = "foreign-must-not-overwrite"
            else:
                for record in packet["data"]["banks"]:
                    if record["publication"] == "C3_IN_DIO96":
                        record["data"] = [False] * 56
            source._enqueue(packet, age=.1, projection=runtime.snapshot())
            self.store.accept(signed_request(source.outbox.peek()))
        value = self.store.snapshot()
        self.assertEqual(value["publications"]["C12NI1409"]["data"], "img-fixture")
        self.assertEqual(value["publications"]["C12NI1409"]["owner"], "supervision")
        self.assertEqual(value["publications"]["C3_IN_DIO96"]["data"], [True] * 56)
        self.assertEqual(value["publications"]["C3_IN_DIO96"]["owner"], "acquisition")
        self.assertEqual(value["publications"]["C1011NI6602"]["data"],
            [30. + index / 10. for index in range(16)]
            + [40. + index / 10. for index in range(16)] + [-1.])
        self.assertFalse(self.store.video_snapshot()["available"])

    def test_web_projection_retains_27_banks_honest_unavailable_and_video_metadata_only(self):
        for role in ("acquisition", "supervision"):
            unused_runtime, source = publisher(role, self.clock,
                                               video=raw_video() if role == "supervision" else None)
            deliver(self.store, source)
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        backend = os.path.join(root, "web", "backend")
        if backend not in sys.path:
            sys.path.insert(0, backend)
        api = importlib.import_module("acq_telemetry_api")
        result = api.present_snapshot(json.dumps(self.store.snapshot()), "ON")
        self.assertEqual(result["source"], "federated_orchestrators")
        self.assertEqual(len(result["snapshot"]["publications"]), 27)
        self.assertEqual(result["quality"], "INCOMPLETE")
        self.assertIn("C12NI1409", result["unavailable_banks"])
        self.assertIsNone(result["snapshot"]["publications"]["C12NI1409"]["data"])
        self.assertIsNone(result["snapshot"]["publications"]["DPC"]["age_seconds"])
        self.assertEqual(result["orchestrators"]["supervision"]["session_id"], "b" * 32)
        self.assertNotIn("data", result["video_metadata"])
        self.assertNotIn("frame", result["video_metadata"])
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["hardware_writes"])


if __name__ == "__main__":
    unittest.main()
