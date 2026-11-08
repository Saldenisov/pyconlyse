"""Original binary selectors agree with heap labels without closing defaults."""

import copy
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from validate_acq_dfds_recovery import (
    EXPECTED,
    MATCHES,
    ROOT_ARCHIVE,
    SLICES,
    check_tail_alignment,
    compare_converter,
    compare_heap,
    decode_table,
    raw_tables,
    read_recovered_source,
)
from validate_acq_modulator_start_event_guards import unique
from validate_acq_vam_status import checked_vam


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.xml = read_recovered_source(extra_type_ids=(3056, 3057))
        cls.tables = raw_tables(cls.payload)
        cls.root, _ = checked_vam(ROOT_ARCHIVE)
        # Mutation scope is selector metadata, not the already-proven case
        # bodies. Preserve every checked field and frame identity in a small
        # projection; the positive integration check still uses the full heap.
        cls.compact = ET.Element("SelectedCases")
        for matches in MATCHES.values():
            for uid, _, _ in matches:
                original = unique(cls.root, "select", uid)
                node = ET.SubElement(cls.compact, "Case", original.attrib)
                for tag in ("SelectRangeArray32", "SelectDefaultCase", "tdOffset"):
                    field = original.find(tag)
                    if field is not None:
                        node.append(copy.deepcopy(field))
                diagrams = ET.SubElement(node, "diagramList")
                for frame in original.findall("diagramList/*"):
                    ET.SubElement(diagrams, "Frame", frame.attrib)

    def test_five_independent_records_match_nine_cases_and64_frames(self):
        self.assertEqual(self.tables, EXPECTED)
        self.assertEqual(compare_heap(self.root, self.tables), (9, 64))
        compare_converter(self.xml, self.tables)

    def test_lazy_tail_block_is_not_misread_as_an_anomalous_case_table(self):
        check_tail_alignment(self.payload, self.xml)
        altered = copy.deepcopy(self.xml)
        altered.find("DataFill[@TypeID='3057']/Cluster")[1].text = "1"
        with self.assertRaises(AssertionError):
            check_tail_alignment(self.payload, altered)

    def test_repeated_block_values_and_population_match_original_bytes(self):
        for index in (0, 997, 1994):
            altered = copy.deepcopy(self.xml)
            row = altered.find("DataFill[@TypeID='3056']/RepeatedBlock")[index]
            row.text = str(int(row.text) + 1)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                check_tail_alignment(self.payload, altered)
        altered = copy.deepcopy(self.xml)
        row = altered.find("DataFill[@TypeID='3056']/RepeatedBlock")
        row.remove(row[-1])
        with self.assertRaises(AssertionError):
            check_tail_alignment(self.payload, altered)

    def test_changed_original_payload_rejected(self):
        for tid, (start, _, _) in SLICES.items():
            altered = bytearray(self.payload)
            altered[start] ^= 1
            with self.subTest(table=tid), self.assertRaises(AssertionError):
                raw_tables(bytes(altered))

    def test_table_extent_count_and_footer_are_strict(self):
        for start, stop, _ in SLICES.values():
            raw = self.payload[start:stop]
            for altered in (
                raw[:12],
                raw[:-1],
                raw + b"\x00",
                raw[:8] + bytes(4) + raw[12:],
                raw[:-1] + b"\x01",
            ):
                with (
                    self.subTest(start=start, bytes=len(altered)),
                    self.assertRaises(AssertionError),
                ):
                    decode_table(altered)

    def test_every_heap_range_field_is_required(self):
        fields = ("start", "end", "startRangeType", "endRangeType", "diagramIdx")
        for tid, matches in MATCHES.items():
            for uid, _, _ in matches:
                for index in range(len(self.tables[tid].rows)):
                    for field in fields:
                        altered = copy.deepcopy(self.compact)
                        elem = (
                            unique(altered, "select", uid)
                            .findall("SelectRangeArray32/*")[index]
                            .find(field)
                        )
                        elem.text = str(int(elem.text) + 1)
                        with (
                            self.subTest(case=uid, row=index, field=field),
                            self.assertRaises(AssertionError),
                        ):
                            compare_heap(altered, self.tables)

    def test_omitted_default_metadata_is_not_replaced_with_zero(self):
        for matches in MATCHES.values():
            for uid, _, default in matches:
                altered = copy.deepcopy(self.compact)
                node = unique(altered, "select", uid)
                elem = node.find("SelectDefaultCase")
                if default is None:
                    ET.SubElement(node, "SelectDefaultCase").text = "00"
                else:
                    node.remove(elem)
                with self.subTest(case=uid), self.assertRaises(AssertionError):
                    compare_heap(altered, self.tables)

    def test_frame_count_is_required_for_every_case(self):
        for matches in MATCHES.values():
            for uid, _, _ in matches:
                altered = copy.deepcopy(self.compact)
                diagrams = unique(altered, "select", uid).find("diagramList")
                diagrams.remove(diagrams[-1])
                with self.subTest(case=uid), self.assertRaises(AssertionError):
                    compare_heap(altered, self.tables)

    def test_every_exported_numeric_range_matches_independent_bytes(self):
        for tid in SLICES:
            rows = self.xml.findall(f"DataFill[@TypeID='{tid}']/Cluster/Array/Cluster")
            for index in range(len(rows)):
                altered = copy.deepcopy(self.xml)
                row = altered.findall(
                    f"DataFill[@TypeID='{tid}']/Cluster/Array/Cluster"
                )[index]
                row[0].text = str(int(row[0].text) + 1)
                with (
                    self.subTest(table=tid, row=index),
                    self.assertRaises(AssertionError),
                ):
                    compare_converter(altered, self.tables)


if __name__ == "__main__":
    unittest.main()
