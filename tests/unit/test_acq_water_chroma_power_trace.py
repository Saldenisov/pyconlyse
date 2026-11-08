"""Local-source-only water and focal mains/output distinction regressions."""

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import trace_acq_water_chroma_power as trace


class WaterChromaPowerTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = trace.checked_vam(trace.ACQ)
        cls.catalog = trace.build_catalog()
        cls.labels = trace.inspect_labels(cls.root, cls.meta)

    def test_saved_report_reproduces_without_device_modules(self):
        before = set(sys.modules)
        report = trace.build()
        self.assertEqual(json.loads(trace.OUTPUT.read_text("utf-8")), report)
        self.assertFalse(report["qualifies_hardware_start"])
        self.assertFalse(report["hardware_commands_sent"])
        self.assertFalse(report["serial_ports_opened"])
        forbidden = ("nidaqmx", "PyDAQmx", "serial", "tango", "PyTango")
        self.assertFalse(any(name.split(".")[0] in forbidden
                             for name in set(sys.modules) - before))

    def test_three_independent_stage_commands_are_not_water_permits(self):
        rows = trace.inspect_stages(self.catalog, self.labels)
        self.assertEqual([r["dps_field"] for r in rows], [4, 6, 10])
        self.assertEqual([r["acq_event"] for r in rows], [12, 13, 15])
        self.assertEqual([r["c4_assignments"][0][1] for r in rows], [3, 5, 7])
        self.assertTrue(all(not r["software_water_admission_predicate_found"] for r in rows))
        self.assertTrue(all(not r["eps_ok_is_hardware_ack"] for r in rows))

    def test_wrong_start_bit_rejected(self):
        changed = copy.deepcopy(self.catalog)
        changed["procedures"]["focales.start"]["frames"][0][1][1][2][0][0] = 16
        with self.assertRaisesRegex(AssertionError, "C4 start/reset"):
            trace.inspect_stages(changed, self.labels)

    def test_removed_or_moved_chroma_delay_rejected(self):
        changed = copy.deepcopy(self.catalog)
        nested = changed["procedures"]["focales.start"]["frames"][2][1][0][1]
        nested[0], nested[2] = nested[2], nested[0]
        with self.assertRaisesRegex(AssertionError, "Wait arguments"):
            trace.inspect_stages(changed, self.labels)

    def test_chroma_call_cannot_be_added_to_prema(self):
        changed = copy.deepcopy(self.catalog)
        changed["procedures"]["prema.start"]["frames"][2][1].append(
            ["call_handle_error", "1_Focales ON.vi"])
        with self.assertRaisesRegex(AssertionError, "helper boundary"):
            trace.inspect_stages(changed, self.labels)

    def test_energization_annotation_is_source_checked(self):
        root = copy.deepcopy(self.root)
        trace.unique(root, "label", "40319").find("textRec/text").text = '"water permit"'
        with self.assertRaisesRegex(AssertionError, "power-intent annotation"):
            trace.inspect_labels(root, self.meta)


if __name__ == "__main__":
    unittest.main()
