"""Passive single-counter XML profile. RAM only; Python3.4 compatible."""

import unittest
import xml.etree.ElementTree as ET

from legacy.xp_acq_agent.elyse_agent.shared_state import (
    decode_snapshot_xml as decode_acquisition_xml,
)
from legacy.xp_acq_control.elyse_agent.shared_state import (
    decode_snapshot_xml,
    decode_supervision_snapshot_xml,
)

from tests.unit import test_supervision_vi_telemetry as fixture

part, xml = fixture.part, fixture.xml


def counter_xml(
    bank="C10-11 NI6602",
    error=False,
    field_type=None,
    duplicate=False,
    empty_variant=False,
):
    root = ET.fromstring(xml())
    array = root.find("Array")
    counter = next(
        row
        for row in array.findall("Cluster")
        if row.findtext("String/Val") == "C1011NI6602"
    )
    for row in list(array.findall("Cluster")):
        array.remove(row)
    counter.find("String/Val").text = bank
    if error:
        cluster = counter.find("Cluster")
        cluster.find("Boolean/Val").text = "1"
        cluster.find("I32/Val").text = "-200000"
        cluster.find("String/Val").text = "control read failed"
    if field_type:
        counter.find("LvVariant/Cluster/DBL").tag = field_type
    if empty_variant:
        variant = counter.find("LvVariant")
        for child in list(variant):
            if child.tag != "Name":
                variant.remove(child)
    array.append(counter)
    if duplicate:
        array.append(ET.fromstring(ET.tostring(counter, encoding="utf-8")))
    array.find("Dimsize").text = "2" if duplicate else "1"
    return ET.tostring(root, encoding="utf-8")


class CounterProfileDecoderTests(unittest.TestCase):
    def test_preserves_exact33_dbl_and_alias_for_supervision_only(self):
        (record,) = decode_supervision_snapshot_xml(counter_xml())
        self.assertEqual(record["publication"], "C1011NI6602")
        self.assertEqual(len(record["data"]), 33)
        self.assertEqual(record["data"][16:32], part()["values"])
        self.assertEqual(record["data"][32], -1.0)
        self.assertEqual(
            [f["type"] for f in record["lv_type"]["contained_type"]["fields"]],
            ["DBL"] * 33,
        )

    def test_both_acquisition_decoders_keep_exact27_bank_contract(self):
        for decoder in (decode_snapshot_xml, decode_acquisition_xml):
            with self.assertRaises(ValueError):
                decoder(counter_xml())
            self.assertEqual(len(decoder(xml())), 27)

    def test_supervision_retains_existing27_profile_without_using_it_in_new_helper(
        self,
    ):
        self.assertEqual(len(decode_supervision_snapshot_xml(xml())), 27)

    def test_other_single_banks_duplicates_or_wrong_dbl_shape_fail_closed(self):
        for raw in (
            counter_xml(bank="C1NI6071E"),
            counter_xml(duplicate=True),
            counter_xml(field_type="I32"),
            counter_xml(empty_variant=True),
        ):
            with self.assertRaises(ValueError):
                decode_supervision_snapshot_xml(raw)

    def test_single_bank_keeps_xml_encoding_dtd_and_size_guards(self):
        for raw in (
            b"<!DOCTYPE x>" + counter_xml(),
            counter_xml() + b"\x00",
            b"x" * (262144 + 1),
        ):
            with self.assertRaises(ValueError):
                decode_supervision_snapshot_xml(raw, "cp1252")


class CounterOnlyPublisherTests(unittest.TestCase):
    setUp = fixture.SupervisionVITests.setUp
    tearDown = fixture.SupervisionVITests.tearDown
    take = fixture.SupervisionVITests.take

    def test_single_bank_publishes_local16_values_without_starting_cards(self):
        receipt = self.publisher.ingest(counter_xml(), "127.0.0.1")
        self.assertEqual(receipt["bank_count"], 1)
        self.assertFalse(receipt["hardware_writes"])
        packet = self.take()["packet"]
        self.assertEqual(packet["counter_part"]["values"], part()["values"])
        self.assertEqual(
            packet["counter_part"]["source"], "observed_labview_control_memory"
        )
        self.assertEqual(packet["session_id"], self.runtime._identity["session_id"])
        self.assertIsNone(packet["video_frame"])
        self.assertEqual(self.runtime._owners, {})
        self.assertIsNone(self.runtime._thread)

    def test_control_read_error_invalidates_prior_counter_without_fabricating_ack(self):
        self.publisher.ingest(counter_xml(), "127.0.0.1")
        self.take()
        self.now = 0.5
        self.publisher.ingest(counter_xml(error=True, empty_variant=True), "127.0.0.1")
        packet = self.take()["packet"]
        self.assertIsNone(packet["counter_part"])
        self.assertIsNone(self.publisher._vi_counter)
        self.assertEqual(self.runtime._owners, {})


if __name__ == "__main__":
    unittest.main()
