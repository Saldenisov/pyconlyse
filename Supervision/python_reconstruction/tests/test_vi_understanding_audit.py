"""Check audit identities and limits, not legacy behavioral completeness."""

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
AUDIT = REPO / "Supervision/analysis/VI_UNDERSTANDING_AUDIT_r4.json"


class VIUnderstandingAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.records = cls.audit["records"]
        cls.by_name = {row["vi_name"]: row for row in cls.records}

    def check_identity(self, row):
        path = REPO / row["path"]
        self.assertTrue(path.is_file(), row["path"])
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        self.assertEqual(actual, row["sha256"], row["path"])

    def test_every_catalog_vi_has_one_individual_record(self):
        self.assertEqual(len(self.records), 126)
        self.assertEqual(len(self.by_name), 126)
        self.assertEqual(
            Counter(row["scope"] for row in self.records),
            {"application_scope": 39, "dependency_scope": 87},
        )
        for row in self.records:
            if row["scope"] == "application_scope":
                self.assertTrue(row["known_logic_boundary"])
                self.assertTrue(row["python_evidence_models"])
                self.assertTrue(row["connector_inventory_available"])
                self.assertTrue(row["original_source_receipt"])

    def test_partial_models_are_not_promoted_to_full_understanding(self):
        self.assertTrue(self.audit["complete_vi_understanding_not_established"])
        self.assertTrue(self.audit["no_defensible_complete_vi_percentage"])
        self.assertEqual(
            self.by_name["Error Code Database.vi"]["understanding_state"],
            "EXCLUDED_BY_USER",
        )
        self.assertFalse(self.by_name["Error Code Database.vi"]["analysis_requested"])
        self.assertEqual(self.audit["active_application_vis"], 38)
        for row in self.records:
            self.assertFalse(row["whole_vi_logic_understanding_certified"])
            self.assertTrue(
                row["runtime_effect_qualification_is_separate_from_logic_understanding"]
            )
            if not row["connector_inventory_available"]:
                self.assertTrue(
                    row["absent_connector_descriptor_means_unknown_not_zero_terminals"]
                )
        for edge in self.audit["symbolic_edges_not_a_qualified_runtime_call_graph"]:
            self.assertFalse(edge["runtime_call_edge_proven"])

    def test_main_event_refinements_do_not_replace_other_vi_reviews(self):
        self.assertEqual(self.audit["main_event_indices_are_not_vi_count"], 34)
        models = self.by_name["0_SUP_ELYSE.vi"]["python_evidence_models"]
        paths = {model["path"] for model in models}
        coverage = json.loads(
            (
                REPO / "Supervision/python_reconstruction/EVENT_MODEL_COVERAGE.json"
            ).read_text(encoding="utf-8")
        )
        names = {
            name for event in coverage["events"] for name in event["bounded_models"]
        }
        for name in names:
            self.assertTrue(any(path.endswith(f"/{name}.py") for path in paths))

    def test_ledger_gaps_are_preserved_per_vi(self):
        self.assertEqual(
            sum(
                row["selector_frame_ledger"]["expected_entries"] for row in self.records
            ),
            732,
        )
        self.assertEqual(
            sum(row["loop_body_ledger"]["expected_entries"] for row in self.records),
            41,
        )
        self.assertTrue(self.audit["unmapped_frames_do_not_mean_no_semantic_knowledge"])

    def test_current_audit_evidence_hashes_match(self):
        for row in self.audit["inventory_evidence"]:
            self.check_identity(row)
        self.check_identity(self.audit["supersedes_without_overwriting"])
        self.check_identity(self.audit["earlier_audit_preserved"])
        for record in self.records:
            if record["saved_descriptor"]:
                self.check_identity(record["saved_descriptor"])
            if record["original_source_receipt"]:
                self.check_identity(record["original_source_receipt"])
                self.check_identity(record["original_source_receipt"]["source"])
            for model in record["python_evidence_models"]:
                self.check_identity(model)
        journal = self.audit["journal_new_descriptor_and_native_observations"]
        for row in journal["evidence"]:
            self.check_identity(row)
        self.assertEqual(journal["display_format"], "%d/%m %H:%M:%S   ")
        self.assertEqual(journal["file_format"], "%Y %d/%m %H:%M:%S   ")
        self.assertTrue(journal["two_independent_clock_reads"])
        self.assertFalse(journal["complete_vi_qualification"])


if __name__ == "__main__":
    unittest.main()
