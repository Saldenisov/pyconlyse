"""Opt-in saved XP artifact audit and mutation checks; no LabVIEW execution."""

import copy
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from tools.validate_acq_telemetry_sender import validate, validate_diagram


BASE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-12")
SOURCE = BASE / "xp_snapshot_20261012/ELYSE_ACQ_TELEMETRY_20261012/ACQ_Telemetry_Send_JSON.vi"
EXPORT = BASE / "helper_static_export"


@unittest.skipUnless(SOURCE.exists() and (EXPORT / "vi_BDHb.xml").exists(),
                     "requires separately archived XP fixture sender and lvkit export")
class SavedTelemetrySenderAuditTests(unittest.TestCase):
    def setUp(self):
        self.diagram = ET.parse(EXPORT / "vi_BDHb.xml").getroot()
        self.metadata = ET.parse(EXPORT / "vi.xml").getroot()

    def test_saved_source_and_export_pass(self):
        report = validate(SOURCE, EXPORT)
        self.assertEqual(report["wire_count"], 24)
        self.assertFalse(report["live_acquisition_hook"])
        self.assertFalse(report["hardware_access"])

    def test_error_wire_removed_fails(self):
        signals = self.diagram.find("root/signalList")
        signals.remove(signals.find("*[@uid='665']"))
        with self.assertRaisesRegex(AssertionError, "wire topology"):
            validate_diagram(self.diagram, self.metadata)

    def test_subvi_added_fails(self):
        ET.SubElement(self.diagram.find("root/zPlaneList"), "SL__arrayElement",
                      {"class": "iUse", "uid": "9999"})
        with self.assertRaisesRegex(AssertionError, "subVI"):
            validate_diagram(self.diagram, self.metadata)

    def test_unknown_primitive_fails(self):
        self.diagram.find("root/zPlaneList/*[@uid='105']/primResID").text = "9999"
        with self.assertRaisesRegex(AssertionError, "primitive identity"):
            validate_diagram(self.diagram, self.metadata)

    def test_timeout_or_destination_changed_fails(self):
        for type_id, tag, value in (("16", "I32", "60000"),
                                   ("10", "String", "10.20.30.10")):
            altered = copy.deepcopy(self.metadata)
            altered.find(f"DFDS/Section/DataFill[@TypeID='{type_id}']/{tag}").text = value
            with self.assertRaisesRegex(AssertionError, "saved constant"):
                validate_diagram(self.diagram, altered)

    def test_run_on_open_fails(self):
        self.metadata.find("LVSR/Section/Execution").set("RunOnOpen", "1")
        with self.assertRaisesRegex(AssertionError, "RunOnOpen"):
            validate_diagram(self.diagram, self.metadata)


if __name__ == "__main__":
    unittest.main()
