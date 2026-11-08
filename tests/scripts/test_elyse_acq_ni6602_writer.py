"""Saved counter source checks reject poll, timing and error-route mutations."""

import json
import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.write_ni6602 import SOURCE
from validate_acq_ni6602_writer import (
    POLL_WIRES,
    ROOT_WIRES,
    checked_root,
    checked_roots,
    unique,
    validate_acq_caller,
    validate_writer,
)


class CounterWriterSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exports = REPOSITORY / "legacy/xp_acq_agent/data/source_exports"
        cls.original = checked_roots(
            exports / "ACQ_17_original_members_XML_20261001.zip"
        )
        cls.acq = checked_root(exports / "0_ACQ_ELYSE_XML_sha6fe8.zip")

    def test_original_and_acq_only_caller_pass(self):
        self.assertIn("Done==True OR i>20", validate_writer(self.original))
        self.assertIn("error input unwired", validate_acq_caller(self.acq))

    def test_python_source_identity_is_original_not_working_copy(self):
        census = json.loads(
            (
                REPOSITORY / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json"
            ).read_text()
        )
        member = next(m for m in census["members"] if m["vi"] == SOURCE.name)
        self.assertEqual(SOURCE.sha256, member["source_vi_sha256"])

    def test_each_root_and_poll_net_is_checked(self):
        for diagram, wires in (("3", ROOT_WIRES), ("3149", POLL_WIRES)):
            for wire in wires:
                roots = deepcopy(self.original)
                unique(roots["vi_BDHb.xml"], "diag", diagram).find(
                    f"signalList/*/termList/*[@uid='{wire[0]}']"
                ).set("uid", "999999")
                with self.assertRaisesRegex(AssertionError, "wire set"):
                    validate_writer(roots)

    def test_stop_polarity_and_error_feedback_change_rejected(self):
        for tag, value in (("loopTestDCO/objFlags", "1"), ("srDCOList", "1")):
            roots = deepcopy(self.original)
            node = unique(roots["vi_BDHb.xml"], "whileLoop", "3129").find(tag)
            if tag == "srDCOList":
                node.set("elements", value)
            else:
                node.text = value
            with self.assertRaisesRegex(AssertionError, "polarity/index/shift"):
                validate_writer(roots)

    def test_input_tunnels_cannot_silently_become_shift_registers(self):
        roots = deepcopy(self.original)
        unique(roots["vi_BDHb.xml"], "whileLoop", "3129").find(
            "termList/*[@uid='184']/dco"
        ).set("class", "lSR")
        with self.assertRaisesRegex(AssertionError, "ordinary loop tunnel"):
            validate_writer(roots)

    def test_comparison_and_or_inversion_are_checked(self):
        for cls, uid, path, value in (
            ("prim", "127", "primResID", "1111"),
            ("prim", "3183", "primResID", "1103"),
            ("cpdArith", "420", "objFlags", "655360"),
            ("cpdArith", "420", "termList/*/dco/objFlags", "196609"),
        ):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], cls, uid).find(path).text = value
            with self.assertRaises(AssertionError):
                validate_writer(roots)

    def test_property_read_write_direction_and_order_are_checked(self):
        for uid, path, value in (
            ("3202", ".//PropItemCode", "664"),
            ("3202", "termList/*[@uid='3216']/dco/objFlags", "0"),
            ("3083", ".//PropItemCode", "4457"),
            ("3083", "termList/*[@uid='3109']/dco/objFlags", "1"),
        ):
            roots = deepcopy(self.original)
            node = unique(roots["vi_BDHb.xml"], "propNode", uid)
            target = node.find(path)
            if target is None:
                target = ET.SubElement(node.find(path.rsplit("/", 1)[0]), "objFlags")
            target.text = value
            with self.assertRaisesRegex(
                AssertionError, "property order/identity/direction"
            ):
                validate_writer(roots)

    def test_no_hidden_retry_or_error_case_is_allowed(self):
        roots = deepcopy(self.original)
        ET.SubElement(
            unique(roots["vi_BDHb.xml"], "diag", "3149").find("zPlaneList"),
            "new",
            {"class": "select", "uid": "999999"},
        )
        with self.assertRaisesRegex(AssertionError, "operation census"):
            validate_writer(roots)

    def test_scale_and_poll_literals_checked(self):
        for diagram, uid in (
            ("3", "13218"),
            ("3", "13230"),
            ("3149", "368"),
            ("3149", "3171"),
            ("3149", "3161"),
        ):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "diag", diagram).find(
                f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue"
            ).text = "00"
            with self.assertRaisesRegex(AssertionError, "literal changed"):
                validate_writer(roots)

    def test_acq_timing_and_error_handler_input_edges_checked(self):
        for port in ("23671", "23677", "23680", "23650"):
            root = deepcopy(self.acq)
            unique(root, "diag", "23641").find(
                f"signalList/*/termList/*[@uid='{port}']"
            ).set("uid", "999999")
            with self.assertRaises(AssertionError):
                validate_acq_caller(root)

    def test_reset_and_publication_order_cannot_be_reversed(self):
        root = deepcopy(self.acq)
        frames = unique(root, "sequence", "23633").find("diagramList")
        first = frames[0]
        frames.remove(first)
        frames.append(first)
        with self.assertRaisesRegex(AssertionError, "call/reset/publication order"):
            validate_acq_caller(root)

    def test_reset_selector_literal_and_field_checked(self):
        root = deepcopy(self.acq)
        unique(root, "nMux", "23468").find("termList/*[@uid='23478']/dco/i").text = "31"
        with self.assertRaisesRegex(AssertionError, "selector reset"):
            validate_acq_caller(root)

    def test_reset_and_publish_read_the_grounded_local(self):
        root = deepcopy(self.acq)
        unique(root, "gRef", "5036").find("termList/*/dco/paramIdx").text = "21"
        with self.assertRaisesRegex(AssertionError, "local alias"):
            validate_acq_caller(root)


if __name__ == "__main__":
    unittest.main()
