from __future__ import annotations

import csv
import hashlib
import importlib
import json
from pathlib import Path
import unittest

from supervision_reconstruction.catalog import records
from tools.build_catalog import extract_dependencies_from_data


PROJECT = Path(__file__).resolve().parents[2]
REPO = PROJECT.parents[1]
VI_ROOT = REPO / "Supervision" / "extracted" / "PILOTAGE_ELYSE_SUP" / "SUPERVISION_VIs"
MOTOR = REPO / "Supervision" / "extracted" / "PILOTAGE_ELYSE_SUP" / "PILOTAGE_ELYSE_SUP_moteurs" / "Moteurs SdC GoTo.vi"
CATALOG_ROOT = PROJECT / "src" / "supervision_reconstruction" / "catalog"
EXPECTED_DOMAIN_MODELS = {
    "0_SUP_ELYSE.vi": "supervision_reconstruction.domain.supervision_orchestrator",
    "1_SUP_INIT_NI6602.vi": "supervision_reconstruction.domain.ni6602",
    "1_SUP_PROFILS XY.vi": "supervision_reconstruction.domain.profiles",
    "1_SUP_WRITE_NI6602.vi": "supervision_reconstruction.domain.ni6602",
    "2_SUP_Ecart_lu_ecr_VDirecte.vi": "supervision_reconstruction.domain.deviation",
    "2_SUP_Ecart_lu_ecr_VDéviée.vi": "supervision_reconstruction.domain.deviation",
    "2_SUP_Graph _Radioprot.vi": "supervision_reconstruction.domain.radioprotection",
    "2_SUP_Journal_des _erreurs.vi": "supervision_reconstruction.domain.journal",
    "2_SUP_marche_defaut_VIDE.vi": "supervision_reconstruction.domain.vacuum",
    "3_SUP_en_défaut_alims.vi": "supervision_reconstruction.domain.power_supplies",
    "Add Item.vi": "supervision_reconstruction.domain.tree_plans",
    "BuildHelpPath.vi": "supervision_reconstruction.domain.help_paths",
    "Check Special Tags.vi": "supervision_reconstruction.domain.message_text",
    "Convert property node font to graphics font.vi": "supervision_reconstruction.domain.font_ui",
    "Details Display Dialog.vi": "supervision_reconstruction.domain.application_plans",
    "Directory to Tree.vi": "supervision_reconstruction.domain.tree_plans",
    "Error Code Database.vi": "supervision_reconstruction.domain.error_code_database",
    "Find Tag.vi": "supervision_reconstruction.domain.message_text",
    "Format Message String.vi": "supervision_reconstruction.domain.message_text",
    "FW102x Close.vi": "supervision_reconstruction.domain.fw102x_operations",
    "FW102x Error Message.vi": "supervision_reconstruction.domain.fw102x_errors",
    "FW102x Get Position.vi": "supervision_reconstruction.domain.fw102x_operations",
    "FW102x Initialize.vi": "supervision_reconstruction.domain.fw102x_operations",
    "FW102x IVI Error Converter.vi": "supervision_reconstruction.domain.fw102x_errors",
    "FW102x Set Position.vi": "supervision_reconstruction.domain.fw102x_operations",
    "GetHelpDir.vi": "supervision_reconstruction.domain.help_paths",
    "General Error Handler CORE.vi": "supervision_reconstruction.domain.dialog_error",
    "General Error Handler.vi": "supervision_reconstruction.domain.dialog_error",
    "Initialize.vi": "supervision_reconstruction.domain.file_dialog",
    "Init_Open_Close.vi": "supervision_reconstruction.domain.application_plans",
    "Longest Line Length in Pixels.vi": "supervision_reconstruction.domain.font_ui",
    "Moteurs SdC GoTo.vi": "supervision_reconstruction.domain.motor_planner",
    "Not Found Dialog.vi": "supervision_reconstruction.domain.dialog_error",
    "Search and Replace Pattern.vi": "supervision_reconstruction.domain.message_text",
    "Set Bold Text.vi": "supervision_reconstruction.domain.font_ui",
    "sous vi LigneCentroide2.vi": "supervision_reconstruction.domain.application_plans",
    "Three Button Dialog CORE.vi": "supervision_reconstruction.domain.dialog_error",
    "Three Button Dialog.vi": "supervision_reconstruction.domain.dialog_error",
    "Validate.vi": "supervision_reconstruction.domain.file_dialog",
}


