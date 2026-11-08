"""Mutation tests against saved native VI exports; no LabVIEW/device execution."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_acq_publication_refactor import Export, GROUP, validate  # noqa: E402
from validate_acq_runtime_io_frame import heap_type  # noqa: E402

ORIGINAL = ROOT / ".tmp/acq_original_diagram_census_20261001/0_ACQ_ELYSE"
NATIVE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-13/group8_static/export")


@unittest.skipUnless((ORIGINAL / "vi.xml").is_file() and (NATIVE / GROUP / "vi.xml").is_file(),
                     "requires immutable local native eight-bank export")
class PublicationRefactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = (Export(ORIGINAL), Export(NATIVE / "0_ACQ_ELYSE"), Export(NATIVE / GROUP),
                        {p.name: Export(p) for p in NATIVE.iterdir()
                         if p.name.startswith("ACQ_Publish_") and p.name != GROUP})

    def setUp(self):
        self.original, self.copied, self.group, self.helpers = deepcopy(self.evidence)

    def check(self):
        return validate(self.original, self.copied, self.group, self.helpers)

    def test_saved_native_refactor_passes_with_bounded_claim(self):
        result = self.check()
        self.assertEqual(result["runtime_bank_order"],
                         ["C1NI6071E", "C2NI6071E", "EPS", "EPC", "VTA", "C3_IN_DIO96", "C4_IN_DIO96", "C5_IN_DIO96"])
        self.assertEqual(result["total_psp_publication_sites"], 73)
        self.assertFalse(result["telemetry_complete"])
        self.assertFalse(result["native_vi_executed"])

    def test_wrong_bank_uri_rejected(self):
        constant = self.helpers["ACQ_Publish_C2NI6071E"].root.find("nodeList/*/termList/*/dco/ConstValue")
        constant.text = constant.text.replace("43324E493630373145", "43314E493630373145")
        with self.assertRaisesRegex(AssertionError, "URI"):
            self.check()

    def test_cut_error_chain_rejected(self):
        signals = self.group.root.find("signalList")
        signals.remove(signals[-1])
        with self.assertRaisesRegex(AssertionError, "wire set"):
            self.check()

    def test_swapped_caller_bank_inputs_rejected(self):
        frame = next(n for n in self.copied.bd.iter() if n.get("class") == "diag" and n.get("uid") == "7392")
        for term in frame.findall("signalList/*/termList/*"):
            uid = term.get("uid")
            if uid in ("24756", "24824"):
                term.set("uid", "24824" if uid == "24756" else "24756")
        with self.assertRaisesRegex(AssertionError, "caller.*wire set"):
            self.check()

    def test_changed_dio_field_type_rejected(self):
        helper = self.helpers["ACQ_Publish_C3_IN_DIO96"]
        control = next(n for n in helper.fp.iter() if n.get("class") == "fPDCO" and n.findtext("conNum") == "11")
        number = int(control.findtext("typeDesc")[7:-1])
        cluster, flat = heap_type(helper.metadata, number)
        flat[int(cluster.find("TypeDesc").get("TypeID"))].set("Type", "NumFloat64")
        with self.assertRaisesRegex(AssertionError, "data type"):
            self.check()

    def test_added_c1_error_input_wire_rejected(self):
        inner = self.helpers["ACQ_Publish_C1NI6071E"]
        signal = deepcopy(inner.root.find("signalList/*"))
        signal.find("termList")[0].set("uid", "C1-ERROR-IN-MUST-NOT-BE-WIRED")
        inner.root.find("signalList").append(signal)
        with self.assertRaisesRegex(AssertionError, "C1 inner.*wire set"):
            self.check()

    def test_extra_hardware_primitive_in_helper_rejected(self):
        ET.SubElement(self.helpers["ACQ_Publish_EPS"].root.find("zPlaneList"), "SL__arrayElement", {"class": "prim", "uid": "extra"})
        with self.assertRaisesRegex(AssertionError, "unexpected operation"):
            self.check()

    def test_local_reference_moved_into_group_rejected(self):
        ET.SubElement(self.group.root.find("zPlaneList"), "SL__arrayElement", {"class": "gRef", "uid": "extra"})
        with self.assertRaisesRegex(AssertionError, "unexpected operation"):
            self.check()

    def test_fault_assignment_false_rejected(self):
        term = next(n for n in self.copied.bd.iter() if n.get("class") == "term" and n.get("uid") == "49997")
        term.find("dco/ConstValue").text = "0000"
        with self.assertRaisesRegex(AssertionError, "fault assignment"):
            self.check()

    def test_fault_case_polarity_rejected(self):
        case = next(n for n in self.copied.bd.iter() if n.get("class") == "select" and n.get("uid") == "40346")
        case.find("SelectRangeArray32/*/start").text = "1"
        with self.assertRaisesRegex(AssertionError, "polarity"):
            self.check()

    def test_removed_remaining_publication_rejected(self):
        node = next(n for n in self.copied.bd.iter() if n.get("class") == "sharedVariableDynamicWrite")
        node.set("class", "REMOVED")
        with self.assertRaisesRegex(AssertionError, "census"):
            self.check()

    def test_missing_group_call_link_rejected(self):
        self.copied.calls = {uid: name for uid, name in self.copied.calls.items() if name != GROUP + ".vi"}
        with self.assertRaisesRegex(AssertionError, "expected one call"):
            self.check()

    def test_extra_caller_operation_rejected(self):
        frame = next(n for n in self.copied.bd.iter() if n.get("class") == "diag" and n.get("uid") == "7392")
        ET.SubElement(frame.find("zPlaneList"), "SL__arrayElement", {"class": "prim", "uid": "extra"})
        with self.assertRaisesRegex(AssertionError, "caller publication frame"):
            self.check()

    def test_duplicate_helper_writer_rejected(self):
        helper = self.helpers["ACQ_Publish_EPC"]
        helper.root.find("zPlaneList").append(deepcopy(helper.root.find("zPlaneList/*[@class='sharedVariableDynamicWrite']")))
        with self.assertRaisesRegex(AssertionError, "exactly one PSP writer"):
            self.check()

    def test_extra_fault_arm_operation_rejected(self):
        frame = next(n for n in self.copied.bd.iter() if n.get("class") == "diag" and n.get("uid") == "50030")
        ET.SubElement(frame.find("zPlaneList"), "SL__arrayElement", {"class": "gRef", "uid": "extra"})
        with self.assertRaisesRegex(AssertionError, "fault arm"):
            self.check()

    def test_duplicate_group_call_rejected(self):
        self.group.root.find("zPlaneList").append(deepcopy(self.group.root.find("zPlaneList/*[@class='iUse']")))
        with self.assertRaisesRegex(AssertionError, "call count"):
            self.check()

    def test_extra_c1_wrapper_call_rejected(self):
        helper = self.helpers["ACQ_Publish_C1NI6071E_State"]
        helper.root.find("zPlaneList").append(deepcopy(helper.root.find("zPlaneList/*[@class='iUse']")))
        with self.assertRaisesRegex(AssertionError, "expected one call|additional C1"):
            self.check()


if __name__ == "__main__":
    unittest.main()
