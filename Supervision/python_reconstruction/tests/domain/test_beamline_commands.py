import hashlib
import csv
from dataclasses import replace
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.beamline_commands import (
    AdjustmentAction,
    BeamLine,
    DEVIATED_CHANNEL_RULES,
    DEVIATED_EVIDENCE,
    DIRECT_CHANNEL_RULES,
    DIRECT_EVIDENCE,
    NON_SETPOINT_SELECTOR_VALUES,
    OBSERVED_ANALOG_WRITE_BOUNDARY,
    ControllerField,
    plan_beamline_adjustment,
    validate_beamline_adjustment_plan,
)


class BeamLineCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.description_path = (
            cls.supervision
            / "analysis"
            / "lvkit_eval"
            / "batch_0_8_4_minimal_vilib"
            / "descriptions"
            / "0_SUP_ELYSE.json"
        )
        cls.description = json.loads(cls.description_path.read_text(encoding="utf-8"))
        with (cls.supervision / "analysis" / "expected_selector_frame_ledger.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            cls.ledger_rows = list(csv.DictReader(handle))
        with (cls.supervision / DIRECT_EVIDENCE.crosswalk_path).open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            cls.crosswalk_rows = list(csv.DictReader(handle))
        cls.scopes = {}

        def walk(value: object) -> None:
            if isinstance(value, dict):
                if value.get("kind") == "scope":
                    cls.scopes[int(value["uid"])] = value
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(cls.description["body"])

    def test_channel_inventory_and_controller_fields_are_exact(self) -> None:
        self.assertEqual(
            [rule.legacy_name for rule in DIRECT_CHANNEL_RULES],
            [
                "Dipôle 1",
                "Focale",
                "Phase HF / Laser",
                "Correcteur H1",
                "Correcteur V1",
                "Correcteur H2",
                "Correcteur V2",
                "Triplet 1-1",
                "Triplet 1-2",
                "Correcteur H3",
                "Correcteur V3",
            ],
        )
        self.assertEqual(
            [rule.legacy_name for rule in DEVIATED_CHANNEL_RULES],
            [
                "Quadrupôle 1",
                "Quadrupôle 2",
                "Triplet 2-1",
                "Triplet 2-2",
                "Correcteur H4",
                "Correcteur V4",
                "Dipôle 2",
                "Correcteur H5",
                "Correcteur V5",
            ],
        )
        self.assertEqual(DIRECT_CHANNEL_RULES[2].destination.observed_variable, "C8NI6703")
        self.assertEqual(DEVIATED_CHANNEL_RULES[6].destination.observed_variable, "C7NI6703")
        self.assertEqual(DEVIATED_CHANNEL_RULES[7].destination.legacy_field, "08 OUT08 b33 Réserve")
        self.assertEqual(
            DIRECT_CHANNEL_RULES[1].crosswalk_status,
            "LABEL_MISMATCH_VERIFY_MEANING",
        )
        self.assertFalse(DIRECT_CHANNEL_RULES[1].crosswalk_label_match)
        self.assertEqual(
            DEVIATED_CHANNEL_RULES[7].crosswalk_status,
            "SCHEMA_RESERVE_UNVERIFIED_ACTUATOR",
        )
        self.assertFalse(DEVIATED_CHANNEL_RULES[7].crosswalk_label_match)
        self.assertEqual(NON_SETPOINT_SELECTOR_VALUES, (0, 1, 16))

    def test_four_actions_use_evidenced_step_sizes_and_clamp(self) -> None:
        normal = plan_beamline_adjustment(
            BeamLine.DIRECT,
            0,
            AdjustmentAction.SMALL_INCREASE,
            False,
            1.0,
        )
        self.assertEqual(normal.step, 0.01)
        self.assertEqual(normal.coerced_setpoint, 1.01)

        x10 = plan_beamline_adjustment(
            BeamLine.DIRECT,
            1,
            AdjustmentAction.LARGE_DECREASE,
            True,
            50.0,
        )
        self.assertEqual(x10.step, 10.0)
        self.assertEqual(x10.coerced_setpoint, 40.0)

        phase_fine_x10 = plan_beamline_adjustment(
            BeamLine.DIRECT,
            2,
            AdjustmentAction.SMALL_INCREASE,
            True,
            100.0,
        )
        self.assertEqual(phase_fine_x10.step, 5.0)
        self.assertEqual(phase_fine_x10.coerced_setpoint, 105.0)

        clamped = plan_beamline_adjustment(
            BeamLine.DEVIATED,
            4,
            AdjustmentAction.LARGE_INCREASE,
            True,
            4.5,
        )
        self.assertEqual(clamped.requested_setpoint, 5.5)
        self.assertEqual(clamped.coerced_setpoint, 5.0)
        self.assertTrue(clamped.was_coerced)

    def test_every_rule_action_x10_and_clamp_combination(self) -> None:
        for beam_line, rules in (
            (BeamLine.DIRECT, DIRECT_CHANNEL_RULES),
            (BeamLine.DEVIATED, DEVIATED_CHANNEL_RULES),
        ):
            for rule in rules:
                midpoint = (rule.minimum + rule.maximum) / 2.0
                for action in AdjustmentAction:
                    for x10_selected in (False, True):
                        plan = plan_beamline_adjustment(
                            beam_line,
                            rule.index,
                            action,
                            x10_selected,
                            midpoint,
                        )
                        step_pair = (
                            rule.large_step
                            if action in (
                                AdjustmentAction.LARGE_DECREASE,
                                AdjustmentAction.LARGE_INCREASE,
                            )
                            else rule.small_step
                        )
                        expected_step = step_pair[1 if x10_selected else 0]
                        direction = -1.0 if action in (
                            AdjustmentAction.LARGE_DECREASE,
                            AdjustmentAction.SMALL_DECREASE,
                        ) else 1.0
                        self.assertEqual(plan.step, expected_step)
                        self.assertEqual(
                            plan.requested_setpoint,
                            midpoint + direction * expected_step,
                        )
                        validate_beamline_adjustment_plan(plan)

                        edge = rule.minimum if direction < 0 else rule.maximum
                        clamped = plan_beamline_adjustment(
                            beam_line,
                            rule.index,
                            action,
                            x10_selected,
                            edge,
                        )
                        self.assertEqual(clamped.coerced_setpoint, edge)
                        self.assertTrue(clamped.was_coerced)
                        validate_beamline_adjustment_plan(clamped)

    def test_plan_retains_timing_write_boundary_and_denies_execution(self) -> None:
        plan = plan_beamline_adjustment(
            BeamLine.DEVIATED,
            6,
            AdjustmentAction.SMALL_DECREASE,
            False,
            0.0,
        )
        self.assertEqual(plan.evidence, DEVIATED_EVIDENCE)
        self.assertEqual(plan.momentary_button_reset_after_ms, 70)
        self.assertEqual(plan.sve_refresh_wait_ms, 100)
        self.assertEqual(plan.observed_full_cluster_write_boundary, OBSERVED_ANALOG_WRITE_BOUNDARY)
        self.assertFalse(plan.ordering_within_write_boundary_proven)
        self.assertTrue(plan.external_effects_blocked)
        self.assertTrue(plan.manual_approval_required)
        self.assertFalse(plan.implementation_allowed)
        self.assertFalse(plan.adapter_use_allowed)
        self.assertIn("acknowledgement", "\n".join(plan.unresolved_boundaries))

        focale = plan_beamline_adjustment(
            BeamLine.DIRECT,
            1,
            AdjustmentAction.SMALL_INCREASE,
            False,
            10.0,
        )
        self.assertEqual(focale.crosswalk_status, "LABEL_MISMATCH_VERIFY_MEANING")
        self.assertFalse(focale.crosswalk_label_match)
        self.assertIn("Solénoïde", "\n".join(focale.unresolved_boundaries))

        h5 = plan_beamline_adjustment(
            BeamLine.DEVIATED,
            7,
            AdjustmentAction.SMALL_INCREASE,
            False,
            0.0,
        )
        self.assertEqual(h5.crosswalk_status, "SCHEMA_RESERVE_UNVERIFIED_ACTUATOR")
        self.assertFalse(h5.crosswalk_label_match)
        self.assertIn("Réserve", "\n".join(h5.unresolved_boundaries))

    def test_validator_rejects_mutated_route_and_safety_gates(self) -> None:
        plan = plan_beamline_adjustment(
            BeamLine.DIRECT,
            0,
            AdjustmentAction.SMALL_INCREASE,
            False,
            0.0,
        )
        validate_beamline_adjustment_plan(plan)
        mutations = (
            replace(plan, external_effects_blocked=False),
            replace(plan, manual_approval_required=False),
            replace(plan, implementation_allowed=True),
            replace(plan, adapter_use_allowed=True),
            replace(plan, crosswalk_status="UNREVIEWED"),
            replace(plan, controller_patch=ControllerField("C9NI6703", "wrong")),
        )
        for mutation in mutations:
            with self.assertRaises(ValueError):
                validate_beamline_adjustment_plan(mutation)

    def test_invalid_or_ambiguous_inputs_fail_closed(self) -> None:
        calls = (
            lambda: plan_beamline_adjustment("direct", 0, AdjustmentAction.SMALL_INCREASE, False, 0.0),
            lambda: plan_beamline_adjustment(BeamLine.DIRECT, True, AdjustmentAction.SMALL_INCREASE, False, 0.0),
            lambda: plan_beamline_adjustment(BeamLine.DIRECT, 11, AdjustmentAction.SMALL_INCREASE, False, 0.0),
            lambda: plan_beamline_adjustment(BeamLine.DIRECT, 0, 512, False, 0.0),
            lambda: plan_beamline_adjustment(BeamLine.DIRECT, 0, AdjustmentAction.SMALL_INCREASE, 1, 0.0),
            lambda: plan_beamline_adjustment(BeamLine.DIRECT, 0, AdjustmentAction.SMALL_INCREASE, False, float("nan")),
        )
        for call in calls:
            with self.assertRaises((TypeError, IndexError, ValueError)):
                call()

    def test_saved_lvkit_and_manual_evidence_match_model_identities(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.description_path.read_bytes()).hexdigest().upper(),
            "AA620AA9E6FE4312F555A4C5A096B51EE54FE5F34214EE17DDBF9CC2822B8710",
        )
        event = self.scopes[5909]
        self.assertEqual(event["frames"][19]["label"], '[19] "Voie directe": Value Change')
        self.assertEqual(event["frames"][20]["label"], '[20] "Voie déviée": Value Change')

        for evidence, action_labels in (
            (
                DIRECT_EVIDENCE,
                ["0", "1", "16", "128", "256", "512", "1024"],
            ),
            (
                DEVIATED_EVIDENCE,
                ["0", "1", "16", "128", "256", "512", "1024"],
            ),
        ):
            self.assertEqual(
                [frame["label"] for frame in self.scopes[evidence.sequence_uid]["frames"]],
                ["0", "1", "2", "3"],
            )
            self.assertEqual(
                [frame["label"] for frame in self.scopes[evidence.action_selector_uid]["frames"]],
                action_labels,
            )
            screenshot = self.supervision / evidence.screenshot
            self.assertEqual(hashlib.sha256(screenshot.read_bytes()).hexdigest().upper(), evidence.screenshot_sha256)
            source_library = self.supervision / evidence.source_library_path
            self.assertEqual(
                hashlib.sha256(source_library.read_bytes()).hexdigest().upper(),
                evidence.source_library_sha256,
            )
            source_vi = (
                self.supervision
                / "extracted"
                / "PILOTAGE_ELYSE_SUP"
                / "SUPERVISION_VIs"
                / "0_SUP_ELYSE.vi"
            )
            self.assertEqual(
                hashlib.sha256(source_vi.read_bytes()).hexdigest().upper(),
                evidence.reviewed_extracted_copy_sha256,
            )
            self.assertFalse(evidence.extracted_copy_matches_evidence_source)
            self.assertNotEqual(evidence.reviewed_extracted_copy_sha256, evidence.source_vi_sha256)

            ledger_row = next(
                row
                for row in self.ledger_rows
                if row["expected_key_sha256"] == evidence.expected_key_sha256
            )
            self.assertEqual(ledger_row["structure_uid"], "5909")
            self.assertEqual(ledger_row["frame_index"], str(evidence.event_case_index))
            self.assertEqual(ledger_row["source_vi_sha256"], evidence.source_vi_sha256)
            self.assertEqual(ledger_row["mapping_status"], evidence.formal_png_mapping_status)
            self.assertIn(evidence.screenshot_sha256, ledger_row["manual_evidence"])

            crosswalk = self.supervision / evidence.crosswalk_path
            self.assertEqual(
                hashlib.sha256(crosswalk.read_bytes()).hexdigest().upper(),
                evidence.crosswalk_sha256,
            )
            for relative_path, expected_hash in evidence.print_assets:
                print_asset = self.supervision / relative_path
                self.assertEqual(
                    hashlib.sha256(print_asset.read_bytes()).hexdigest().upper(),
                    expected_hash,
                )

        description_text = json.dumps(self.description, ensure_ascii=False)
        for rule in DIRECT_CHANNEL_RULES + DEVIATED_CHANNEL_RULES:
            self.assertIn(rule.destination.legacy_field, description_text)

    def test_crosswalk_rows_exactly_match_all_twenty_rules(self) -> None:
        expected = set()
        for beam_line, event, evidence, rules in (
            (BeamLine.DIRECT, "19", DIRECT_EVIDENCE, DIRECT_CHANNEL_RULES),
            (BeamLine.DEVIATED, "20", DEVIATED_EVIDENCE, DEVIATED_CHANNEL_RULES),
        ):
            print_names = tuple(Path(path).name for path, _ in evidence.print_assets)
            for rule in rules:
                field_parts = rule.destination.legacy_field.split()
                bank_index = str(int(field_parts[0]))
                card_field = " ".join(field_parts[3:])
                card_number = rule.destination.observed_variable[1]
                expected.add(
                    (
                        beam_line.value,
                        event,
                        f"{rule.legacy_name}.Consigne",
                        rule.destination.observed_variable,
                        bank_index,
                        card_field,
                        f"/{card_number}/ao{bank_index}",
                        rule.crosswalk_status,
                        print_names[0],
                        print_names[1],
                    )
                )

        actual = {
            (
                row["line"],
                row["event"],
                row["ui_setpoint"],
                row["psp_bank"],
                row["bank_index"],
                row["card_field"],
                row["physical_channel"],
                row["status"],
                row["frame1_print"],
                row["frame2_psp_print"],
            )
            for row in self.crosswalk_rows
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
