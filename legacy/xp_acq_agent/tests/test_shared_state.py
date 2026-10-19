"""Synthetic transport/schema tests only; never real cards, PSP or Tango DB."""

import copy
import json
import socket
import struct
import threading
import unittest

from elyse_agent.protocol import recv_message
from elyse_agent.shared_state import (
    BANKS,
    LatestSnapshotOutbox,
    SharedStateStore,
    decode_snapshot_xml,
    expand_snapshot,
    validate_snapshot_packet,
)
from elyse_agent.shared_state_receiver import SharedStateServer


def fixture_xml(override=None):
    records = []
    for index, bank in enumerate(BANKS):
        name = "C10-11 NI6602" if bank == "C1011NI6602" else bank
        value = "<DBL><Name>fixture</Name><Val>{0}</Val></DBL>".format(index + 0.25)
        if override is not None and index == 0:
            value = override
        records.append(
            "<Cluster><Name></Name><NumElts>3</NumElts>"
            "<String><Name>bank</Name><Val>{0}</Val></String>"
            "<LvVariant><Name>value</Name>{1}</LvVariant>"
            "<Cluster><Name>error</Name><NumElts>3</NumElts>"
            "<Boolean><Name>status</Name><Val>0</Val></Boolean>"
            "<I32><Name>code</Name><Val>0</Val></I32>"
            "<String><Name>source</Name><Val></Val></String>"
            "</Cluster></Cluster>".format(name, value)
        )
    return (
        "<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>"
        + "".join(records)
        + "</Array></LvVariant>"
    ).encode("utf-8")


