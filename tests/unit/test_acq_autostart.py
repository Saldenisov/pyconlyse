"""Mutation tests of saved native lifecycle evidence; executes no VI."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from validate_acq_autostart import (  # noqa: E402
    FIXTURE,
    NATIVE,
    START,
    TEST,
    WORKER,
    NativeExport,
    audit,
    validate,
)
from validate_acq_shared_state_helpers import node  # noqa: E402


@unittest.skipUnless((NATIVE / "export" / START).is_dir(), "native evidence required")
class AutoStartTests(unittest.TestCase):
    def setUp(self):
        self.start = NativeExport(START)
        self.worker = NativeExport(WORKER)

    def test_four_reviewed_native_files_pass(self):
        self.assertEqual(len(audit()), 4)

    def test_false_stop_rejected(self):
        node(self.start.bd, "bDConstDCO", "1244").find("ConstValue").text = "0000"
        with self.assertRaisesRegex(AssertionError, "constant"):
            validate(self.start)

    def test_blocking_stop_send_rejected(self):
        node(self.start.bd, "bDConstDCO", "1159").find("ConstValue").text = "FFFFFFFF"
        with self.assertRaisesRegex(AssertionError, "constant"):
            validate(self.start)

    def test_blocking_stop_receive_rejected(self):
        node(self.worker.bd, "bDConstDCO", "759").find("ConstValue").text = "FFFFFFFF"
        with self.assertRaisesRegex(AssertionError, "constant"):
            validate(self.worker)

    def test_stop_element_disconnected_rejected(self):
        d = node(self.worker.bd, "diag", "297")
        for wire in d.findall("signalList/*"):
            if wire.find("termList/*").get("uid") == "739":
                wire.find("termList/*").set("uid", "742")
        with self.assertRaisesRegex(AssertionError, "stop Dequeue"):
            validate(self.worker)

    def test_idle_network_insertion_rejected(self):
        ET.SubElement(
            node(self.worker.bd, "diag", "1688").find("nodeList"),
            "SL__arrayElement",
            {"class": "iUse", "uid": "99999"},
        )
        with self.assertRaisesRegex(AssertionError, "native resource"):
            validate(self.worker)

    def test_new_psp_write_rejected(self):
        ET.SubElement(
            self.worker.bd.find("root/zPlaneList"),
            "SL__arrayElement",
            {"class": "sharedVariableDynamicWrite", "uid": "99999"},
        )
        with self.assertRaisesRegex(AssertionError, "native resource"):
            validate(self.worker)

    def test_nonhardware_test_cannot_call_main(self):
        e = NativeExport(TEST)
        e.calls["378"] = "0_ACQ_ELYSE.vi"
        with self.assertRaisesRegex(AssertionError, "launcher call"):
            validate(e)

    def test_fixture_cannot_run_main(self):
        e = NativeExport(FIXTURE)
        e.calls["999"] = "0_ACQ_ELYSE.vi"
        with self.assertRaisesRegex(AssertionError, "must not run acquisition"):
            validate(e)

    def test_run_on_open_rejected(self):
        e = deepcopy(self.start)
        e.metadata.find("LVSR/Section/Execution").set("RunOnOpen", "1")
        with self.assertRaisesRegex(AssertionError, "RunOnOpen"):
            validate(e)
