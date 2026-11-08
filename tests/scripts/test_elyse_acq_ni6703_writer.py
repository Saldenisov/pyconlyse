"""Pinned original source and rejecting mutations for NI6703 writer facets."""

import json
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.write_ni6703 import (
    C8_OFFSETS,
    SLOPES,
    SOURCE,
    WRITE_UIDS,
)
from validate_acq_ni6703_writer import (
    ARRAYS,
    CALL_PORTS,
    CALLS,
    FORMULAS,
    checked_root,
    checked_writer_roots,
    numeric_array,
    unique,
    validate_caller_edges,
    validate_writer,
)


class Ni6703WriterSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exports = REPOSITORY / "legacy/xp_acq_agent/data/source_exports"
        cls.original = checked_writer_roots(
            exports / "ACQ_17_original_members_XML_20261001.zip"
        )
        cls.original_root = checked_root(exports / "0_ACQ_ELYSE_XML_sha6fe8.zip")

    def setUp(self):
        self.roots = deepcopy(self.original)

    def constant(self, uid, roots=None):
        bd = (self.roots if roots is None else roots)["vi_BDHb.xml"]
        return bd.find(f"root/nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue")

    def test_original_writer_and_three_caller_facets_pass(self):
        self.assertIn("C6->C9 error chain", validate_writer(self.roots))
        self.assertEqual(len(validate_caller_edges(self.original_root)), 3)

    def test_python_source_identity_and_all_fifty_coefficients_match_original(self):
        census = json.loads(
            (
                REPOSITORY / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json"
            ).read_text(encoding="utf-8")
        )
        identity = next(m for m in census["members"] if m["vi"] == SOURCE.name)
        self.assertEqual(SOURCE.sha256, identity["source_vi_sha256"])
        frame = self.roots["vi_BDHb.xml"].find("root")
        self.assertEqual(
            SLOPES,
            tuple(numeric_array(frame, uid) for uid in ("378", "420", "453", "485")),
        )
        self.assertEqual(C8_OFFSETS, numeric_array(frame, "1246"))
        self.assertEqual(WRITE_UIDS, tuple(row[0] for row in CALLS))

    def test_every_connected_coefficient_mutation_is_rejected(self):
        for uid, values in ARRAYS.items():
            for index in range(10):
                with self.subTest(uid=uid, index=index):
                    roots = deepcopy(self.original)
                    changed = list(values)
                    changed[index] += 0.001
                    self.constant(uid, roots).text = (
                        (struct.pack(">I", 10) + struct.pack(">10d", *changed))
                        .hex()
                        .upper()
                    )
                    with self.assertRaisesRegex(AssertionError, "coefficient array"):
                        validate_writer(roots)

    def test_all_nonlinear_indices_are_checked(self):
        for uid in ("1347", "1229", "791", "1370"):
            roots = deepcopy(self.original)
            self.constant(uid, roots).text = "00000005"
            with self.assertRaisesRegex(AssertionError, "nonlinear channel index"):
                validate_writer(roots)

    def test_every_active_formula_is_checked(self):
        for uid, *_ in FORMULAS:
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "fBox", uid).find(
                "formula/text"
            ).text = '"y=x;"'
            with self.assertRaisesRegex(AssertionError, "active formula"):
                validate_writer(roots)

    def test_acos_to_cubic_wire_swap_is_rejected(self):
        self.roots["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='753']").set(
            "uid", "762"
        )
        with self.assertRaisesRegex(AssertionError, "root wire set"):
            validate_writer(self.roots)

    def test_every_error_input_chain_break_is_rejected(self):
        for uid in ("1411", "1773", "2037", "2298", "1282"):
            roots = deepcopy(self.original)
            roots["vi_BDHb.xml"].find(
                f"root/signalList/*/termList/*[@uid='{uid}']"
            ).set("uid", "999999")
            with self.assertRaisesRegex(AssertionError, "root wire set"):
                validate_writer(roots)

    def test_each_timeout_and_autostart_literal_is_checked(self):
        for _, _, auto, timeout in CALLS:
            for uid, value in ((auto, "00"), (timeout, "3FF0000000000000")):
                roots = deepcopy(self.original)
                self.constant(uid, roots).text = value
                with self.assertRaisesRegex(AssertionError, "autoStart/timeout"):
                    validate_writer(roots)

    def test_write_selector_and_port_identity_are_checked(self):
        node = unique(self.roots["vi_BDHb.xml"], "polyIUse", "592")
        node.find("instanceSelector/menuInstanceUsed").text = "08"
        with self.assertRaisesRegex(AssertionError, "polymorphic"):
            validate_writer(self.roots)
        node.find("instanceSelector/menuInstanceUsed").text = "06"
        node.find("termList/*[@uid='1411']").set("uid", "999999")
        with self.assertRaisesRegex(AssertionError, "connector identities"):
            validate_writer(self.roots)

    def test_returned_task_or_count_consumption_is_rejected(self):
        for ports in CALL_PORTS:
            for slot in (4, 10):
                roots = deepcopy(self.original)
                roots["vi_BDHb.xml"].find(
                    "root/signalList/*/termList/*[@uid='1411']"
                ).set("uid", ports[slot])
                with self.assertRaisesRegex(AssertionError, "root wire set"):
                    validate_writer(roots)

    def test_input_task_field_swap_is_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "nMux", "1840").find(
            "termList/*[2]/dco/i"
        ).text = "2"
        with self.assertRaisesRegex(AssertionError, "task field order"):
            validate_writer(self.roots)

    def test_added_retry_guard_or_alias_is_rejected(self):
        ET.SubElement(
            self.roots["vi_BDHb.xml"].find("root/zPlaneList"),
            "extra",
            {"class": "whileLoop", "uid": "999999"},
        )
        with self.assertRaisesRegex(AssertionError, "operation census"):
            validate_writer(self.roots)

    def test_old_implementation_enable_or_nonempty_active_arm_is_rejected(self):
        comment = unique(self.roots["vi_BDHb.xml"], "commentNode", "1070")
        comment.find("commentMode").text = "False"
        with self.assertRaisesRegex(AssertionError, "disabled implementation mode"):
            validate_writer(self.roots)
        comment.find("commentMode").text = "True"
        ET.SubElement(
            comment.findall("diagramList/*")[1].find("zPlaneList"),
            "extra",
            {"class": "prim", "uid": "999999"},
        )
        with self.assertRaisesRegex(AssertionError, "empty enabled arm"):
            validate_writer(self.roots)

    def test_public_connector_bank_swap_is_rejected(self):
        self.roots["vi.xml"].findall("CPMp/Section/TypeDesc")[5].set("Flags", "0x0300")
        with self.assertRaisesRegex(AssertionError, "local mapping"):
            validate_writer(self.roots)

    def test_each_root_bank_alias_swap_is_rejected(self):
        for uid in ("19603", "2388", "55742"):
            root = deepcopy(self.original_root)
            unique(root, "gRef", uid).find("termList/*/dco/paramIdx").text = "10"
            with self.assertRaisesRegex(AssertionError, "logical bank/converter"):
                validate_caller_edges(root)

    def test_each_root_error_chain_break_is_rejected(self):
        for frame_uid, port in (
            ("25990", "19444"),
            ("7386", "484"),
            ("41713", "55569"),
        ):
            root = deepcopy(self.original_root)
            unique(root, "diag", frame_uid).find(
                f"signalList/*/termList/*[@uid='{port}']"
            ).set("uid", "999999")
            with self.assertRaisesRegex(AssertionError, "terminal wire"):
                validate_caller_edges(root)

    def test_added_root_call_site_is_rejected(self):
        root = deepcopy(self.original_root)
        node = deepcopy(unique(root, "iUse", "278"))
        node.set("uid", "999999")
        unique(root, "diag", "7386").find("zPlaneList").append(node)
        with self.assertRaisesRegex(AssertionError, "call-site census"):
            validate_caller_edges(root)


if __name__ == "__main__":
    unittest.main()
