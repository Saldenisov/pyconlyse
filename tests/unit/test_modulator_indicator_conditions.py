"""Non-actuating colour/aggregate/consumer source checks and truth fixtures."""

import copy
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import trace_modulator_indicator_conditions as trace


class ModulatorIndicatorConditionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt, cls.roots = trace.original()

    def test_pinned_two_frame_summary_and_no_local_consumers(self):
        summary = trace.verify_summary(self.receipt, self.roots)
        self.assertEqual(len(summary["included_fields"]), 28)
        self.assertEqual(summary["summary_local_readers"], [])
        self.assertFalse(summary["statically_connected_to_command_gate"])
        self.assertEqual(summary["excludes_eau_section_field"], 45)
        self.assertIn("43342", summary["native_qualified_omitted_zero_terminal"])

    def test_all_28_individual_faults_clear_summary(self):
        page = [False] * 59
        self.assertTrue(trace.project_summary(page, page))
        for field in trace.SUMMARY_FIELDS:
            changed = list(page)
            changed[field] = True
            with self.subTest(field=field):
                self.assertFalse(trace.project_summary(changed, changed))

    def test_section_extra_lamp_and_software_ok_are_not_summary_inputs(self):
        page = [False] * 59
        page[45] = True
        page[54:59] = [True] * 5
        self.assertTrue(trace.project_summary(page, page))

    def test_separate_frame_snapshots_must_not_be_silently_made_atomic(self):
        first, second = [False] * 59, [False] * 59
        first[24] = True
        second[0] = True
        self.assertTrue(trace.project_summary(first, second))
        self.assertFalse(trace.project_summary(first, first))
        self.assertFalse(trace.project_summary(second, second))

    def test_projection_rejects_short_snapshot_and_unknown_selected_bit(self):
        with self.assertRaisesRegex(AssertionError, "59-field"):
            trace.project_summary([], [])
        page = [False] * 59
        page[20] = None
        with self.assertRaisesRegex(AssertionError, "Boolean"):
            trace.project_summary(page, page)

    def test_page_writer_and_reader_census(self):
        report = trace.verify_page_consumers(self.receipt, self.roots)
        self.assertEqual(report["local_references"], 12)
        self.assertEqual(len(report["writers"]), 5)

    def test_acquisition_value_producers_are_three_dio_readback_callers(self):
        root, _ = trace.checked_vam(trace.ACQ)
        result = trace.verify_acq_provenance(root, trace.checked_roots(trace.MEMBERS))
        self.assertEqual(result["read_data_terminal"], "2688")
        self.assertEqual({r["c4_input_writer"] for r in result["main_assignments"]},
                         {"19587", "2352", "55726"})
        self.assertFalse(result["software_vacuum_oil_water_threshold_found"])
        self.assertFalse(result["electrical_signal_source_identified"])

    def test_or_instead_of_and_rejected(self):
        roots = copy.deepcopy(self.roots)
        roots["bd"].find(".//*[@class='cpdArith'][@uid='43385']/objFlags").text = "724992"
        with self.assertRaisesRegex(AssertionError, "AND operation"):
            trace.verify_summary(self.receipt, roots)

    def test_removed_input_inversion_rejected(self):
        roots = copy.deepcopy(self.roots)
        roots["bd"].find(".//*[@class='cpdArith'][@uid='48228']/termList/*[@uid='48233']/dco/objFlags").text = "262144"
        with self.assertRaisesRegex(AssertionError, "inversion"):
            trace.verify_summary(self.receipt, roots)

    def test_summary_cannot_gain_an_unreviewed_consumer(self):
        roots = copy.deepcopy(self.roots)
        roots["bd"].find(".//*[@class='signal'][@uid='4182']/termList").append(
            ET.Element("extra", uid="HARDWARE_START_GUARD"))
        with self.assertRaisesRegex(AssertionError, "consumer"):
            trace.verify_summary(self.receipt, roots)

    def test_summary_cannot_gain_a_local_reader(self):
        roots = copy.deepcopy(self.roots)
        roots["bd"].append(ET.fromstring(
            '<extra class="gRef" uid="NEW_READER"><termList><t class="term" uid="NEW_PORT">'
            '<dco><paramIdx>60</paramIdx><objFlags>1</objFlags></dco></t></termList></extra>'))
        with self.assertRaisesRegex(AssertionError, "local reader"):
            trace.verify_summary(self.receipt, roots)

    def test_page_cannot_gain_a_hidden_stage_permission_reader(self):
        roots = copy.deepcopy(self.roots)
        roots["bd"].append(ET.fromstring(
            '<extra class="gRef" uid="NEW_READER"><termList><t class="term" uid="NEW_PORT">'
            '<dco><paramIdx>164</paramIdx><objFlags>1</objFlags></dco></t></termList></extra>'))
        with self.assertRaisesRegex(AssertionError, "reference census"):
            trace.verify_page_consumers(self.receipt, roots)

    def test_other_lamp_cannot_replace_vacuum_in_summary(self):
        roots = copy.deepcopy(self.roots)
        roots["bd"].find(".//*[@class='nMux'][@uid='43337']/termList/*[@uid='54876']/dco/i").text = "45"
        with self.assertRaisesRegex(AssertionError, "field ordinal"):
            trace.verify_summary(self.receipt, roots)

    def test_report_reproduces_without_hardware_modules(self):
        before = set(sys.modules)
        report = trace.build()
        self.assertEqual(json.loads(trace.OUTPUT.read_text("utf-8")), report)
        self.assertEqual(len(report["observations"]["raw_digital_indicators"]), 29)
        self.assertFalse(report["hardware_commands_sent"])
        self.assertFalse(report["safe_to_start_without_cooling"])
        forbidden = {"nidaqmx", "PyDAQmx", "serial", "tango", "PyTango"}
        self.assertFalse(any(name.split(".")[0] in forbidden
                             for name in set(sys.modules) - before))


if __name__ == "__main__":
    unittest.main()
