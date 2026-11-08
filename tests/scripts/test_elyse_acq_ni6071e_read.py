"""AI source-wire/calibration correspondence and source-mutation rejection."""

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.read_ni6071e import (
    C1_OFFSETS,
    C1_SLOPES,
    C2_OFFSETS,
    C2_SLOPES,
    SOURCE,
)
from validate_acq_ni6071e_read import (
    WIRES,
    checked_root,
    checked_roots,
    decoded_calibration,
    unique,
    validate_io_callers,
    validate_read,
)


class AnalogReadSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exports = REPOSITORY / "legacy/xp_acq_agent/data/source_exports"
        cls.original = checked_roots(
            exports / "ACQ_17_original_members_XML_20261001.zip"
        )
        cls.acq = checked_root(exports / "0_ACQ_ELYSE_XML_sha6fe8.zip")

    def test_original_and_callers_pass(self):
        self.assertIn("independent C1/C2", validate_read(self.original))
        self.assertIn("requested 1000", validate_io_callers(self.acq))

    def test_python_source_hash_and_all_calibration_values_match(self):
        census = json.loads(
            (
                REPOSITORY / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json"
            ).read_text()
        )
        member = next(m for m in census["members"] if m["vi"] == SOURCE.name)
        self.assertEqual(SOURCE.sha256, member["source_vi_sha256"])
        self.assertEqual(
            decoded_calibration(self.original),
            ((C1_SLOPES, C1_OFFSETS), (C2_SLOPES, C2_OFFSETS)),
        )

    def test_all_five_diagram_net_sets_checked(self):
        for uid, wires in WIRES.items():
            for wire in wires:
                roots = deepcopy(self.original)
                unique(roots["vi_BDHb.xml"], "diag", uid).find(
                    f"signalList/*/termList/*[@uid='{wire[0]}']"
                ).set("uid", "999999")
                with self.assertRaisesRegex(AssertionError, "wire set"):
                    validate_read(roots)

    def test_each_calibration_array_mutation_is_rejected(self):
        for uid in ("756", "804", "1023", "1089"):
            roots = deepcopy(self.original)
            literal = unique(roots["vi_BDHb.xml"], "diag", "875").find(
                f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue"
            )
            literal.text = literal.text[:8] + "3FF0000000000000" + literal.text[24:]
            with self.assertRaisesRegex(AssertionError, "coefficient array changed"):
                validate_read(roots)

    def test_auto_indexed_mean_bound_cannot_become_sample_count(self):
        roots = deepcopy(self.original)
        unique(roots["vi_BDHb.xml"], "forLoop", "510").find(
            "termList/*[@uid='531']/dco/TunnelType"
        ).text = "00"
        with self.assertRaisesRegex(AssertionError, "auto-index tunnel"):
            validate_read(roots)

    def test_saved_calibration_true_literal_checked(self):
        roots = deepcopy(self.original)
        unique(roots["vi_BDHb.xml"], "diag", "3").find(
            "nodeList/*/termList/*[@uid='1160']/dco/ConstValue"
        ).text = "00"
        with self.assertRaisesRegex(AssertionError, "calibration literal"):
            validate_read(roots)

    def test_raw_case_mapping_and_merge_error_input_order_checked(self):
        roots = deepcopy(self.original)
        unique(roots["vi_BDHb.xml"], "select", "861").find(
            "SelectRangeArray32/*/diagramIdx"
        ).text = "1"
        with self.assertRaisesRegex(AssertionError, "Case mapping"):
            validate_read(roots)
        roots = deepcopy(self.original)
        unique(roots["vi_BDHb.xml"], "mergeErrors", "584").find("dcoList/*").set(
            "uid", "592"
        )
        with self.assertRaisesRegex(AssertionError, "merge error order"):
            validate_read(roots)

    def test_each_timeout_and_n_literal_checked(self):
        for uid in ("670", "809", "57", "823"):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "diag", "3").find(
                f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue"
            ).text = "00"
            with self.assertRaisesRegex(AssertionError, "count/timeout"):
                validate_read(roots)

    def test_polymorphic_reader_selection_checked(self):
        roots = deepcopy(self.original)
        unique(roots["vi_BDHb.xml"], "polyIUse", "1269").find(
            "instanceSelector/menuInstanceUsed"
        ).text = "0F"
        with self.assertRaisesRegex(AssertionError, "polymorphic selection"):
            validate_read(roots)

    def test_all_root_callers_sample_count_literal_checked(self):
        for diag, uid in (("25990", "19298"), ("7386", "8081"), ("41713", "55618")):
            root = deepcopy(self.acq)
            unique(root, "diag", diag).find(
                f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue"
            ).text = "0000000A"
            with self.assertRaisesRegex(AssertionError, "caller/count"):
                validate_io_callers(root)

    def test_task_and_output_card_order_is_not_parser_caption_order(self):
        for uid in ("19467", "1725", "55592", "19491", "2234", "55630"):
            root = deepcopy(self.acq)
            unique(root, "gRef", uid).find("termList/*/dco/paramIdx").text = "20"
            with self.assertRaises(AssertionError):
                validate_io_callers(root)


if __name__ == "__main__":
    unittest.main()
