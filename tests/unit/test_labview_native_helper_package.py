"""Native qualification boundaries; exact VI copies only, no LabVIEW calls."""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.verify_labview_native_helper_package import qualify_helper, verify_component

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PACKET = os.path.join(
    REPO, "legacy", "labview", "supervision_telemetry", "individual_helpers", "camera"
)


class NativeHelperPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.temp.name, "camera")
        shutil.copytree(PACKET, self.root)
        self.manifest = self.read("package_manifest.json")
        self.evidence = self.read(self.manifest["qualification_receipt"])
        self.row = next(
            r for r in self.manifest["files"] if r["path"] == "SUP_Camera_Epoch.vi"
        )
        self.qualified = self.evidence["helpers"][self.row["path"]]

    def tearDown(self):
        self.temp.cleanup()

    def read(self, name):
        with open(
            os.path.join(self.root, *name.split("/")), encoding="utf-8"
        ) as stream:
            return json.load(stream)

    def store(self, name, value):
        with open(
            os.path.join(self.root, *name.split("/")), "w", encoding="utf-8"
        ) as stream:
            json.dump(value, stream)

    def save_manifest(self):
        self.store("package_manifest.json", self.manifest)

    def edit_project(self, transform):
        project = self.manifest["projects"][1]["path"]
        path = os.path.join(self.root, project)
        tree = ET.parse(path)
        transform(tree)
        tree.write(path, encoding="utf-8", xml_declaration=True)
        with open(path, "rb") as stream:
            raw = stream.read()
        row = next(r for r in self.manifest["files"] if r["path"] == project)
        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.save_manifest()

    def test_four_helpers_pass_without_runtime_or_full_camera_claim(self):
        result = verify_component(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["helpers"]), 4)
        self.assertFalse(result["native2012_runtime_proven"])
        self.assertFalse(result["full_camera_pipeline_ready"])
        self.assertFalse(result["FrameTap_implemented"])

    def test_all_three_native_phases_are_required_even_with_models(self):
        for phase in ("native_save", "fresh_project_load", "native_export"):
            evidence = copy.deepcopy(self.qualified)
            evidence[phase]["passed"] = False
            evidence["graph_tests_passed"] = True
            with self.assertRaises(ValueError):
                qualify_helper(self.row, evidence)

    def test_fresh_FP_and_BD_are_individually_required(self):
        for field in ("FP", "BD", "stopped"):
            evidence = copy.deepcopy(self.qualified)
            evidence["fresh_project_load"][field] = False
            with self.assertRaises(ValueError):
                qualify_helper(self.row, evidence)

    def test_current_lvkit_pylabview_writer_rejected_even_with_native_flags(self):
        for writer in ("lvkit", "pylabview", "RSRC_serializer"):
            evidence = copy.deepcopy(self.qualified)
            evidence["last_writer"] = writer
            evidence["graph_tests_passed"] = True
            with self.assertRaises(ValueError):
                qualify_helper(self.row, evidence)
        evidence = copy.deepcopy(self.qualified)
        evidence["native_save"]["last_writer"] = "pylabview"
        with self.assertRaises(ValueError):
            qualify_helper(self.row, evidence)

    def test_historical_generation_and_same_process_are_not_fake_failures(self):
        evidence = copy.deepcopy(self.qualified)
        evidence["historical_generated_source"] = True
        evidence["fresh_project_load"]["process_restart"] = False
        self.assertTrue(qualify_helper(self.row, evidence))

    def test_unimplemented_FrameTap_and_stale_source_or_export_hash_rejected(self):
        for change in ("unimplemented", "source", "output", "version"):
            evidence = copy.deepcopy(self.qualified)
            if change == "unimplemented":
                evidence["implemented"] = False
            elif change == "source":
                evidence["native_save"]["sha256"] = "0" * 64
            elif change == "output":
                evidence["native_export"]["sha256"] = "0" * 64
            else:
                evidence["native_export"]["version"] = "20.0"
            with self.assertRaises(ValueError):
                qualify_helper(self.row, evidence)

    def test_wrong_payload_pin_rejected_without_mutating_a_VI(self):
        self.row["sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_filename_only_URL_fails_even_when_same_folder_file_exists(self):
        def transform(tree):
            for item in tree.iter("Item"):
                if item.get("URL", "").startswith("../"):
                    item.set("URL", item.get("URL")[3:])

        self.edit_project(transform)
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_unlisted_custom_caller_rejected(self):
        self.manifest["custom_relative_links"][0]["caller"] = "stale.vi"
        self.save_manifest()
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_unlisted_FrameTap_exact_copy_rejected(self):
        shutil.copy2(
            os.path.join(self.root, "SUP_Camera_Epoch.vi"),
            os.path.join(self.root, "SUP_Camera_FrameTap.vi"),
        )
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_undeclared_system_dependency_rejected(self):
        def transform(tree):
            for item in tree.iter("Item"):
                if item.get("URL", "").startswith("/<vilib>/"):
                    item.set("URL", "/<vilib>/unexpected.ctl")

        self.edit_project(transform)
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_direct_script_and_module_entrypoints_work(self):
        commands = [
            ["tools/verify_labview_native_helper_package.py", "--root", self.root],
            ["-m", "tools.verify_labview_native_helper_package", "--root", self.root],
            ["tools/verify_labview_sync_native12_package.py"],
        ]
        for command in commands:
            output = subprocess.check_output([sys.executable, "-B"] + command, cwd=REPO)
            self.assertEqual(json.loads(output.decode("utf-8"))["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
