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

    def test_eight_helpers_pass_without_runtime_or_full_camera_claim(self):
        result = verify_component(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["helpers"]), 8)
        self.assertFalse(result["native2012_runtime_proven"])
        self.assertFalse(result["full_camera_pipeline_ready"])
        self.assertTrue(result["FrameTap_implemented"])

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
            os.path.join(self.root, "DIAG_Unqualified_FrameTap.vi"),
        )
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_unlisted_non_VI_payloads_are_not_a_subtree_exemption(self):
        for name in ("extra.exe", "extra.py", "extra.lvlps"):
            path = os.path.join(self.root, name)
            with open(path, "wb") as stream:
                stream.write(b"unexpected test payload; never executed")
            with self.assertRaises(ValueError):
                verify_component(self.root)
            os.remove(path)

    def test_only_three_exact_retained_native12_dependencies_are_admitted(self):
        names = (
            "SUP_Camera_Observe_U8_UNCOMPILED.vi",
            "observer_v3/SUP_Camera_Queue_Latest.vi",
            "SUP_Camera_Transport.vi",
        )
        for name in names:
            row = next(r for r in self.manifest["files"] if r["path"] == name)
            evidence = self.evidence["helpers"][name]
            self.assertTrue(
                evidence["fresh_project_load"]["dirty_after_cross_version_load"]
            )
            self.assertTrue(qualify_helper(row, evidence))
            for field in ("name", "hash", "writer", "proof", "fresh_hash"):
                changed_row, changed = copy.deepcopy(row), copy.deepcopy(evidence)
                if field == "name":
                    changed_row["path"] = "unreviewed.vi"
                elif field == "hash":
                    changed_row["sha256"] = "0" * 64
                elif field == "writer":
                    changed["last_writer"] = "pylabview"
                elif field == "proof":
                    changed["existing_native12_artifact"]["receipt_sha256"] = "0" * 64
                else:
                    changed["fresh_project_load"]["sha256"] = "0" * 64
                with self.assertRaises(ValueError):
                    qualify_helper(changed_row, changed)

    def test_retained_original_receipt_tamper_refuses(self):
        queue = self.evidence["helpers"]["observer_v3/SUP_Camera_Queue_Latest.vi"]
        path = os.path.join(
            self.root, *queue["existing_native12_artifact"]["receipt"].split("/")
        )
        with open(path, "ab") as stream:
            stream.write(b" ")
        with self.assertRaises(ValueError):
            verify_component(self.root)

    def test_synthetic_FrameTap_cannot_bypass_native_events_with_model_success(self):
        row = next(
            r for r in self.manifest["files"] if r["path"] == "SUP_Camera_FrameTap.vi"
        )
        evidence = copy.deepcopy(self.evidence["helpers"][row["path"]])
        evidence["native_save"]["last_writer"] = "lvkit"
        evidence["graph_tests_passed"] = True
        evidence["model_cases"] = 4000
        with self.assertRaises(ValueError):
            qualify_helper(row, evidence)

    def test_manifest_cannot_promote_runtime_or_full_pipeline(self):
        for field in ("full_camera_pipeline_ready", "native2012_runtime_proven"):
            self.manifest[field] = True
            self.save_manifest()
            with self.assertRaises(ValueError):
                verify_component(self.root)
            self.manifest[field] = False
        self.save_manifest()

    def test_frametap_audit_tamper_and_false_inventory_claim_refuse(self):
        audit = self.evidence["helpers"]["SUP_Camera_FrameTap.vi"]["source_graph_audit"]
        with open(os.path.join(self.root, *audit["path"].split("/")), "ab") as stream:
            stream.write(b" ")
        with self.assertRaises(ValueError):
            verify_component(self.root)
        self.manifest["FrameTap_implemented"] = False
        self.save_manifest()
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
