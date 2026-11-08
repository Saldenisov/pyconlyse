"""Original DIO96 exchange and rejecting source mutations, including callers."""

import json
import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.rw_dio96 import (
    READ_UIDS,
    SOURCE,
    WRITE_UIDS,
)
from validate_acq_dio96_exchange import (
    CALL_UIDS,
    PORTS,
    checked_root,
    checked_roots,
    unique,
    validate_callers,
    validate_exchange,
)


class Dio96ExchangeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exports = REPOSITORY / "legacy/xp_acq_agent/data/source_exports"
        cls.original = checked_roots(
            exports / "ACQ_17_original_members_XML_20261001.zip"
        )
        cls.original_root = checked_root(exports / "0_ACQ_ELYSE_XML_sha6fe8.zip")

    def setUp(self):
        self.roots = deepcopy(self.original)

    def test_original_helper_and_callers_pass(self):
        self.assertIn(
            "read data assigned without error guard", validate_exchange(self.roots)
        )
        self.assertIn("OUT 17/15/13, IN 18/16/14", validate_callers(self.original_root))

    def test_python_identity_and_call_sequence_match_pinned_source(self):
        census = json.loads(
            (
                REPOSITORY / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json"
            ).read_text(encoding="utf-8")
        )
        member = next(m for m in census["members"] if m["vi"] == SOURCE.name)
        self.assertEqual(SOURCE.sha256, member["source_vi_sha256"])
        self.assertEqual(READ_UIDS + WRITE_UIDS, CALL_UIDS)

    def test_every_error_net_break_rejected(self):
        for port in ("5669", "2734", "3973", "2880", "4786", "5301", "4024"):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "diag", "1684").find(
                f"signalList/*/termList/*[@uid='{port}']"
            ).set("uid", "999999")
            with self.assertRaisesRegex(AssertionError, "body wire set"):
                validate_exchange(roots)

    def test_each_read_or_write_data_edge_swap_rejected(self):
        for port in ("1479", "3084", "4010", "1666", "4829", "5343"):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "diag", "1684").find(
                f"signalList/*/termList/*[@uid='{port}']"
            ).set("uid", "999999")
            with self.assertRaisesRegex(AssertionError, "body wire set"):
                validate_exchange(roots)

    def test_read_output_alias_and_output_bank_alias_changes_rejected(self):
        for uid in ("843", "3081", "4007", "854", "4826", "5340"):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "gRef", uid).find(
                "termList/*/dco/paramIdx"
            ).text = "3"
            with self.assertRaisesRegex(AssertionError, "local identity/direction"):
                validate_exchange(roots)

    def test_front_panel_ddo_register_is_not_parser_document_order(self):
        first = self.roots["vi_FPHb.xml"].find("root/ddoList/*")
        first.set("uid", "5469")
        with self.assertRaisesRegex(AssertionError, "local-index register"):
            validate_exchange(self.roots)

    def test_task_cluster_input_output_fields_checked(self):
        unique(self.roots["vi_BDHb.xml"], "nMux", "425").find(
            "termList/*[2]/dco/i"
        ).text = "5"
        with self.assertRaisesRegex(AssertionError, "task-cluster field order"):
            validate_exchange(self.roots)

    def test_each_autostart_checked(self):
        for uid in ("538", "4816", "5330"):
            roots = deepcopy(self.original)
            unique(roots["vi_BDHb.xml"], "diag", "1684").find(
                f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue"
            ).text = "00"
            with self.assertRaisesRegex(AssertionError, "autoStart"):
                validate_exchange(roots)

    def test_each_call_selector_and_port_identity_checked(self):
        for uid, ports in zip(CALL_UIDS, PORTS):
            roots = deepcopy(self.original)
            node = unique(roots["vi_BDHb.xml"], "polyIUse", uid)
            node.find("instanceSelector/menuInstanceUsed").text = "00"
            with self.assertRaisesRegex(AssertionError, "polymorphic boundary"):
                validate_exchange(roots)
            node.find("instanceSelector/menuInstanceUsed").text = (
                "0F" if uid in READ_UIDS else "0E"
            )
            node.find(f"termList/*[@uid='{ports[11]}']").set("uid", "999999")
            with self.assertRaisesRegex(AssertionError, "port identities"):
                validate_exchange(roots)

    def test_added_error_guard_retry_or_debounce_rejected(self):
        ET.SubElement(
            unique(self.roots["vi_BDHb.xml"], "diag", "1684").find("zPlaneList"),
            "extra",
            {"class": "select", "uid": "999999"},
        )
        with self.assertRaisesRegex(AssertionError, "operation census"):
            validate_exchange(self.roots)

    def test_empty_first_frame_cannot_hide_new_operation(self):
        ET.SubElement(
            unique(self.roots["vi_BDHb.xml"], "diag", "9110").find("zPlaneList"),
            "extra",
            {"class": "iUse", "uid": "999999"},
        )
        with self.assertRaisesRegex(AssertionError, "first frame gained"):
            validate_exchange(self.roots)

    def test_error_tunnel_reversal_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "sequence", "8872").find(
            "termList/*[@uid='5673']/dco/objFlags"
        ).text = "2049"
        with self.assertRaisesRegex(AssertionError, "sequence tunnel"):
            validate_exchange(self.roots)

    def test_root_alias_changes_rejected_for_every_caller(self):
        for uid in ("19555", "2344", "55694", "19579", "2336", "55718"):
            root = deepcopy(self.original_root)
            unique(root, "gRef", uid).find("termList/*/dco/paramIdx").text = "13"
            with self.assertRaisesRegex(AssertionError, "bank/converter"):
                validate_callers(root)

    def test_root_error_chain_changes_rejected_for_every_caller(self):
        for frame, port in (("25990", "19388"), ("7386", "700"), ("41713", "55514")):
            root = deepcopy(self.original_root)
            unique(root, "diag", frame).find(
                f"signalList/*/termList/*[@uid='{port}']"
            ).set("uid", "999999")
            with self.assertRaisesRegex(AssertionError, "terminal wire"):
                validate_callers(root)


if __name__ == "__main__":
    unittest.main()
