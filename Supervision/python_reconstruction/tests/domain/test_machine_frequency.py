from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.machine_frequency import (
    C1011_LOCAL_MIRROR,
    C1011_PSP_URL,
    MACHINE_FREQUENCY_EVIDENCE,
    MACHINE_FREQUENCY_FIELD,
    MACHINE_FREQUENCY_SINKS,
    PAGE_SYNCHRONISATION,
    SELECTION_NUMBER_FIELD,
    SELECTION_NUMBER_VALUE,
    FrequencySinkKind,
    MachineFrequencySink,
    plan_machine_frequency_change,
)


class MachineFrequencyEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.supervision = Path(__file__).resolve().parents[3]

    def test_new_value_replaces_two_fields_and_fans_out_to_three_sinks(self) -> None:
        plan = plan_machine_frequency_change(17)

        self.assertEqual(plan.event_new_value, 17)
        self.assertEqual(plan.updated_cluster.base_cluster, PAGE_SYNCHRONISATION)
        self.assertEqual(
            plan.updated_cluster.replacements,
            (
                (MACHINE_FREQUENCY_FIELD, 17),
                (SELECTION_NUMBER_FIELD, 4.0),
            ),
        )
        self.assertEqual(SELECTION_NUMBER_VALUE, 4.0)
        self.assertIs(type(SELECTION_NUMBER_VALUE), float)
        self.assertEqual(
            plan.updated_cluster.replacement_labview_types,
            (
                (MACHINE_FREQUENCY_FIELD, "INTEGER_WIDTH_SIGNEDNESS_UNRESOLVED"),
                (SELECTION_NUMBER_FIELD, "DBL"),
            ),
        )
        self.assertTrue(plan.updated_cluster.preserves_unmentioned_fields)
        self.assertEqual(plan.sinks, MACHINE_FREQUENCY_SINKS)
        self.assertEqual(
            plan.sinks,
            frozenset(
                (
                    MachineFrequencySink(FrequencySinkKind.LOCAL_VARIABLE, PAGE_SYNCHRONISATION),
                    MachineFrequencySink(FrequencySinkKind.LOCAL_VARIABLE, C1011_LOCAL_MIRROR),
                    MachineFrequencySink(FrequencySinkKind.PSP_DYNAMIC_WRITE, C1011_PSP_URL),
                )
            ),
        )

    def test_intent_is_immutable_nonexecuting_and_has_no_invented_protocol(self) -> None:
        plan = plan_machine_frequency_change(-1)
        with self.assertRaises(FrozenInstanceError):
            plan.event_new_value = 2  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            plan.updated_cluster.preserves_unmentioned_fields = False  # type: ignore[misc]

        self.assertFalse(plan.sink_order_serialized)
        self.assertFalse(plan.acknowledgement_observed)
        self.assertFalse(plan.retry_observed)
        self.assertFalse(plan.error_consumer_observed)
        self.assertTrue(plan.external_effects_blocked)
        self.assertTrue(plan.manual_approval_required)
        self.assertIn("signedness", "\n".join(plan.unresolved_boundaries))
        for invalid in (True, 1.0, "1", None):
            with self.assertRaises(TypeError):
                plan_machine_frequency_change(invalid)  # type: ignore[arg-type]

    def test_evidence_hashes_and_formal_unmapped_status_are_preserved(self) -> None:
        evidence = MACHINE_FREQUENCY_EVIDENCE
        self.assertEqual(evidence.event_structure_uid, 5909)
        self.assertEqual(evidence.event_case_index, 1)
        self.assertEqual(evidence.event_label, '[1] "Fréquence machine": Value Change')
        self.assertEqual(evidence.formal_png_mapping_status, "UNMAPPED")
        self.assertFalse(evidence.extracted_copy_matches_evidence_source)

        for relative_path, expected_hash in (
            (evidence.source_library_path, evidence.source_library_sha256),
            (evidence.lvkit_description_path, evidence.lvkit_description_sha256),
            (evidence.manual_screenshot_path, evidence.manual_screenshot_sha256),
            (evidence.print_png_path, evidence.print_png_sha256),
        ):
            artifact = self.supervision / relative_path
            self.assertEqual(
                hashlib.sha256(artifact.read_bytes()).hexdigest().upper(),
                expected_hash,
            )
        extracted_copy = self.supervision / evidence.reviewed_extracted_copy_path
        self.assertEqual(
            hashlib.sha256(extracted_copy.read_bytes()).hexdigest().upper(),
            evidence.reviewed_extracted_copy_sha256,
        )
        self.assertNotEqual(evidence.reviewed_extracted_copy_sha256, evidence.source_vi_sha256)

        ledger_path = self.supervision / "analysis" / "expected_selector_frame_ledger.jsonl"
        matching_rows = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["structure_uid"] == "5909" and row["frame_index"] == 1:
                matching_rows.append(row)
        self.assertEqual(len(matching_rows), 1)
        row = matching_rows[0]
        self.assertEqual(row["expected_key_sha256"], evidence.expected_key_sha256)
        self.assertEqual(row["source_vi_sha256"], evidence.source_vi_sha256)
        self.assertEqual(row["mapping_status"], "UNMAPPED")
        self.assertIsNone(row["png_path"])
        self.assertIsNone(row["png_sha256"])
        self.assertEqual(row["manual_evidence"][0]["sha256"], evidence.manual_screenshot_sha256)

    def test_saved_lvkit_topology_matches_the_intent(self) -> None:
        evidence = MACHINE_FREQUENCY_EVIDENCE
        description = json.loads(
            (self.supervision / evidence.lvkit_description_path).read_text(encoding="utf-8")
        )
        event_scope = None

        def walk(value: object) -> None:
            nonlocal event_scope
            if isinstance(value, dict):
                if value.get("kind") == "scope" and value.get("uid") == str(evidence.event_structure_uid):
                    event_scope = value
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(description["body"])
        self.assertIsNotNone(event_scope)
        frame = event_scope["frames"][evidence.event_case_index]
        nodes = {int(node["uid"]): node for node in frame["body"]}
        self.assertEqual(
            set(nodes),
            {
                evidence.event_data_node_uid,
                evidence.base_cluster_read_uid,
                evidence.bundle_by_name_uid,
                evidence.shared_variable_write_uid,
                *evidence.local_variable_uids,
            },
        )

        bundle = nodes[evidence.bundle_by_name_uid]
        base_cluster_input = next(
            item for item in bundle["inputs"] if item["terminal"] == "1"
        )
        self.assertEqual(
            base_cluster_input["net"]["occurrence"],
            nodes[evidence.base_cluster_read_uid]["occurrence"],
        )
        event_value_input = next(
            item for item in bundle["inputs"] if item["net"].get("node") == "Event Data Node"
        )
        self.assertEqual(event_value_input["net"]["terminal"], "5")
        selection_input = next(
            item for item in bundle["inputs"] if item["net"].get("bare") == "4.0"
        )
        self.assertEqual(selection_input["net"]["bare"], "4.0")
        bundle_output = bundle["outputs"][0]

        consumers = []
        for node in nodes.values():
            if any(
                item["net"].get("node") == bundle_output["node"]
                and item["net"].get("terminal") == bundle_output["terminal"]
                and item["net"].get("occurrence") == bundle_output["occurrence"]
                for item in node.get("inputs", ())
            ):
                consumers.append(int(node["uid"]))
        self.assertEqual(
            set(consumers),
            {evidence.shared_variable_write_uid, *evidence.local_variable_uids},
        )

        dynamic_write = nodes[evidence.shared_variable_write_uid]
        self.assertEqual(
            next(item for item in dynamic_write["inputs"] if item["terminal"] == "0")["net"]["bare"],
            "Refnum(46)",
        )

        write_outputs = {
            (output["node"], output["terminal"], output["occurrence"])
            for output in dynamic_write["outputs"]
        }
        consumed_nets = {
            (item["net"].get("node"), item["net"].get("terminal"), item["net"].get("occurrence"))
            for node in nodes.values()
            for item in node.get("inputs", ())
        }
        self.assertTrue(write_outputs.isdisjoint(consumed_nets))


if __name__ == "__main__":
    unittest.main()
