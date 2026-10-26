"""Offline plan/source checks only; never load LabVIEW or an NI driver."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools import prepare_supervision_vi_export as plan


def panel_fixture():
    root = ET.Element("root")
    for name, uid in plan.CONTROL_UIDS.items():
        node = ET.SubElement(root, "node", {"class": "fPDCO", "uid": uid})
        parts = ET.SubElement(ET.SubElement(node, "ddo"), "partsList")
        label = ET.SubElement(parts, "label", {"class": "label"})
        ET.SubElement(label, "partID").text = "16"
        ET.SubElement(ET.SubElement(label, "textRec"), "text").text = '"' + name + '"'
    return root


class SupervisionExportPlanUnitTests(unittest.TestCase):
    def test_exact_shared_control_catalog_and_ambiguous_or_missing_refusal(self):
        source = panel_fixture()
        self.assertEqual(plan.control_catalog(source), plan.CONTROL_UIDS)
        duplicate = copy.deepcopy(source)
        duplicate.append(copy.deepcopy(duplicate[0]))
        self.assertRaises(ValueError, plan.control_catalog, duplicate)
        source.remove(source[0])
        self.assertRaises(ValueError, plan.control_catalog, source)

    def test_exact_source_wire_anchor_and_changed_net_refusal(self):
        root = ET.Element("root")
        for diagram, wires in plan.WIRES.items():
            node = ET.SubElement(root, "node", {"class": "diag", "uid": diagram})
            signals = ET.SubElement(node, "signalList")
            for uid, terminals in wires.items():
                signal = ET.SubElement(signals, "signal", {"uid": uid})
                terms = ET.SubElement(signal, "termList")
                for term in terminals:
                    ET.SubElement(terms, "term", {"uid": term})
        self.assertEqual(plan.verify_wires(root), plan.WIRES)
        root.find("node/signalList/signal/termList/term").set("uid", "changed")
        self.assertRaises(ValueError, plan.verify_wires, root)


@unittest.skipUnless((plan.DEFAULT_RECEIPTS / "00.json").is_file() and plan.DEFAULT_HELPERS.is_dir(),
                     "External pinned native source corpus unavailable")
class PinnedSupervisionExportPlanTests(unittest.TestCase):
    def test_original_source_audit_is_explicitly_not_an_exporter_or_compile(self):
        value = plan.audit()
        self.assertEqual(value["original_root_sha256"], plan.ROOT_HASH)
        self.assertTrue(value["existing_collector_27_names_reusable"])
        self.assertEqual(value["counter"]["supervision_slice"], [16, 32])
        self.assertEqual(value["descriptor"]["type"], "String")
        self.assertFalse(value["new_native_vi_authored"])
        self.assertFalse(value["native_compile_verified"])
        self.assertFalse(value["deployable"])
        self.assertFalse(value["originals_modified"])
        self.assertFalse(value["live_canonical_source_bound"])
        self.assertFalse(value["authoring_workspace_bound"])
        self.assertEqual(set(value["verified_source_receipts"]), {"00.json", "01.json", "03.json"})

    def test_changed_helper_source_and_malformed_or_changed_xml_receipts_refuse(self):
        with tempfile.TemporaryDirectory(prefix="elyse-sup-helper-receipt-test-") as folder:
            folder = Path(folder)
            originals = {name: json.loads((plan.DEFAULT_RECEIPTS / name).read_text(encoding="utf-8"))
                         for name in plan.SOURCE_PINS}
            def save(candidate_name=None, candidate=None):
                for name, value in originals.items():
                    (folder / name).write_text(json.dumps(candidate if name == candidate_name else value), encoding="utf-8")
            for name in ("01.json", "03.json"):
                bad = copy.deepcopy(originals[name])
                bad["xml"] = "not a source closure"
                save(name, bad)
                self.assertRaises(ValueError, plan.audit, folder)
                bad = copy.deepcopy(originals[name])
                bad["xml"][0]["sha256"] = "0" * 64
                save(name, bad)
                self.assertRaises(ValueError, plan.audit, folder)
                bad = copy.deepcopy(originals[name])
                changed = folder / (name + ".changed.vi")
                changed.write_bytes(Path(bad["source"]).read_bytes() + b"changed synthetic trailer")
                bad["source"] = str(changed)
                save(name, bad)
                self.assertRaises(ValueError, plan.audit, folder)
                bad = copy.deepcopy(originals[name])
                changed_xml = folder / (name + ".changed.xml")
                changed_xml.write_bytes(Path(bad["xml"][1]["path"]).read_bytes() + b"changed synthetic trailer")
                bad["xml"][1]["path"] = str(changed_xml)
                save(name, bad)
                self.assertRaises(ValueError, plan.audit, folder)

    def test_staged_reference_helpers_match_source_and_exclude_hardware_launchers(self):
        with tempfile.TemporaryDirectory(prefix="elyse-offline-sup-export-plan-") as folder:
            output = Path(folder) / "new_plan"
            value = plan.stage(output)
            self.assertFalse(value["hardware_main_or_launcher_copied"])
            self.assertFalse(value["hardware_accessed"])
            self.assertFalse(value["vi_executed"])
            assets = output / "reference_helpers_do_not_autorun"
            self.assertEqual({path.name for path in assets.iterdir()}, set(plan.HELPER_HASHES))
            for name, expected in plan.HELPER_HASHES.items():
                self.assertEqual(plan.digest(assets / name), expected)
            self.assertRaises(ValueError, plan.stage, output)
            self.assertEqual(json.loads((output / "export_plan.json").read_text())["deployable"], False)


if __name__ == "__main__":
    unittest.main()
