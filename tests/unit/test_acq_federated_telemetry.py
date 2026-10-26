"""Everest store in RAM only; XP codec is tested separately on Python 3.4."""
import copy
import datetime
import unittest

from legacy.xp_acq_control.elyse_agent.federation_wire import (
    owner_frame, validate_owner_frame, OWNED_BANKS, expand_owner_frame,
)
from legacy.xp_acq_control.elyse_agent.standard_banks import schemas
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import sign
from DeviceServers.control.elyse_acq.federated_telemetry import FederatedTelemetryStore
from DeviceServers.control.elyse_acq.telemetry_archive import ingress_record


KEYS = dict(acquisition=b"acquisition-test-only-key-000000000000000000",
            supervision=b"supervision-test-only-key-000000000000000000")


def record(name, data, age=0.):
    return dict(publication=name, data=data, lv_type=copy.deepcopy(schemas()[name]),
                error=dict(status=False, code=0, source=""), source_age_seconds=age)


def part(value=1., age=0., pending=False, selector=-1.):
    return dict(values=[value] * 16, source_age_seconds=age,
                source="last_successful_counter_command_memory", selector=selector,
                pending_selector=pending)


def frame(role, session=None, sequence=1, age=0., counter=None):
    name = "C1NI6071E" if role == "acquisition" else "C12NI1409"
    data = [20.] * 64 if role == "acquisition" else "img0"
    return owner_frame(role, session or ("a" if role == "acquisition" else "b") * 32,
                       sequence, {name: record(name, data, age)}, "PYTHON_NATIVE", counter)


def body(packet, relay=None, message=1, age=0.):
    return dict(schema_version=1, relay_id=relay or ("c" if packet["owner"] == "acquisition" else "d") * 32,
        message_id=message, received_utc_on_xp="2026-10-26T12:00:00+00:00",
        age_seconds_on_xp=age, packet=packet, hardware_writes=False)


def request(value, key=None):
    signed = dict(body=value, nonce="e" * 32)
    return dict(signed, signature=sign(key or KEYS[value["packet"]["owner"]],
                                    "ACQ-TELEMETRY-REQUEST-1", signed))


class FederatedStoreTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.store = FederatedTelemetryStore(KEYS, clock=lambda: self.now)

    def tearDown(self):
        self.store.close()

    def test_both_start_orders_preserve_two_disjoint_owners(self):
        for order in (("acquisition", "supervision"), ("supervision", "acquisition")):
            sink = FederatedTelemetryStore(KEYS)
            for role in order:
                sink.accept(request(body(frame(role))))
            value = sink.snapshot()
            self.assertEqual(set(value["publications"]), set(BANKS))
            self.assertEqual(value["publications"]["C1NI6071E"]["data"], [20.] * 64)
            self.assertEqual(value["publications"]["C12NI1409"]["data"], "img0")
            self.assertFalse(value["atomic_across_publications"])
            self.assertEqual(value["unavailable_owners"], [])
            sink.close()

    def test_missing_peer_is_explicit_null_not_synthetic_zero(self):
        self.store.accept(request(body(frame("acquisition"))))
        value = self.store.snapshot()
        missing = value["publications"]["C12NI1409"]
        self.assertIsNone(missing["data"])
        self.assertTrue(missing["error"]["status"])
        self.assertEqual(value["unavailable_owners"], ["supervision"])
        self.assertTrue(value["publications"]["DPC"]["error"]["status"])

    def test_distinct_owner_keys_required_and_role_forgery_rejected(self):
        self.assertRaises(ValueError, FederatedTelemetryStore, dict(acquisition=KEYS["acquisition"], supervision=KEYS["acquisition"]))
        value = body(frame("acquisition"))
        self.assertRaises(ValueError, self.store.accept, request(value, KEYS["supervision"]))
        self.assertEqual(self.store.snapshot()["received_this_process"], 0)

    def test_foreign_bank_rejected_even_if_unavailable(self):
        self.assertRaises(ValueError, owner_frame, "acquisition", "a" * 32, 1,
                          {"C12NI1409": record("C12NI1409", "camera")}, "PYTHON_NATIVE")
        value = frame("supervision")
        value["banks"][0] = record("C1NI6071E", [1.] * 64)
        self.assertRaises(ValueError, self.store.accept, request(body(value)))

    def test_restart_of_one_owner_never_retires_other(self):
        self.store.accept(request(body(frame("acquisition"))))
        self.store.accept(request(body(frame("supervision"))))
        self.store.accept(request(body(frame("acquisition", "f" * 32), relay="1" * 32)))
        value = self.store.snapshot()
        self.assertEqual(value["owners"]["supervision"]["session_id"], "b" * 32)
        self.assertEqual(value["publications"]["C12NI1409"]["data"], "img0")
        self.assertRaises(ValueError, self.store.accept, request(body(frame("acquisition", sequence=2), message=2)))
        self.store.accept(request(body(frame("supervision", sequence=2), message=2)))

    def test_healthy_peer_does_not_refresh_stale_card_or_counter_part(self):
        self.store.accept(request(body(frame("acquisition", counter=part()))))
        self.store.accept(request(body(frame("supervision", counter=part()))))
        self.now = 2.1
        self.store.accept(request(body(frame("supervision", sequence=2, counter=part()), message=2)))
        value = self.store.snapshot()
        self.assertTrue(value["publications"]["C1NI6071E"]["stale"])
        self.assertFalse(value["publications"]["C12NI1409"]["stale"])
        self.assertIsNone(value["publications"]["C1011NI6602"]["data"])

    def test_per_bank_source_age_plus_queue_and_receiver_age(self):
        self.store.accept(request(body(frame("acquisition", age=.8), age=.5)))
        self.now = .8
        value = self.store.snapshot()["publications"]["C1NI6071E"]
        self.assertAlmostEqual(value["age_seconds"], 2.1)
        self.assertTrue(value["stale"])

    def test_immutable_retry_acks_without_refreshing_source_time(self):
        first = body(frame("acquisition"))
        self.store.accept(request(first))
        self.now = 1.
        retry = copy.deepcopy(first)
        retry["age_seconds_on_xp"] = 1.
        ack = self.store.accept(request(retry))
        self.assertTrue(ack["body"]["duplicate"])
        self.assertEqual(self.store.snapshot()["received_this_process"], 1)
        self.assertEqual(self.store.snapshot()["publications"]["C1NI6071E"]["age_seconds"], 1.)
        retry["packet"]["banks"][0]["data"][0] = 99.
        self.assertRaises(ValueError, self.store.accept, request(retry))

    def test_same_boot_cannot_switch_relay_or_regress_sequence(self):
        self.store.accept(request(body(frame("acquisition"))))
        self.assertRaises(ValueError, self.store.accept, request(body(frame("acquisition", sequence=2), relay="2" * 32)))
        self.assertRaises(ValueError, self.store.accept, request(body(frame("acquisition"), message=2)))
        self.assertRaises(ValueError, self.store.accept, request(body(frame("acquisition", sequence=2), message=3)))

    def test_counter_bank_requires_both_explicit_idle_memories(self):
        self.store.accept(request(body(frame("acquisition", counter=part(1.)))))
        self.store.accept(request(body(frame("supervision", counter=part(2.)))))
        value = self.store.snapshot()["publications"]["C1011NI6602"]
        self.assertEqual(value["data"], [1.] * 16 + [2.] * 16 + [-1.])
        self.assertFalse(value["hardware_acknowledged"])
        self.assertFalse(value["atomic_across_owners"])
        self.store.accept(request(body(frame("supervision", sequence=2, counter=part(2., pending=True, selector=17.)), message=2)))
        self.assertIsNone(self.store.snapshot()["publications"]["C1011NI6602"]["data"])

    def test_no_pending_flag_without_minus_one_is_not_an_ack(self):
        self.assertRaises(ValueError, frame, "acquisition", counter=part(pending=False, selector=0.))
        self.assertRaises(ValueError, frame, "acquisition", counter=part(age=float("inf")))

    def test_camera_uses_pinned_opaque_string_contract_and_bounded_size(self):
        for data in ([1, 2, 3], "x" * 4097):
            self.assertRaises(ValueError, owner_frame, "supervision", "a" * 32, 1,
                              {"C12NI1409": record("C12NI1409", data)}, "PYTHON_NATIVE")
        value = frame("supervision")
        value["banks"][0]["lv_type"]["contained_type"]["type"] = "Array"
        self.assertRaises(ValueError, validate_owner_frame, value)

    def test_empty_heartbeat_does_not_claim_owner_data_available(self):
        value = owner_frame("acquisition", "a" * 32, 1, source_mode="PYTHON_NATIVE")
        self.store.accept(request(body(value)))
        snapshot = self.store.snapshot()
        self.assertFalse(snapshot["owners"]["acquisition"]["source_current"])
        self.assertTrue(all(bank["data"] is None for bank in snapshot["publications"].values()))

    def test_archive_keeps_owner_provenance_and_does_not_invent_peer_banks(self):
        value = body(frame("supervision", age=.5), age=.25)
        record = ingress_record(value, "a" * 32, 1, "2026-10-26T12:00:00+00:00")
        self.assertEqual(set(record["snapshot"]["publications"]), {"C12NI1409"})
        bank = record["snapshot"]["publications"]["C12NI1409"]
        self.assertEqual(bank["owner"], "supervision")
        self.assertEqual(bank["age_seconds"], .75)
        self.assertEqual(record["wire_body"], value)

    def test_closed_store_refuses_any_new_signed_frame(self):
        self.store.close()
        self.assertRaises(RuntimeError, self.store.accept, request(body(frame("acquisition"))))

    def test_unavailable_new_boot_cannot_retire_current_owner(self):
        self.store.accept(request(body(frame("acquisition"))))
        candidate = owner_frame("acquisition", "f" * 32, 1)
        self.store.accept(request(body(candidate, relay="1" * 32)))
        value = self.store.snapshot()
        self.assertEqual(value["owners"]["acquisition"]["session_id"], "a" * 32)
        self.assertTrue(value["owners"]["acquisition"]["candidate_requires_current_data"])
        self.assertEqual(value["publications"]["C1NI6071E"]["data"], [20.] * 64)
        self.store.accept(request(body(frame("acquisition", sequence=2), message=2)))
        self.store.accept(request(body(frame("acquisition", "f" * 32, sequence=2), relay="1" * 32, message=2)))
        self.assertEqual(self.store.snapshot()["owners"]["acquisition"]["session_id"], "f" * 32)
        self.assertRaises(ValueError, self.store.accept, request(body(frame("acquisition", sequence=3), message=3)))

    def test_stale_first_frame_is_only_candidate_and_cannot_claim_source_current(self):
        self.store.accept(request(body(frame("acquisition"))))
        self.store.accept(request(body(frame("acquisition", "f" * 32, age=3.), relay="1" * 32)))
        self.assertEqual(self.store.snapshot()["owners"]["acquisition"]["session_id"], "a" * 32)
        self.now = 3.
        self.assertFalse(self.store.owner_current("acquisition"))
        self.assertEqual(self.store.snapshot()["publications"]["C1NI6071E"]["session_id"], "a" * 32)

    def test_unavailable_owner_heartbeat_does_not_refresh_prior_bank(self):
        self.store.accept(request(body(frame("acquisition"))))
        self.now = .5
        unavailable = owner_frame("acquisition", "a" * 32, 2)
        self.store.accept(request(body(unavailable, message=2)))
        self.assertFalse(self.store.owner_current("acquisition"))
        self.assertIsNone(self.store.snapshot()["publications"]["C1NI6071E"]["data"])

    def test_archive_receipt_identity_is_namespaced_by_authenticated_owner(self):
        acq = body(frame("acquisition"), relay="c" * 32)
        sup = body(frame("supervision"), relay="c" * 32)
        self.store.accept(request(acq))
        self.store.accept(request(sup))
        acq_row = ingress_record(acq, "a" * 32, 1, "2026-10-26T12:00:00+00:00")
        sup_row = ingress_record(sup, "a" * 32, 2, "2026-10-26T12:00:00+00:00")
        self.assertNotEqual(acq_row["uid"], sup_row["uid"])
        self.assertEqual(self.store.snapshot()["received_this_process"], 2)

    def test_archive_failure_does_not_ack_or_replace_current_frame(self):
        self.store.accept(request(body(frame("acquisition"))))
        class BrokenArchive(object):
            def append_ingress(self, *args):
                raise OSError("fixture durable spool unavailable")
            def status(self):
                return dict(state="SPOOL_ERROR")
        self.store.archive = BrokenArchive()
        self.assertRaises(OSError, self.store.accept,
            request(body(frame("acquisition", "f" * 32), relay="1" * 32)))
        self.assertEqual(self.store.snapshot()["owners"]["acquisition"]["session_id"], "a" * 32)
        self.assertEqual(self.store.snapshot()["received_this_process"], 1)


if __name__ == "__main__":
    unittest.main()