def hidden_frame_manifest() -> dict[str, object]:
    return json.loads((CATALOG_ROOT / "labview_hidden_frame_manifest.json").read_text(encoding="utf-8"))


def root_dependency_sections() -> list[dict[str, object]]:
    manifest = hidden_frame_manifest()
    document = next(item for item in manifest["documents"] if item["document"]["path"].endswith("root_and_dependencies_all_hidden.html"))
    return document["sections"]


class CatalogTests(unittest.TestCase):
    def assert_artifact(self, value: dict[str, object]) -> None:
        path = REPO / str(value["path"])
        self.assertTrue(path.is_file(), path)
        self.assertEqual(value["sha256"], hashlib.sha256(path.read_bytes()).hexdigest().upper())

    def test_every_vi_section_has_one_importable_fail_closed_stub(self) -> None:
        root_vi_names = {
            section["vi_name"]
            for section in root_dependency_sections()
            if Path(section["vi_name"]).suffix.lower() == ".vi" and section["vi_name"] != "Global Variables.vi"
        }
        expected_names = root_vi_names | {MOTOR.name}
        catalog_records = records()
        self.assertEqual({record["vi_name"] for record in catalog_records}, expected_names)
        self.assertEqual(len(catalog_records), len(expected_names))
        self.assertEqual(len({record["module"] for record in catalog_records}), len(catalog_records))
        for record in catalog_records:
            module = importlib.import_module(record["module"])
            source = record["source"]
            self.assertEqual(module.SOURCE_SHA256, source["sha256"] if source else None)
            self.assertEqual(module.DOMAIN_MODEL, record["domain_model"])
            with self.assertRaises(NotImplementedError):
                module.reconstruct()

    def test_all_root_sections_are_classified_without_brittle_total(self) -> None:
        sections = root_dependency_sections()
        catalog_names = {record["vi_name"] for record in records()}
        inventory = json.loads((CATALOG_ROOT / "catalog.json").read_text(encoding="utf-8"))["non_vi_evidence"]
        inventory_names = {record["section_name"] for record in inventory}
        expected_non_vi = {
            section["vi_name"]
            for section in sections
            if Path(section["vi_name"]).suffix.lower() == ".ctl" or section["vi_name"] == "Global Variables.vi"
        }
        expected_vi = {section["vi_name"] for section in sections if section["vi_name"] not in expected_non_vi}
        self.assertEqual(inventory_names, expected_non_vi)
        self.assertTrue(expected_vi <= catalog_names)
        self.assertTrue(all(record["section_classification"] == "VI" for record in records()))
        self.assertEqual(expected_vi | expected_non_vi, {section["vi_name"] for section in sections})
        self.assertEqual(
            {record["classification"] for record in inventory},
            {"CTL", "EXPECTED_DIAGRAMLESS_GLOBAL"},
        )

    def test_original_thirty_nine_application_records_remain_resolved(self) -> None:
        application_records = [record for record in records() if record["record_scope"] == "application_scope"]
        expected_sources = {*VI_ROOT.glob("*.vi"), MOTOR}
        self.assertEqual(len(application_records), len(expected_sources))
        self.assertEqual({REPO / record["source"]["path"] for record in application_records}, expected_sources)
        self.assertTrue(all(record["source_status"] == "resolved" for record in application_records))

    def test_sources_are_hashed_only_when_unambiguous_and_unresolved_entries_are_evidence_identified(self) -> None:
        for record in records():
            source = record["source"]
            if record["source_status"] == "resolved":
                self.assertIsNotNone(source)
                self.assert_artifact(source)
                self.assertIn(record["boundary"]["kind"], {"application_scope", "copied_vendor", "labview_builtin", "copied_source"})
            else:
                self.assertIsNone(source)
                self.assertEqual(record["boundary"]["kind"], "unresolved_dependency")
                self.assertTrue(record["identity"].startswith("labview-export:"))
                self.assertEqual(record["boundary"]["intended_as"], "black_box_adapter_contract")

    def test_all_vi_records_link_hashed_hidden_frame_sections(self) -> None:
        for record in records():
            sections = record["evidence"]["labview_hidden_frames"]["sections"]
            self.assertGreaterEqual(len(sections), 1, record["vi_name"])
            for section in sections:
                self.assert_artifact(section["document"])
                self.assertGreaterEqual(len(section["frames"]), 1)
                for frame in section["frames"]:
                    self.assert_artifact(frame)
                    self.assertEqual(frame["dimensions"]["format"], "png")

    def test_hidden_frame_export_manifest_is_complete_and_hashed(self) -> None:
        manifest = hidden_frame_manifest()
        self.assertEqual(manifest["summary"], {"html_documents": 3, "png_frames": 1305})
        for document in manifest["documents"]:
            self.assert_artifact(document["document"])
        for frame in manifest["all_png_frames"]:
            self.assert_artifact(frame)
            self.assertEqual(frame["dimensions"]["format"], "png")

    def test_error_code_database_is_visually_blocked_not_complete(self) -> None:
        record = next(record for record in records() if record["vi_name"] == "Error Code Database.vi")
        self.assertEqual(record["visual_status"], "BLOCKED_VISUAL")
        self.assertEqual(record["conversion_state"], "open")
        self.assertIn("password-protected", record["visual_rationale"])

    def test_lvkit_contexts_are_retained_for_application_and_not_overclaimed_for_dependencies(self) -> None:
        allowed = {"CONTEXT_AGREEMENT_NOT_VALIDATION", "CONTEXT_DISAGREEMENT", "MISSING_CONTEXT", "NOT_BATCHED_DEPENDENCY"}
        for record in records():
            contexts = record["evidence"]["lvkit"]["contexts"]
            self.assertEqual(set(contexts), {"base", "minimal_vilib"})
            self.assertIn(record["evidence"]["lvkit"]["context_verdict"]["verdict"], allowed)
        dependencies = [record for record in records() if record["record_scope"] == "dependency_scope"]
        self.assertTrue(all(record["evidence"]["lvkit"]["context_verdict"]["verdict"] == "NOT_BATCHED_DEPENDENCY" for record in dependencies))

    def test_reviewed_domain_models_remain_explicit_and_importable(self) -> None:
        modeled = [record for record in records() if record["domain_model"] is not None]
        self.assertEqual({record["vi_name"]: record["domain_model"] for record in modeled}, EXPECTED_DOMAIN_MODELS)
        for record in modeled:
            importlib.import_module(record["domain_model"])

    def test_verified_status_cannot_be_claimed_without_complete_evidence(self) -> None:
        self.assertEqual([record["vi_name"] for record in records() if record["conversion_state"] == "verified"], [])

    def test_application_coverage_matrix_matches_catalog_models_and_states(self) -> None:
        matrix_path = REPO / "Supervision" / "analysis" / "vi_coverage_matrix.csv"
        with matrix_path.open(encoding="utf-8-sig", newline="") as stream:
            matrix = {row["vi_name"]: row for row in csv.DictReader(stream)}
        application = {
            record["vi_name"]: record
            for record in records()
            if record["record_scope"] == "application_scope"
        }
        self.assertEqual(set(matrix), set(application))
        for vi_name, record in application.items():
            row = matrix[vi_name]
            self.assertEqual(row["conversion_state"], record["conversion_state"])
            self.assertEqual(row["domain_model"], record["domain_model"] or "")
            self.assertEqual(
                row["python_status"],
                "REVIEWED_PURE_MODEL" if record["domain_model"] else "FAIL_CLOSED_STUB",
            )

    def test_catalog_is_machine_readable_and_declares_safe_stubs(self) -> None:
        data = json.loads((CATALOG_ROOT / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 3)
        self.assertTrue(all(record["implementation"] == "stub_raises_not_implemented" for record in data["records"]))

    def test_nested_lvkit_bodies_are_traversed_for_dependencies(self) -> None:
        nested = {
            "body": [
                {"kind": "instance", "name": "outer.vi"},
                {"frames": [{"body": [{"kind": "instance", "qualified_name": "nested.vi"}]}]},
                {"events": [{"case": {"body": [{"kind": "instance", "name": "event.vi"}]}}]},
            ]
        }
        extracted = extract_dependencies_from_data(nested)
        self.assertEqual([entry["name"] for entry in extracted], ["event.vi", "nested.vi", "outer.vi"])
        self.assertTrue(any("frames" in entry["json_path"] for entry in extracted))