class SharedStateTests(unittest.TestCase):
    def test_explicit_native_ansi_preserves_french_names_and_string_values(self):
        value = (
            "<String><Name>Défaut refroidissement</Name>"
            "<Val>Arrêt général — état</Val></String>"
        )
        raw = fixture_xml(value).decode("utf-8").encode("cp1252")
        with self.assertRaises(ValueError):
            decode_snapshot_xml(raw)
        records = decode_snapshot_xml(raw, "cp1252")
        self.assertEqual(records[0]["data"], "Arrêt général — état")
        self.assertEqual(
            records[0]["lv_type"]["contained_type"]["name"], "Défaut refroidissement"
        )
        store = SharedStateStore("fixture", xml_encoding="cp1252")
        store.ingest(raw, "127.0.0.1")
        diagnostics = store.snapshot()["xml_diagnostics"]
        self.assertFalse(diagnostics["utf8_valid"])
        self.assertGreater(diagnostics["nonascii_bytes"], 0)
        self.assertEqual(diagnostics["bytes"], len(raw))
        with self.assertRaises(ValueError):
            decode_snapshot_xml(raw.replace(b"Arr", b"\x81rr"), "cp1252")
        with self.assertRaises(ValueError):
            SharedStateStore("fixture", xml_encoding="auto")

    def test_all_27_banks_alias_values_and_read_errors_preserved(self):
        records = decode_snapshot_xml(fixture_xml())
        self.assertEqual(tuple(r["publication"] for r in records), BANKS)
        self.assertEqual(records[0]["data"], 0.25)
        self.assertEqual(records[-1]["data"], 26.25)
        self.assertEqual(records[0]["lv_type"]["contained_type"]["type"], "DBL")
        self.assertFalse(records[0]["error"]["status"])
        store = SharedStateStore("fixture")
        self.assertTrue(store.ingest(fixture_xml(), "127.0.0.1")["accepted"])
        head = store.outbox.peek()
        expanded = expand_snapshot(head["packet"])
        self.assertEqual(set(expanded), set(BANKS))
        self.assertEqual(
            expanded["VAM-A"]["timestamp_origin"], "xp_receipt_not_card_sample"
        )

    def test_empty_array_prototype_is_not_an_actual_sample(self):
        xml = (
            "<Array><Name></Name><Dimsize>0</Dimsize>"
            "<DBL><Name></Name><Val>99</Val></DBL></Array>"
        )
        first = decode_snapshot_xml(fixture_xml(xml))[0]
        self.assertEqual(first["data"], [])
        self.assertEqual(first["lv_type"]["contained_type"]["dimensions"], [0])

    def test_nonfinite_and_signed_zero_are_not_fabricated_as_finite_zero(self):
        for text, expected in (
            ("NaN", {"nonfinite": "NaN"}),
            ("Inf", {"nonfinite": "+Inf"}),
            ("-Inf", {"nonfinite": "-Inf"}),
        ):
            xml = "<DBL><Name></Name><Val>{0}</Val></DBL>".format(text)
            self.assertEqual(decode_snapshot_xml(fixture_xml(xml))[0]["data"], expected)
        value = decode_snapshot_xml(
            fixture_xml("<DBL><Name></Name><Val>-0.0</Val></DBL>")
        )[0]["data"]
        self.assertEqual(json.dumps(value), "-0.0")

    def test_missing_duplicate_reordered_banks_and_dtd_fail_closed(self):
        xml = fixture_xml()
        for invalid in (
            xml.replace(b"Dimsize>27", b"Dimsize>26"),
            xml.replace(b"C2NI6071E", b"C1NI6071E"),
            b'<!DOCTYPE a [<!ENTITY x "bad">]>' + xml,
            xml.replace(b"<DBL>", b"<Refnum>").replace(b"</DBL>", b"</Refnum>"),
        ):
            with self.subTest(invalid=invalid[:80]):
                with self.assertRaises(ValueError):
                    decode_snapshot_xml(invalid)

    def test_whole_snapshot_validation_before_enqueue_and_remote_ingress_rejected(self):
        store = SharedStateStore("fixture")
        with self.assertRaises(ValueError):
            store.ingest(fixture_xml(), "10.20.30.202")
        self.assertEqual(store.outbox.status()["pending"], 0)
        store.ingest(fixture_xml(), "127.0.0.1")
        value = copy.deepcopy(store.outbox.peek()["packet"])
        value["data"]["banks"][1]["publication"] = BANKS[0]
        with self.assertRaises(ValueError):
            validate_snapshot_packet(value)

    def test_pending_replacements_keep_contiguous_ack_ids_and_one_retry_identity(self):
        box = LatestSnapshotOutbox()
        box.enqueue(json.dumps({"sequence": 0}), "fixture UTC")
        first = box.peek()
        for sequence in range(1, 1001):
            box.enqueue(json.dumps({"sequence": sequence}), "fixture UTC")
        self.assertEqual(box.status()["pending"], 2)
        self.assertEqual(box.status()["replaced_pending"], 999)
        self.assertEqual(box.peek()["packet"]["sequence"], 0)
        with self.assertRaises(ValueError):
            box.acknowledge("wrong", first["message_id"])
        box.acknowledge(first["relay_id"], first["message_id"])
        second = box.peek()
        self.assertEqual(second["message_id"], first["message_id"] + 1)
        self.assertEqual(second["packet"]["sequence"], 1000)
        box.acknowledge(second["relay_id"], second["message_id"])
        self.assertIsNone(box.peek())

    def test_tcp_xml_ingress_acknowledges_xp_ram_not_everest(self):
        store = SharedStateStore("fixture")
        server = SharedStateServer(("127.0.0.1", 0), store)
        thread = threading.Thread(
            target=server.serve_forever, kwargs=dict(poll_interval=0.01)
        )
        thread.start()
        try:
            with socket.create_connection(
                server.server_address, timeout=2
            ) as connection:
                raw = fixture_xml()
                connection.sendall(struct.pack("!I", len(raw)) + raw)
                reply = recv_message(connection, 262144)
                self.assertTrue(reply["ok"])
                self.assertEqual(reply["result"]["bank_count"], 27)
                self.assertEqual(
                    reply["result"]["acknowledged_on"], "xp_ram_not_everest"
                )
            self.assertEqual(store.outbox.status()["everest_acknowledged"], 0)
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()

    def test_oversize_or_json_instead_of_xml_is_rejected(self):
        for raw in (b"", b"x" * 262145, b'{"command":"write"}'):
            with self.assertRaises(ValueError):
                decode_snapshot_xml(raw)


if __name__ == "__main__":
    unittest.main()
