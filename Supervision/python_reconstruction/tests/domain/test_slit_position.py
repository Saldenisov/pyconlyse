import hashlib
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.slit_position import (
    SLIT_POSITION_EVIDENCE,
    plan_slit_position_change,
)


class SlitPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.supervision = Path(__file__).resolve().parents[3]

    def test_exact_affine_formulas(self) -> None:
        cases = (
            (0, 0, 5.000, 5.000),
            (10, 0, 5.979, 4.021),
            (0, 10, 4.510, 4.510),
            (10, 2, 5.881, 3.923),
        )
        for axe_h, gap_h, expected_hg, expected_hd in cases:
            plan = plan_slit_position_change(axe_h, gap_h)
            self.assertAlmostEqual(plan.position_hg, expected_hg)
            self.assertAlmostEqual(plan.position_hd, expected_hd)

    def test_cluster_patch_and_effect_boundaries_are_exact(self) -> None:
        plan = plan_slit_position_change(2.0, 3.0)
        self.assertEqual(plan.base_cluster, "C9NI6703")
        self.assertEqual(plan.local_mirror, "C9NI6703")
        self.assertEqual(plan.psp_url, "ni.var.psp://localhost/SUPERVISION/C9NI6703")
        self.assertEqual(plan.connection_refnum, 43)
        self.assertEqual(
            [patch.field for patch in plan.patches],
            [
                "02 OUT02 b09 Cmd position fente HG",
                "03 OUT03 b13 Cmd position fente HD",
            ],
        )
        self.assertTrue(plan.preserves_unmentioned_fields)
        self.assertFalse(plan.local_and_psp_sink_order_serialized)
        self.assertTrue(plan.write_error_consumer_observed)
        self.assertTrue(plan.external_effects_blocked)
        self.assertTrue(plan.manual_approval_required)

    def test_invalid_numeric_inputs_fail_closed(self) -> None:
        for axe_h, gap_h, exception in (
            (True, 0, TypeError),
            ("0", 0, TypeError),
            (0, None, TypeError),
            (float("nan"), 0, ValueError),
            (0, float("inf"), ValueError),
        ):
            with self.assertRaises(exception):
                plan_slit_position_change(axe_h, gap_h)  # type: ignore[arg-type]

    def test_evidence_hashes_ledger_and_saved_topology(self) -> None:
        evidence = SLIT_POSITION_EVIDENCE
        self.assertFalse(evidence.extracted_copy_matches_evidence_source)
        for relative_path, expected_hash in (
            (evidence.source_library_path, evidence.source_library_sha256),
            (evidence.reviewed_extracted_copy_path, evidence.reviewed_extracted_copy_sha256),
            (evidence.lvkit_description_path, evidence.lvkit_description_sha256),
            (evidence.manual_screenshot_path, evidence.manual_screenshot_sha256),
            (evidence.print_png_path, evidence.print_png_sha256),
        ):
            artifact = self.supervision / relative_path
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest().upper(), expected_hash)
        self.assertNotEqual(evidence.reviewed_extracted_copy_sha256, evidence.evidence_source_vi_sha256)

        ledger = self.supervision / "analysis" / "expected_selector_frame_ledger.jsonl"
        row = next(
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["expected_key_sha256"] == evidence.expected_key_sha256
        )
        self.assertEqual(row["structure_uid"], "5909")
        self.assertEqual(row["frame_index"], 2)
        self.assertEqual(row["source_vi_sha256"], evidence.evidence_source_vi_sha256)
        self.assertEqual(row["mapping_status"], evidence.formal_png_mapping_status)
        self.assertEqual(row["manual_evidence"][0]["sha256"], evidence.manual_screenshot_sha256)

        description = json.loads(
            (self.supervision / evidence.lvkit_description_path).read_text(encoding="utf-8")
        )
        event_scope = None

        def walk(value: object) -> None:
            nonlocal event_scope
            if isinstance(value, dict):
                if value.get("kind") == "scope" and value.get("uid") == "5909":
                    event_scope = value
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(description["body"])
        self.assertIsNotNone(event_scope)
        frame = event_scope["frames"][2]
        self.assertEqual(frame["label"], evidence.lvkit_event_label)
        nodes = {int(node["uid"]): node for node in frame["body"]}
        self.assertEqual(
            set(nodes),
            {
                62203, 62171, 62296, 62285, 65078, 69008, 67319, 69044, 69033,
                88926, 88939, 83833, 62319, 62327, 69067, 69089, 88920, 88976,
            },
        )
        self.assertFalse(
            any(
                item["net"].get("node") == "Event Data Node"
                for node in nodes.values()
                for item in node.get("inputs", ())
            )
        )
        bundle = nodes[evidence.bundle_uid]
        self.assertEqual(
            [item["terminal"] for item in bundle["inputs"]],
            [
                "1",
                "02 OUT02 b09 Cmd position fente HG",
                "03 OUT03 b13 Cmd position fente HD",
            ],
        )
        write = nodes[evidence.shared_variable_write_uid]
        self.assertEqual(next(item for item in write["inputs"] if item["terminal"] == "0")["net"]["bare"], "Refnum(43)")
        handler = nodes[evidence.simple_error_handler_uid]
        self.assertEqual(handler["inputs"][0]["net"]["node"], "sharedVariableDynamicWrite")


if __name__ == "__main__":
    unittest.main()
