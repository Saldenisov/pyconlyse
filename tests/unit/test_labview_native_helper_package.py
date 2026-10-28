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

    def save_evidence(self):
        name = self.manifest["qualification_receipt"]
        self.store(name, self.evidence)
        with open(os.path.join(self.root, *name.split("/")), "rb") as stream:
            pin = hashlib.sha256(stream.read()).hexdigest()
        self.manifest["qualification_sha256"] = pin
        for proof in self.manifest["proof_receipts"]:
            if proof["path"] == name:
                proof["sha256"] = pin
        self.save_manifest()

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
        self.assertTrue(result["transport_error_output_erratum_verified"])
        self.assertTrue(result["transport_four_error_sinks_source_verified"])

    def test_transport_erratum_corrects_four_outputs_and_keeps_input_direction(self):
        review = self.evidence["helpers"]["SUP_Camera_Transport.vi"][
            "historical_runtime_findings"
        ]
        self.assertEqual(
            review["unwired_private_error_terminals"], [532, 745, 677, 316]
        )
        correction = self.read(review["mapping_erratum"]["path"])
        scan = correction["error_output_scan"]
        self.assertEqual(scan["total_typed_primitive_error_outputs"], 13)
        self.assertEqual(scan["unwired_output_count"], 4)
        self.assertEqual(scan["incorrect_prior_candidate_673"]["direction"], "input")
        self.assertFalse(correction["qualification"]["runtime_qualified"])

    def test_stale_transport_summary_cannot_repin_qualification(self):
        review = self.evidence["helpers"]["SUP_Camera_Transport.vi"][
            "historical_runtime_findings"
        ]
        for terminals in ([532, 745, 673], [532, 745, 677]):
            review["unwired_private_error_terminals"] = terminals
            self.save_evidence()
            with self.assertRaises(ValueError):
                verify_component(self.root)
        review["unwired_private_error_terminals"] = [532, 745, 677, 316]
        for field, wrong in (
            ("unwired_output_count", 3),
            ("incorrect_prior_terminal_673_direction", "output"),
        ):
            original = review[field]
            review[field] = wrong
            self.save_evidence()
            with self.assertRaises(ValueError):
                verify_component(self.root)
            review[field] = original

    def test_transport_erratum_documents_must_be_declared_and_exact(self):
        paths = (
            "receipts/TRANSPORT20_BASELINE_AND_ERROR_OUTPUT_ERRATUM.json",
            "receipts/TRANSPORT_ERROR_OUTPUT_ERRATUM.rst",
        )
        original = copy.deepcopy(self.manifest["proof_receipts"])
        for path in paths:
            self.manifest["proof_receipts"] = [
                row for row in original if row["path"] != path
            ]
            self.save_manifest()
            with self.assertRaises(ValueError):
                verify_component(self.root)
        self.manifest["proof_receipts"] = original
        path = os.path.join(self.root, *paths[1].split("/"))
        with open(path, "ab") as stream:
            stream.write(b" ")
        with open(path, "rb") as stream:
            pin = hashlib.sha256(stream.read()).hexdigest()
        for row in original:
            if row["path"] == paths[1]:
                row["sha256"] = pin
        self.save_manifest()
        with self.assertRaises(ValueError):
            verify_component(self.root)

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

    def test_only_two_exact_retained_native12_dependencies_are_admitted(self):
        names = (
            "SUP_Camera_Observe_U8_UNCOMPILED.vi",
            "observer_v3/SUP_Camera_Queue_Latest.vi",
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

    def test_old_transport_retained_receipts_cannot_admit_replaced_payload(self):
        transport = self.evidence["helpers"]["SUP_Camera_Transport.vi"]
        prior = transport["history"]
        with self.assertRaises(ValueError):
            qualify_helper(prior["replaced_artifact"], prior["retained_qualification"])
        row = next(
            row
            for row in self.manifest["files"]
            if row["path"] == "SUP_Camera_Transport.vi"
        )
        self.assertTrue(qualify_helper(row, transport))
        for phase in ("native_save", "fresh_project_load", "native_export"):
            changed = copy.deepcopy(transport)
            changed[phase]["passed"] = False
            with self.assertRaises(ValueError):
                qualify_helper(row, changed)

    def test_current_transport_requires_all_thirteen_wired_and_exact_native_sinks(self):
        transport = self.evidence["helpers"]["SUP_Camera_Transport.vi"]
        reference = transport["source_graph_audit"]
        original = self.read(reference["path"])
        for change in ("unwired", "wrong_sink", "changed_old_net"):
            audit = copy.deepcopy(original)
            graph = audit["source_graph"]
            if change == "unwired":
                graph["unwired_error_output_count"] = 1
                graph["typed_error_outputs"][0]["wire_ids"] = []
            elif change == "wrong_sink":
                graph["only_four_extra_nets_relative_to_original"][0]["sink_input"] = (
                    999
                )
            else:
                graph["all_58_original4ab_8f48_nets_exact"] = False
            self.store(reference["path"], audit)
            with open(
                os.path.join(self.root, *reference["path"].split("/")), "rb"
            ) as f:
                pin = hashlib.sha256(f.read()).hexdigest()
            reference["sha256"] = pin
            for proof in self.manifest["proof_receipts"]:
                if proof["path"] == reference["path"]:
                    proof["sha256"] = pin
            self.save_evidence()
            with self.assertRaises(ValueError):
                verify_component(self.root)

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
