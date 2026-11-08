import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.diagnostic_events import (
    CENTROID_RESET_EVIDENCE, DIAGNOSTIC_POSITION_RULES, DIAGNOSTIC_SELECTOR_VALUES,
    EVIDENCE_SOURCE_VI_SHA256, LVKIT_CONTEXTS, REVIEWED_WORKING_COPY, SOURCE_LIBRARY,
    DiagnosticStation, ResetStepKind, plan_centroid_average_reset, plan_diagnostic_position_change,
)


def walk(nodes):
    for node in nodes:
        yield node
        for frame in node.get("frames", []):
            yield from walk(frame.get("body", []))


class DiagnosticEventsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.events = []
        for context in LVKIT_CONTEXTS:
            description = json.loads((cls.supervision / context.path).read_text(encoding="utf-8"))
            cls.events.append(next(n for n in walk(description["body"]) if n.get("uid") == "5909"))
        cls.ledger = [json.loads(line) for line in (cls.supervision / "analysis/expected_selector_frame_ledger.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_nine_golden_selection_cases_use_unscaled_command_and_scaled_display(self):
        expected = [(0, 2.126, 21.26), (1, 8.98, 89.8), (2, 5.553, 55.53)]
        for station in DiagnosticStation:
            for selector, command, display in expected:
                with self.subTest(station=station, selector=selector):
                    plan = plan_diagnostic_position_change(station, selector)
                    self.assertEqual(plan.legacy_command_value, command)
                    self.assertEqual(plan.patch[1], command)
                    self.assertAlmostEqual(plan.display_value, display)
                    self.assertEqual(plan.display_local, f"Cmd pos {station.value}")

    def test_each_station_replaces_only_its_named_historical_field(self):
        fields = ["04 OUT04 b17 Cmd position translateur Ecran 1",
                  "05 OUT05 b21 Cmd position translateur Ecran 2",
                  "06 OUT06 b25 Cmd position translateur Ecran 3"]
        for station, field_name in zip(DiagnosticStation, fields):
            plan = plan_diagnostic_position_change(station, 1)
            self.assertEqual(plan.patch, (field_name, 8.98))
            self.assertEqual(plan.base_cluster, "C9NI6703")
            self.assertEqual(plan.local_mirror, "C9NI6703")
            self.assertEqual(plan.psp_url, "ni.var.psp://localhost/SUPERVISION/C9NI6703")
            self.assertEqual(plan.connection_refnum, 43)
            self.assertTrue(plan.preserves_unmentioned_fields)

    def test_invalid_station_and_noninteger_selectors_fail_closed(self):
        for station in ["T1", 1, None, True]:
            with self.assertRaises(TypeError):
                plan_diagnostic_position_change(station, 0)
        for selector in [True, False, 1.0, "1", None]:
            with self.assertRaises(TypeError):
                plan_diagnostic_position_change(DiagnosticStation.T1, selector)

    def test_unknown_selector_does_not_silently_request_the_native_default_position(self):
        for selector in [-1, 3, 65535, 10 ** 100]:
            with self.assertRaises(ValueError):
                plan_diagnostic_position_change(DiagnosticStation.T1, selector)

    def test_intents_are_immutable_nonexecutable_and_not_physical_readback(self):
        plan = plan_diagnostic_position_change(DiagnosticStation.T1, 0)
        self.assertTrue(plan.external_effects_blocked)
        self.assertFalse(plan.execution_allowed)
        self.assertFalse(plan.establishes_physical_position)
        self.assertFalse(plan.acknowledgement_observed)
        self.assertFalse(plan.sink_order_serialized)
        self.assertFalse(plan.write_error_consumer_observed)
        with self.assertRaises(FrozenInstanceError):
            plan.legacy_command_value = 0
        with self.assertRaises(ValueError):
            replace(plan, execution_allowed=True)

    def test_reset_sequence_is_true_200ms_false_without_an_averaging_count_input(self):
        plan = plan_centroid_average_reset()
        self.assertEqual([step.frame_index for step in plan.steps], [0, 1, 2])
        self.assertEqual([step.node_uid for step in plan.steps], [19732, 22081, 21619])
        self.assertEqual([step.kind for step in plan.steps],
            [ResetStepKind.LOCAL_VARIABLE_WRITE, ResetStepKind.WAIT_BOUNDARY, ResetStepKind.LOCAL_VARIABLE_WRITE])
        self.assertEqual([(s.target, s.value, s.observed_wait_ms) for s in plan.steps],
            [("Init moy CxCy", True, None), (None, None, 200), ("Init moy CxCy", False, None)])
        self.assertFalse(plan.event_new_value_consumed)
        self.assertTrue(plan.frame_order_serialized)

    def test_reset_plan_does_not_claim_a_reader_observed_the_pulse(self):
        plan = plan_centroid_average_reset()
        self.assertFalse(plan.establishes_consumer_reset)
        self.assertFalse(plan.execution_allowed)
        self.assertTrue(plan.external_effects_blocked)
        self.assertIn("not acknowledgement", "\n".join(plan.unresolved_boundaries))
        with self.assertRaises(FrozenInstanceError):
            plan.steps = ()
        with self.assertRaises(ValueError):
            replace(plan, execution_allowed=True)

    def test_all_evidence_artifacts_are_hashed_and_source_drift_is_not_hidden(self):
        artifacts = [SOURCE_LIBRARY, REVIEWED_WORKING_COPY, *LVKIT_CONTEXTS,
                     CENTROID_RESET_EVIDENCE.manual, CENTROID_RESET_EVIDENCE.print_artifact]
        for rule in DIAGNOSTIC_POSITION_RULES:
            artifacts.extend([rule.evidence.manual, *rule.evidence.prints])
            self.assertFalse(rule.evidence.working_copy_matches_evidence_source)
        for artifact in artifacts:
            with self.subTest(path=artifact.path):
                self.assertEqual(hashlib.sha256((self.supervision / artifact.path).read_bytes()).hexdigest().upper(), artifact.sha256)
        self.assertNotEqual(REVIEWED_WORKING_COPY.sha256, EVIDENCE_SOURCE_VI_SHA256)

    def test_saved_context_agreement_is_separate_from_visual_default_disagreement(self):
        for rule in DIAGNOSTIC_POSITION_RULES:
            evidence = rule.evidence
            frame = self.events[0]["frames"][evidence.event_case_index]
            self.assertEqual(frame, self.events[1]["frames"][evidence.event_case_index])
            selector = next(n for n in frame["body"] if n.get("uid") == str(evidence.selector_uid))
            self.assertEqual(selector["selector"]["node"], "Event Data Node")
            self.assertEqual(selector["selector"]["terminal"], "5")
            self.assertEqual([f["label"] for f in selector["frames"]], ["0", "1", "2"])
            self.assertFalse(any(f["is_default"] for f in selector["frames"]))
            self.assertFalse(evidence.parsed_default_detected)
            self.assertEqual(evidence.visible_default_label, "0, Default")
            sources = {int(c["frame"]): float(c["source"]["bare"]) for c in selector["outputs"][0]["cases"]}
            self.assertEqual(sources, dict(DIAGNOSTIC_SELECTOR_VALUES))

    def test_selector_output_not_multiplied_display_is_wired_to_controller_field(self):
        for rule in DIAGNOSTIC_POSITION_RULES:
            evidence = rule.evidence
            nodes = {int(n["uid"]): n for n in self.events[0]["frames"][evidence.event_case_index]["body"]}
            case_output = f"case_{evidence.selector_uid}.out0"
            bundle = nodes[evidence.bundle_uid]
            self.assertEqual([i["terminal"] for i in bundle["inputs"]], ["1", rule.field])
            self.assertEqual(bundle["inputs"][1]["net"]["bare"], case_output)
            multiply = nodes[evidence.display_multiply_uid]
            self.assertEqual({i["net"]["bare"] for i in multiply["inputs"]}, {"10.0", case_output})
            write = nodes[evidence.write_uid]
            self.assertEqual(write["name"], "sharedVariableDynamicWrite")
            self.assertEqual(next(i for i in write["inputs"] if i["terminal"] == "0")["net"]["bare"], "Refnum(43)")
            self.assertEqual(next(i for i in write["inputs"] if i["terminal"] == "4")["net"], bundle["outputs"][0])
            for mismatch in evidence.name_mismatches:
                self.assertEqual(nodes[mismatch.node_uid]["name"], mismatch.parsed_name)
            display_node = nodes[evidence.name_mismatches[0].node_uid]
            self.assertEqual(display_node["inputs"][0]["net"], multiply["outputs"][0])
            write_outputs = {o["bare"] for o in write["outputs"]}
            consumed = {i["net"]["bare"] for n in nodes.values() for i in n.get("inputs", [])}
            self.assertFalse(write_outputs & consumed)

    def test_reset_graph_has_no_shared_variable_write_or_event_value_dependency(self):
        evidence = CENTROID_RESET_EVIDENCE
        frame = self.events[0]["frames"][26]
        self.assertEqual(frame, self.events[1]["frames"][26])
        sequence = next(n for n in frame["body"] if n.get("uid") == str(evidence.sequence_uid))
        self.assertEqual(sequence["scope_kind"], "sequence")
        self.assertEqual([f["label"] for f in sequence["frames"]], ["0", "1", "2"])
        steps = [f["body"][0] for f in sequence["frames"]]
        self.assertEqual([n["uid"] for n in steps], ["19732", "22081", "21619"])
        self.assertEqual([n["inputs"][0]["net"]["bare"] for n in steps], ["True", "200", "False"])
        self.assertEqual([n["name"] for n in steps], ["ID_NI6602_DAQmx", "Wait (ms)", "ID_NI6602_DAQmx"])
        self.assertFalse(any(n.get("name") == "sharedVariableDynamicWrite" for n in walk(frame["body"])))
        self.assertFalse(any(i["net"].get("node") == "Event Data Node"
            for n in walk(frame["body"]) for i in n.get("inputs", [])))

    def test_formal_event_keys_remain_unmapped_in_original_ledger(self):
        evidence_items = [r.evidence for r in DIAGNOSTIC_POSITION_RULES] + [CENTROID_RESET_EVIDENCE]
        for evidence in evidence_items:
            row = next(r for r in self.ledger if r["expected_key_sha256"] == evidence.expected_event_key_sha256)
            self.assertEqual(row["structure_uid"], "5909")
            self.assertEqual(row["frame_index"], evidence.event_case_index)
            self.assertEqual(row["source_vi_sha256"], EVIDENCE_SOURCE_VI_SHA256)
            self.assertEqual(row["mapping_status"], evidence.formal_png_mapping_status)
            self.assertEqual(row["manual_evidence"][0]["sha256"], evidence.manual.sha256)

    def test_new_module_imports_only_pure_standard_library_primitives(self):
        path = self.supervision / "python_reconstruction/src/supervision_reconstruction/domain/diagnostic_events.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {"__future__", "dataclasses", "enum"})
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))

    def test_main_vi_stub_still_refuses_execution(self):
        from supervision_reconstruction.catalog.vi_0_sup_elyse import reconstruct
        with self.assertRaises(NotImplementedError):
            reconstruct()
