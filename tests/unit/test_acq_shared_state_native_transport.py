"""Offline regressions of saved native queue/TCP guard; never execute a VI."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_acq_shared_state_helpers import Export, node  # noqa: E402
from validate_acq_shared_state_transport import (  # noqa: E402
    NAME,
    NATIVE,
    audit,
    validate,
)


@unittest.skipUnless(
    (NATIVE / "export" / NAME / "vi.xml").is_file(), "local native evidence required"
)
class NativeTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = Export(NATIVE / "export" / NAME)

    def setUp(self):
        self.export = deepcopy(self.saved)

    def test_saved_hash_pinned_transport_passes_without_delivery_claim(self):
        report = audit()
        self.assertEqual(report["empty_queue_tcp_operations"], 0)
        self.assertFalse(report["native_runtime_verified_by_this_audit"])

    def test_timeout_error_instead_of_boolean_cannot_select_tcp(self):
        signal = node(self.export.bd, "signal", "1848")
        signal.find("termList/*").set("uid", "1185")
        with self.assertRaisesRegex(AssertionError, "wire topology"):
            validate(self.export)

    def test_inverted_case_polarity_rejected(self):
        case = node(self.export.bd, "select", "1680")
        case.find("SelectRangeArray32/*/diagramIdx").text = "1"
        with self.assertRaisesRegex(AssertionError, "polarity"):
            validate(self.export)

    def test_network_operation_in_idle_case_rejected(self):
        case = node(self.export.bd, "diag", "1688")
        ET.SubElement(
            case.find("nodeList"), "SL__arrayElement", {"class": "iUse", "uid": "99999"}
        )
        with self.assertRaisesRegex(AssertionError, "unexpected executable"):
            validate(self.export)

    def test_psp_write_rejected(self):
        ET.SubElement(
            self.export.bd.find("root/zPlaneList"),
            "SL__arrayElement",
            {"class": "sharedVariableDynamicWrite", "uid": "99999"},
        )
        with self.assertRaisesRegex(AssertionError, "unexpected executable"):
            validate(self.export)

    def test_queue_capacity_cannot_grow(self):
        node(self.export.bd, "bDConstDCO", "1099").find("ConstValue").text = "000003E8"
        with self.assertRaisesRegex(AssertionError, "constant"):
            validate(self.export)

    def test_unbounded_dequeue_rejected(self):
        node(self.export.bd, "bDConstDCO", "1228").find("ConstValue").text = "FFFFFFFF"
        with self.assertRaisesRegex(AssertionError, "constant"):
            validate(self.export)

    def test_cleanup_queue_reference_wire_required(self):
        diagram = node(self.export.bd, "diag", "3")
        diagram.find("signalList").remove(node(self.export.bd, "signal", "1369"))
        with self.assertRaisesRegex(AssertionError, "wire topology"):
            validate(self.export)

    def test_run_on_open_rejected(self):
        self.export.metadata.find("LVSR/Section/Execution").set("RunOnOpen", "1")
        with self.assertRaisesRegex(AssertionError, "RunOnOpen"):
            validate(self.export)
