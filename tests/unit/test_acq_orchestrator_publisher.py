"""Cold RAM-only owner publishing, without sockets or hardware; Python3.4."""
import copy
import json
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.orchestrator_publisher import OwnerTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.shared_state import LatestSnapshotOutbox, MAX_XML_BYTES
from legacy.xp_acq_control.elyse_agent.standard_banks import standard_packet
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from tests.unit import test_acq_fault_diagnostic as fixture


class Runtime(object):
    def __init__(self):
        self._identity = dict(session_id="a" * 32, build_id="b" * 64)
        self._lock = threading.RLock()
        self.value = dict(self._identity, state="FAULT", sequence=1, state_revision=1,
            latest=None, age_seconds=None, resource_count=21, stale=True,
            error="Another card failed", telemetry_view_current=True)

    def snapshot(self):
        return copy.deepcopy(self.value)


class OwnerPublisherTests(unittest.TestCase):
    def test_transform_never_calls_back_into_runtime_while_publication_lock_is_owned(self):
        runtime = Runtime()
        def forbidden():
            self.fail("Publisher transform attempted a runtime callback under its lock")
        runtime.counter_memory_part = runtime.video_frame_snapshot = forbidden
        memory = dict(values=[1., 2.] * 8, source_age_seconds=.1,
            source="last_successful_counter_command_memory", selector=-1, pending_selector=False)
        projection = dict(runtime.value, _publisher_counter_part=memory)
        publisher = OwnerTelemetryPublisher(runtime, ("127.0.0.1", 12345), b"x" * 32)
        with publisher.lock:
            frame = json.loads(publisher._transform(standard_packet(projection, 1), 0, projection))
        self.assertEqual(frame["counter_part"], memory)
        projection["telemetry_view_current"] = False
        with publisher.lock:
            expired = json.loads(publisher._transform(standard_packet(projection, 2), 0, projection))
        self.assertIsNone(expired["counter_part"])

    def test_counter_memory_is_hidden_until_timing_write_is_complete(self):
        class Backend(object):
            startup_complete = True
            _counter_config_generation = "c" * 32
            commanded_counter_ticks = dict((i, dict(low_ticks=20, high_ticks=40)) for i in range(8))
            card_processes = dict(cards={"10": dict(state="READY", input_current=True,
                sample_age_seconds=.1, unresolved_request=False,
                native=dict(ownership_uncertain=False, worker_generation="c" * 32))})
        runtime = AcquisitionControlRuntime.__new__(AcquisitionControlRuntime)
        runtime._lock, runtime._backend = threading.RLock(), Backend()
        runtime._pending, runtime._operation, runtime._shutdown_requested = None, None, False
        self.assertEqual(runtime.counter_memory_part()["values"], [1., 2.] * 8)
        runtime._pending = "counter_timing"
        self.assertIsNone(runtime.counter_memory_part())
        runtime._pending, runtime._operation = None, "acq.stage.counter_timing.set"
        self.assertIsNone(runtime.counter_memory_part())
        runtime._operation = None
        self.assertEqual(runtime.counter_memory_part()["values"], [1., 2.] * 8)
        runtime._shutdown_requested = True
        self.assertIsNone(runtime.counter_memory_part())

    def test_fresh_card_survives_unrelated_fault_without_fake_output_or_foreign_bank(self):
        runtime = Runtime()
        card = dict(state="READY", input_current=True, unresolved_request=False,
            sample_age_seconds=.4, sample_sequence=4,
            native=dict(ownership_uncertain=False, worker_generation="c" * 32),
            sample=dict(device=3, banks=dict(C3_DIO96_DI=dict(device=3, kind="digital_input", values=[True]*56))))
        runtime.value["card_processes"] = dict(transport_age_seconds=.1, cards={"3": card})
        publisher = OwnerTelemetryPublisher(runtime, ("127.0.0.1", 12345), b"x" * 32)
        packet = standard_packet(runtime.value, 1)
        frame = json.loads(publisher._transform(packet, 0, runtime.value))
        records = {row["publication"]: row for row in frame["banks"]}
        self.assertEqual(records["C3_IN_DIO96"]["data"], [True]*56)
        self.assertAlmostEqual(records["C3_IN_DIO96"]["source_age_seconds"], .5)
        self.assertIsNone(records["C3_OUT_DIO96"]["data"])
        self.assertNotIn("C12NI1409", records)
        self.assertFalse(publisher.worker)

    def test_expired_card_and_transport_do_not_receive_new_freshness_window(self):
        runtime = Runtime()
        runtime.value["card_processes"] = dict(transport_age_seconds=.02, cards={"3": dict(
            state="READY", input_current=True, unresolved_request=False, sample_age_seconds=1.99,
            native=dict(ownership_uncertain=False), sample=dict(device=3, banks=dict(
                C3_DIO96_DI=dict(device=3,kind="digital_input",values=[False]*56))))})
        publisher = OwnerTelemetryPublisher(runtime, ("127.0.0.1",12345), b"x"*32)
        records=json.loads(publisher._transform(standard_packet(runtime.value,1),0,runtime.value))["banks"]
        self.assertTrue(all(row["data"] is None for row in records))

    def test_owner_outbox_limit_does_not_enlarge_legacy_xml_limit(self):
        legacy, owner = LatestSnapshotOutbox(), LatestSnapshotOutbox(max_encoded_bytes=900*1024)
        encoded = json.dumps(dict(value="x"*(MAX_XML_BYTES+100)))
        self.assertRaises(ValueError, legacy.enqueue, encoded, "now")
        owner.enqueue(encoded,"now")
        first = owner.peek()
        owner.enqueue(json.dumps(dict(value="new")), "later")
        retry = owner.peek()
        self.assertEqual(retry["packet"], first["packet"])
        self.assertEqual(retry["message_id"], first["message_id"])
        self.assertGreaterEqual(retry["age_seconds_on_xp"], first["age_seconds_on_xp"])
        owner.acknowledge(first["relay_id"],first["message_id"])
        self.assertEqual(owner.peek()["packet"]["value"],"new")


if __name__ == "__main__":
    unittest.main()
