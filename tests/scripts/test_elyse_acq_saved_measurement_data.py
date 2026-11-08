"""Independent saved-byte checks and mutation tests for seven controls."""

import copy
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from validate_acq_modulator_start_event_guards import unique
from validate_acq_saved_measurement_data import (
    CONTROLS,
    compare_control_identities,
    compare_source_data,
    read_source_data,
)
from validate_acq_stop_ui_bindings import checked_trees


class SavedMeasurementSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.data = read_source_data()
        cls.bd, cls.fp, cls.metadata = checked_trees()
        cls.compact_fp = ET.Element("Controls")
        for spec in CONTROLS.values():
            cls.compact_fp.append(copy.deepcopy(unique(cls.fp, "fPDCO", spec.control)))
        cls.compact_bd = ET.Element("Diagrams")
        parents = {child: parent for parent in cls.bd.iter() for child in parent}
        diagrams = {}
        for node in cls.bd.findall(".//*[@class='gRef']"):
            if node.findtext("termList/*/dco/paramIdx") not in {
                str(b) for b in CONTROLS
            }:
                continue
            owner = parents[node]
            while owner.get("class") != "diag":
                owner = parents[owner]
            uid = owner.get("uid")
            if uid not in diagrams:
                diagrams[uid] = ET.SubElement(
                    cls.compact_bd, "Diagram", {"class": "diag", "uid": uid}
                )
            diagrams[uid].append(copy.deepcopy(node))

    def test_original_source_has_four_empty_arrays_and_three_zero_scalars(self):
        self.assertEqual(
            compare_source_data(self.payload, self.data),
            {59: (), 62: 0, 63: 0, 65: (), 66: (), 67: (), 68: 0},
        )
        compare_control_identities(self.bd, self.fp, self.metadata)

    def test_each_of_26_independently_decoded_bytes_is_required(self):
        for bank, spec in CONTROLS.items():
            for offset in range(
                spec.offset, spec.offset + struct.calcsize(spec.format)
            ):
                payload = bytearray(self.payload)
                payload[offset] = 1
                with (
                    self.subTest(bank=bank, offset=offset),
                    self.assertRaises(AssertionError),
                ):
                    compare_source_data(bytes(payload), self.data)

    def test_all_typed_metadata_and_measured_record_intervals_are_required(self):
        for bank, record in self.data["controls"].items():
            for field, value in record.items():
                data = copy.deepcopy(self.data)
                data["controls"][bank][field] = (
                    value + 1 if type(value) is int else "wrong"
                )
                with (
                    self.subTest(bank=bank, field=field),
                    self.assertRaises(AssertionError),
                ):
                    compare_source_data(self.payload, data)

    def test_empty_dimension_cannot_be_misreported_as_four_zero_elements(self):
        for bank in (59, 65, 66, 67):
            data = copy.deepcopy(self.data)
            data["controls"][bank]["dimensions"] = (4,)
            data["controls"][bank]["value"] = (0.0,) * 4
            with self.subTest(bank=bank), self.assertRaises(AssertionError):
                compare_source_data(self.payload, data)

    def test_dco_data_link_cannot_be_replaced_by_default_data_tmi(self):
        for bank, spec in CONTROLS.items():
            data = copy.deepcopy(self.data)
            rows = list(data["dcos"])
            row = list(rows[bank])
            row[7], row[8] = -1, spec.type_id - 25
            rows[bank] = tuple(row)
            data["dcos"] = tuple(rows)
            with self.subTest(bank=bank), self.assertRaises(AssertionError):
                compare_source_data(self.payload, data)

    def test_dbl_element_and_exact_control_population_are_required(self):
        for field in ("element_descriptor", "element_type"):
            data = copy.deepcopy(self.data)
            data[field] = "wrong"
            with self.subTest(field=field), self.assertRaises(AssertionError):
                compare_source_data(self.payload, data)
        data = copy.deepcopy(self.data)
        del data["controls"][65]
        with self.assertRaises(AssertionError):
            compare_source_data(self.payload, data)

    def test_front_panel_identity_widget_type_and_label_are_required(self):
        for bank, spec in CONTROLS.items():
            for field in ("typeDesc", "ddo", "widget", "label"):
                fp = copy.deepcopy(self.compact_fp)
                node = unique(fp, "fPDCO", spec.control)
                if field == "typeDesc":
                    node.find(field).text = "TypeID(11)"
                elif field == "ddo":
                    node.find(field).set("uid", "wrong")
                elif field == "widget":
                    node.find("ddo").set("class", "wrong")
                else:
                    node.find(
                        "ddo/partsList/*[@class='label']/textRec/text"
                    ).text = '"wrong"'
                with (
                    self.subTest(bank=bank, field=field),
                    self.assertRaises(AssertionError),
                ):
                    compare_control_identities(self.compact_bd, fp, self.metadata)

    def test_all_21_local_indices_flags_and_owner_diagrams_are_required(self):
        for local in self.compact_bd.findall(".//*[@class='gRef']"):
            for field in ("paramIdx", "objFlags", "owner"):
                bd = copy.deepcopy(self.compact_bd)
                node = unique(bd, "gRef", local.get("uid"))
                if field == "owner":
                    owner = next(p for p in bd for child in p if child is node)
                    owner.remove(node)
                    ET.SubElement(
                        bd, "Diagram", {"class": "diag", "uid": "wrong"}
                    ).append(node)
                else:
                    dco = node.find("termList/*/dco")
                    elem = dco.find(field)
                    if elem is None:
                        elem = ET.SubElement(dco, field)
                    elem.text = "999"
                with (
                    self.subTest(local=local.get("uid"), field=field),
                    self.assertRaises(AssertionError),
                ):
                    compare_control_identities(bd, self.compact_fp, self.metadata)

    def test_capture_writer_cannot_be_relocated_into_initialization(self):
        bd = copy.deepcopy(self.compact_bd)
        writer = unique(bd, "gRef", "101607")
        owner = next(p for p in bd for child in p if child is writer)
        owner.remove(writer)
        ET.SubElement(bd, "Diagram", {"class": "diag", "uid": "227"}).append(writer)
        with self.assertRaises(AssertionError):
            compare_control_identities(bd, self.compact_fp, self.metadata)


if __name__ == "__main__":
    unittest.main()
