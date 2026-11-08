"""Independent original DCO and persisted-stop byte checks, not live reads."""

import copy
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from validate_acq_modulator_start_event_guards import unique
from validate_acq_saved_stop_data import (
    STOP_DATA,
    compare_control_identities,
    compare_source_data,
    read_source_data,
)
from validate_acq_stop_ui_bindings import checked_trees


class SavedStopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.data = read_source_data()
        cls.bd, cls.fp, cls.metadata = checked_trees()
        # Only the identities checked by this proof belong to mutation scope.
        # Positive checks below still use the entire original BD/FP trees.
        cls.compact_fp = ET.Element("Controls")
        for _, _, uid, _, _, _ in STOP_DATA.values():
            cls.compact_fp.append(copy.deepcopy(unique(cls.fp, "fPDCO", uid)))
        cls.compact_bd = ET.Element("Locals")
        for local in cls.bd.findall(".//*[@class='gRef']"):
            terminal = local.find("termList/*/dco")
            if terminal is not None and terminal.findtext("paramIdx") in {
                str(bank) for bank in STOP_DATA
            }:
                cls.compact_bd.append(copy.deepcopy(local))

    def test_original_69_dcos_and_four_stored_false_values(self):
        self.assertEqual(
            compare_source_data(self.payload, self.data),
            {30: False, 45: False, 46: False, 47: False},
        )
        compare_control_identities(self.bd, self.fp, self.metadata)

    def test_every_one_of_2208_dco_fields_matches_independent_bytes(self):
        for index, row in enumerate(self.data["dcos"]):
            for field, value in enumerate(row):
                changed = dict(self.data)
                rows = list(changed["dcos"])
                cells = list(row)
                cells[field] = value + 1 if isinstance(value, int) else b"wrong"
                rows[index] = tuple(cells)
                changed["dcos"] = tuple(rows)
                with (
                    self.subTest(row=index, field=field),
                    self.assertRaises(AssertionError),
                ):
                    compare_source_data(self.payload, changed)

    def test_all_51_dsinit_values_match_original_bytes(self):
        for index, value in enumerate(self.data["dsinit"]):
            changed = dict(self.data)
            values = list(changed["dsinit"])
            values[index] = value + 1
            changed["dsinit"] = tuple(values)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                compare_source_data(self.payload, changed)

    def test_each_stored_stop_byte_is_required(self):
        for bank, (_, offset, _, _, _, _) in STOP_DATA.items():
            changed = bytearray(self.payload)
            changed[offset] = 1
            with self.subTest(bank=bank), self.assertRaises(AssertionError):
                compare_source_data(bytes(changed), self.data)

    def test_each_stored_stop_typed_field_is_required(self):
        for bank, row in self.data["stops"].items():
            for field, value in row.items():
                changed = dict(self.data)
                changed["stops"] = {
                    key: dict(item) for key, item in self.data["stops"].items()
                }
                changed["stops"][bank][field] = (
                    value + 1 if isinstance(value, int) else b"wrong"
                )
                with (
                    self.subTest(bank=bank, field=field),
                    self.assertRaises(AssertionError),
                ):
                    compare_source_data(self.payload, changed)

    def test_front_panel_types_and_ddo_links_are_required(self):
        for _, _, uid, _, _, _ in STOP_DATA.values():
            for field in ("typeDesc", "ddo"):
                changed = copy.deepcopy(self.compact_fp)
                node = unique(changed, "fPDCO", uid)
                if field == "typeDesc":
                    node.find(field).text = "TypeID(11)"
                else:
                    node.find(field).set("uid", "wrong")
                with (
                    self.subTest(control=uid, field=field),
                    self.assertRaises(AssertionError),
                ):
                    compare_control_identities(self.compact_bd, changed, self.metadata)

    def test_each_stop_local_bank_is_required(self):
        for index, local in enumerate(self.compact_bd):
            changed = copy.deepcopy(self.compact_bd)
            changed[index].find("termList/*/dco/paramIdx").text = "999"
            with (
                self.subTest(local=local.get("uid")),
                self.assertRaises(AssertionError),
            ):
                compare_control_identities(changed, self.compact_fp, self.metadata)


if __name__ == "__main__":
    unittest.main()
