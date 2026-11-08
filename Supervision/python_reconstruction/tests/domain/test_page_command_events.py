from __future__ import annotations

import ast
import hashlib
import json
import runpy
import unittest
import xml.etree.ElementTree as ET
from dataclasses import FrozenInstanceError, replace
from itertools import product
from pathlib import Path

from supervision_reconstruction.domain import page_command_events as model
from supervision_reconstruction.domain.fw102x_errors import ErrorCluster


class PageCommandEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.proof_path = cls.supervision / model.EVIDENCE_PATH
        cls.proof = json.loads(cls.proof_path.read_text(encoding="utf-8"))
        receipt = json.loads(
            (
                cls.supervision / "analysis/lvkit_eval/parser_release_20261003/00.json"
            ).read_text(encoding="utf-8")
        )
        cls.bd = ET.parse(receipt["xml"][0]["path"]).getroot()
        cls.raw = {
            n.get("uid"): n for n in cls.bd.iter() if n.get("class") and n.get("uid")
        }

    @staticmethod
    def clear_dps():
        return dict.fromkeys(model.DPS_FIELDS, False)

    @staticmethod
    def field_map(page):
        return (
            model.ALIMENTATIONS_FIELD_MAP
            if page is model.CommandPage.ALIMENTATIONS
            else model.MODULATOR_FIELD_MAP
        )

    def values(self, page, selected=()):
        return {source: source in selected for source, _ in self.field_map(page)}

    def plan(self, page, selected=(), dps=None):
        return model.plan_page_command_change(
            page, self.clear_dps() if dps is None else dps, self.values(page, selected)
        )

    def test_complete_dps_schema_has_29_booleans_and_matches_original_fp_vctp(self):
        self.assertEqual(len(model.DPS_FIELDS), 29)
        self.assertEqual(len(set(model.DPS_FIELDS)), 29)
        self.assertEqual(
            tuple(f["name"] for f in self.proof["dps_fields"]), model.DPS_FIELDS
        )
        self.assertTrue(self.proof["dps_original_fp_vctp_agree"])
        self.assertEqual(self.proof["dps_control_uid"], 135293)

    def test_all_eight_alimentations_combinations_forward_full_selected_payload(self):
        page = model.CommandPage.ALIMENTATIONS
        names = tuple(s for s, _ in self.field_map(page))
        for states in product((False, True), repeat=3):
            with self.subTest(states=states):
                plan = self.plan(page, tuple(s for s, v in zip(names, states) if v))
                self.assertEqual(plan.evidence.event_index, 17)
                self.assertEqual(
                    plan.patches,
                    tuple((t, v) for (_, t), v in zip(self.field_map(page), states)),
                )
                self.assertEqual(tuple(v for _, v in plan.extracted_newval), states)
                self.assertEqual(plan.wait_ms, 200)
                self.assertTrue(plan.write_intent_observed)

    def test_all_2048_modulator_combinations_are_described_without_arbitration(self):
        page = model.CommandPage.MODULATOR
        names = tuple(s for s, _ in self.field_map(page))
        for states in product((False, True), repeat=11):
            plan = self.plan(page, tuple(s for s, v in zip(names, states) if v))
            self.assertEqual(plan.evidence.event_index, 18)
            self.assertEqual(
                plan.patches,
                tuple((t, v) for (_, t), v in zip(self.field_map(page), states)),
            )
            self.assertFalse(plan.one_hot_arbitration_observed)
            self.assertFalse(plan.execution_allowed)

    def test_each_of_29_flags_blocks_both_pages_including_unrelated_subsystems(self):
        for page, busy_field in product(model.CommandPage, model.DPS_FIELDS):
            with self.subTest(page=page, busy_field=busy_field):
                dps = self.clear_dps()
                dps[busy_field] = True
                plan = self.plan(page, (self.field_map(page)[0][0],), dps)
                self.assertEqual(plan.active_guard_fields, (busy_field,))
                self.assertTrue(plan.discarded_due_to_busy_dps)
                self.assertFalse(plan.write_intent_observed)
                self.assertIsNone(plan.projected_dps)
                self.assertEqual(plan.patches, ())
                self.assertEqual(plan.wait_ms, 0)
                self.assertFalse(plan.queued)
                self.assertTrue(plan.wait_after_guard_completion)

    def test_busy_snapshot_records_all_active_fields_in_schema_order(self):
        dps = dict.fromkeys(reversed(model.DPS_FIELDS), True)
        plan = self.plan(model.CommandPage.MODULATOR, dps=dps)
        self.assertEqual(plan.active_guard_fields, model.DPS_FIELDS)
        self.assertEqual(plan.incoming_dps, tuple((f, True) for f in model.DPS_FIELDS))

    def test_all_false_page_event_still_has_two_write_intents_and_200ms_wait(self):
        for page in model.CommandPage:
            plan = self.plan(page)
            self.assertTrue(plan.write_intent_observed)
            self.assertEqual(dict(plan.projected_dps), self.clear_dps())
            self.assertEqual(len(plan.patches), len(self.field_map(page)))
            self.assertEqual(plan.wait_ms, 200)
            self.assertFalse(plan.local_and_psp_writes_serialized)

    def test_complete_projection_preserves_unselected_fields_and_does_not_mutate_input(
        self,
    ):
        for page in model.CommandPage:
            original = self.clear_dps()
            original_values = self.values(
                page, tuple(s for s, _ in self.field_map(page))
            )
            plan = model.plan_page_command_change(page, original, original_values)
            projected = dict(plan.projected_dps)
            selected = {t for _, t in self.field_map(page)}
            self.assertEqual(set(projected), set(model.DPS_FIELDS))
            self.assertTrue(
                all(projected[n] == (n in selected) for n in model.DPS_FIELDS)
            )
            self.assertEqual(original, self.clear_dps())
            original[model.DPS_FIELDS[0]] = True
            original_values.clear()
            self.assertFalse(dict(plan.incoming_dps)[model.DPS_FIELDS[0]])
            self.assertEqual(len(plan.extracted_newval), len(selected))

    def test_partial_unknown_extra_or_whitespace_normalized_dps_banks_fail_closed(self):
        page = model.CommandPage.ALIMENTATIONS
        for missing in model.DPS_FIELDS:
            dps = self.clear_dps()
            del dps[missing]
            with self.assertRaises(ValueError):
                self.plan(page, dps=dps)
        for dps in (
            {},
            {**self.clear_dps(), "unknown": False},
            {k.strip(): v for k, v in self.clear_dps().items()},
        ):
            with self.assertRaises(ValueError):
                self.plan(page, dps=dps)

    def test_unknown_or_coerced_dps_values_are_not_clear_flags(self):
        for bad in (None, 0, 1, 0.0, "False", [], object()):
            dps = self.clear_dps()
            dps[model.DPS_FIELDS[-1]] = bad
            with self.assertRaises(TypeError):
                self.plan(model.CommandPage.ALIMENTATIONS, dps=dps)

    def test_input_mapping_and_page_enum_are_required(self):
        for bad in (17, "Page Alimentations", None, True):
            with self.assertRaises(TypeError):
                model.plan_page_command_change(bad, self.clear_dps(), {})
        for bad in (None, [], tuple(self.clear_dps().items())):
            with self.assertRaises(TypeError):
                model.plan_page_command_change(model.CommandPage.ALIMENTATIONS, bad, {})

    def test_newval_requires_all_selected_fields_not_a_delta_or_whole_ui_page(self):
        for page in model.CommandPage:
            values = self.values(page)
            for missing in values:
                partial = dict(values)
                del partial[missing]
                with self.assertRaises(ValueError):
                    model.plan_page_command_change(page, self.clear_dps(), partial)
            with self.assertRaises(ValueError):
                model.plan_page_command_change(
                    page, self.clear_dps(), {**values, "readback": False}
                )

    def test_newval_exact_booleans_required_even_on_busy_input(self):
        for page in model.CommandPage:
            for bad in (None, 0, 1, "True", 1.0):
                values = self.values(page)
                values[next(iter(values))] = bad
                for dps in (self.clear_dps(), dict.fromkeys(model.DPS_FIELDS, True)):
                    with self.assertRaises(TypeError):
                        model.plan_page_command_change(page, dps, values)
            with self.assertRaises(TypeError):
                model.plan_page_command_change(page, self.clear_dps(), [])

    def test_error_prefixes_preserve_native_typo_punctuation_and_spaces(self):
        for page in model.CommandPage:
            plan = self.plan(page)
            prefix = ast.literal_eval(
                self.proof["nodes"][str(plan.evidence.concatenate_uid)]["inputs"][0][
                    "net"
                ]["bare"]
            )
            self.assertEqual(prefix, plan.evidence.error_prefix)
            for source in ("", "source", "  texte\nligne", "échec"):
                self.assertEqual(
                    model.project_page_command_error(
                        plan, "old TER", ErrorCluster(True, -42, source)
                    ),
                    prefix + source,
                )

    def test_noerror_and_warning_keep_stored_ter_instead_of_clearing_it(self):
        for page in model.CommandPage:
            for code in (0, 7, -1):
                self.assertEqual(
                    model.project_page_command_error(
                        self.plan(page),
                        "stale TER",
                        ErrorCluster(False, code, "not used"),
                    ),
                    "stale TER",
                )

    def test_busy_branch_has_no_error_result_or_ter_assignment(self):
        for page in model.CommandPage:
            plan = self.plan(page, dps=dict.fromkeys(model.DPS_FIELDS, True))
            self.assertEqual(
                model.project_page_command_error(plan, "stored", None), "stored"
            )
            for error in (ErrorCluster(False, 0, ""), ErrorCluster(True, 1, "error")):
                with self.assertRaises(ValueError):
                    model.project_page_command_error(plan, "stored", error)

    def test_psp_failure_does_not_remove_ungated_local_write_intent(self):
        plan = self.plan(model.CommandPage.ALIMENTATIONS, ("Marche Aimants.",))
        before = plan.projected_dps
        model.project_page_command_error(plan, "", ErrorCluster(True, 1, "failed"))
        self.assertEqual(plan.projected_dps, before)
        self.assertFalse(plan.local_write_conditioned_on_psp_success)
        self.assertTrue(dict(plan.projected_dps)["X Marche alimentation aimant"])

    def test_error_projection_rejects_missing_or_malformed_results(self):
        plan = self.plan(model.CommandPage.MODULATOR)
        for error in (
            None,
            {},
            ErrorCluster(1, 0, ""),
            ErrorCluster(True, True, ""),
            ErrorCluster(True, 0, None),
        ):
            with self.assertRaises(TypeError):
                model.project_page_command_error(plan, "", error)
        for code in (-(2**31) - 1, 2**31):
            with self.assertRaises(ValueError):
                model.project_page_command_error(plan, "", ErrorCluster(True, code, ""))
        for p, ter in ((None, ""), (plan, None)):
            with self.assertRaises(TypeError):
                model.project_page_command_error(p, ter, ErrorCluster(False, 0, ""))

    def test_plans_cannot_opt_into_execution_or_claim_physical_success(self):
        for page in model.CommandPage:
            plan = self.plan(page)
            self.assertFalse(plan.execution_allowed)
            self.assertTrue(plan.external_effects_blocked)
            self.assertFalse(plan.acknowledgement_observed)
            self.assertFalse(plan.establishes_physical_state)
            self.assertFalse(plan.ui_reset_observed)
            self.assertEqual(plan.psp_url, model.PSP_URL)
            self.assertEqual(plan.connection_refnum, 38)
            self.assertEqual(plan.base_cluster, "DPS")
            with self.assertRaises(FrozenInstanceError):
                plan.wait_ms = 0
            with self.assertRaises(ValueError):
                replace(plan, execution_allowed=True)

    def test_pinned_original_receipt_xml_source_contexts_and_12_native_images(self):
        self.assertEqual(
            hashlib.sha256(self.proof_path.read_bytes()).hexdigest().upper(),
            model.EVIDENCE_SHA256,
        )
        self.assertEqual(self.proof["source_vi_sha256"], model.SOURCE_VI_SHA256)
        self.assertEqual(len(self.proof["artifacts"]), 20)
        self.assertEqual(
            sum(a["path"].endswith(".png") for a in self.proof["artifacts"]), 12
        )
        for a in self.proof["artifacts"]:
            path = self.supervision / a["path"]
            with self.subTest(path=path):
                self.assertEqual(path.stat().st_size, a["bytes"])
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest().upper(), a["sha256"]
                )

    def test_evidence_builder_reproduces_without_vi_or_converter_execution(self):
        builder = runpy.run_path(
            str(self.supervision / "analysis/build_page_command_evidence.py")
        )
        self.assertEqual(builder["build_evidence"](), self.proof)
        self.assertFalse(self.proof["generation_or_vi_execution"])
        self.assertFalse(self.proof["full_vi_qualification"])
        self.assertEqual(self.proof["global_png_mapping_status"], "UNMAPPED")
        self.assertEqual([e["index"] for e in self.proof["events"]], [17, 18])
        self.assertTrue(all(e["old_contexts_agree"] for e in self.proof["events"]))

    def assert_wire(self, wires, *terms):
        self.assertTrue(any(set(terms) <= set(w) for w in wires), terms)

    def test_original_dps_local_to_array_or_guard_chain_uses_complete_cluster(self):
        nodes = self.proof["nodes"]
        for page, event in zip(model.CommandPage, self.proof["events"]):
            e = self.plan(page).evidence
            read, array, logical_or, guard = [
                nodes[str(u)]
                for u in (
                    e.dps_read_uid,
                    e.cluster_array_uid,
                    e.or_array_uid,
                    e.guard_uid,
                )
            ]
            self.assertEqual(read["stored_local_name"], "DPS")
            self.assertFalse(read["stored_local_write"])
            self.assertEqual(array["old_description_name"], "Cluster To Array")
            self.assertEqual(logical_or["old_description_name"], "Or Array Elements")
            self.assert_wire(
                event["wires"],
                read["term_uids"][0],
                array["term_uids"][1],
                guard["term_uids"][2],
            )
            self.assert_wire(
                event["wires"], array["term_uids"][0], logical_or["term_uids"][1]
            )
            self.assert_wire(
                event["wires"], logical_or["term_uids"][0], guard["term_uids"][0]
            )

    def test_original_cluster_newval_uses_stored_27_or_65_slot_not_oldval_slot_5(self):
        # Complex Event NewVal slots differ from the scalar-event slot 6.
        nodes = self.proof["nodes"]
        for page, event, slot in zip(
            model.CommandPage, self.proof["events"], ("27", "65")
        ):
            e = self.plan(page).evidence
            data, guard, unbundle = [
                nodes[str(u)] for u in (e.event_data_uid, e.guard_uid, e.unbundle_uid)
            ]
            self.assertEqual(data["term_field_indices"][-2:], ["5", slot])
            self.assert_wire(
                event["wires"], data["term_uids"][-1], guard["term_uids"][1]
            )
            false_frame = self.proof["scopes"][str(e.guard_uid)]["frames"][0]
            self.assert_wire(
                false_frame["wires"],
                guard["tunnel_term_uids"][1][0],
                unbundle["term_uids"][0],
            )

    def test_each_original_selected_field_wire_reaches_exact_dps_drawer_and_two_sinks(
        self,
    ):
        nodes = self.proof["nodes"]
        for page in model.CommandPage:
            e = self.plan(page).evidence
            unbundle, bundle, local, psp, guard, error = [
                nodes[str(u)]
                for u in (
                    e.unbundle_uid,
                    e.bundle_uid,
                    e.dps_write_uid,
                    e.psp_write_uid,
                    e.guard_uid,
                    e.error_case_uid,
                )
            ]
            frame = self.proof["scopes"][str(e.guard_uid)]["frames"][0]
            self.assertEqual(local["stored_local_name"], "DPS")
            self.assertTrue(local["stored_local_write"])
            self.assertEqual(psp["inputs"][0]["net"]["bare"], "Refnum(38)")
            fields = self.field_map(page)
            self.assertEqual(
                tuple(
                    (o["terminal"], i["terminal"])
                    for o, i in zip(unbundle["outputs"], bundle["inputs"][1:])
                ),
                fields,
            )
            self.assertEqual(
                tuple(
                    model.DPS_FIELDS[int(i)] for i in bundle["term_field_indices"][2:]
                ),
                tuple(t for _, t in fields),
            )
            for source, target in zip(
                unbundle["term_uids"][1:], bundle["term_uids"][2:]
            ):
                self.assert_wire(frame["wires"], source, target)
            self.assert_wire(
                frame["wires"], guard["tunnel_term_uids"][2][0], bundle["term_uids"][1]
            )
            self.assert_wire(
                frame["wires"],
                bundle["term_uids"][0],
                local["term_uids"][0],
                psp["term_uids"][4],
            )
            self.assert_wire(frame["wires"], psp["term_uids"][3], error["term_uids"][0])

    def test_wait_is_outside_guard_and_has_200_idle_or_0_busy_source(self):
        nodes = self.proof["nodes"]
        # Shared outer-event input is the original literal U32 200, not a
        # runtime "SVE tempo" setting inferred from its nearby comment.
        self.assertEqual(self.raw["28150"].findtext("dco/ConstValue"), "000000C8")
        parent = next(n for n in self.bd.iter() if n.get("uid") == "6068")
        parent_wires = [
            [t.get("uid") for t in s.find("termList")]
            for s in parent.find("signalList")
        ]
        self.assert_wire(parent_wires, "28150", "40553")
        outer_tunnel = self.raw["40500"]
        self.assertEqual(outer_tunnel.find("termList")[-1].get("uid"), "40553")
        for page, event in zip(model.CommandPage, self.proof["events"]):
            e = self.plan(page).evidence
            guard, wait = [nodes[str(u)] for u in (e.guard_uid, e.wait_uid)]
            self.assertEqual(
                [
                    (c["frame"], c["source"]["bare"])
                    for c in guard["outputs"][0]["cases"]
                ],
                [("False", "200"), ("True", "0")],
            )
            self.assertEqual(wait["old_description_name"], "Wait (ms)")
            self.assert_wire(
                event["wires"], guard["term_uids"][-1], wait["term_uids"][1]
            )
            self.assert_wire(
                event["wires"],
                outer_tunnel.find("termList")[e.event_index].get("uid"),
                guard["term_uids"][3],
            )
            frames = self.proof["scopes"][str(e.guard_uid)]["frames"]
            for frame in frames:
                self.assertNotIn(str(e.wait_uid), [n["uid"] for n in frame["nodes"]])
            self.assert_wire(
                frames[0]["wires"],
                guard["tunnel_term_uids"][3][0],
                guard["tunnel_term_uids"][4][0],
            )
            true_frame = self.raw[str(e.guard_uid)].find("diagramList")[1]
            constant = next(
                n for n in true_frame.iter() if n.find("dco/ConstValue") is not None
            )
            self.assertEqual(constant.findtext("dco/ConstValue"), "0000000000")
            self.assert_wire(
                frames[1]["wires"], constant.get("uid"), guard["tunnel_term_uids"][4][1]
            )

    def test_busy_branch_has_no_local_psp_or_ui_mutation_and_noerror_frame_is_empty(
        self,
    ):
        for page in model.CommandPage:
            e = self.plan(page).evidence
            busy = self.raw[str(e.guard_uid)].find("diagramList")[1]
            self.assertTrue(
                all(n.get("class") in (None, "label") for n in busy.find("zPlaneList"))
            )
            noerror = self.proof["scopes"][str(e.error_case_uid)]["frames"][0]
            self.assertEqual(noerror["nodes"], [])
            self.assertEqual(noerror["wires"], [])

    def test_original_error_source_concat_and_ter_write_chain_preserves_original_name(
        self,
    ):
        nodes = self.proof["nodes"]
        for page in model.CommandPage:
            e = self.plan(page).evidence
            unbundle, concat, ter = [
                nodes[str(u)]
                for u in (e.error_source_uid, e.concatenate_uid, e.ter_write_uid)
            ]
            frame = self.proof["scopes"][str(e.error_case_uid)]["frames"][1]
            self.assertEqual(unbundle["outputs"][0]["terminal"], "source")
            self.assertEqual(ter["stored_local_name"], "TER")
            self.assertTrue(ter["stored_local_write"])
            self.assertNotEqual(ter["old_description_name"], ter["stored_local_name"])
            self.assert_wire(
                frame["wires"], unbundle["term_uids"][1], concat["term_uids"][2]
            )
            self.assert_wire(
                frame["wires"], concat["term_uids"][0], ter["term_uids"][0]
            )

    def test_native_named_field_anchors_do_not_claim_an_alimentations_binary_decoder(
        self,
    ):
        self.assertEqual(
            self.proof["nodes"]["47174"]["term_field_indices"][1:], ["11", "10", "19"]
        )
        self.assertTrue(
            any("no index-order shortcut" in x for x in self.proof["known_limits"])
        )
        self.assertTrue(
            any(
                "binary decoding" in x
                for x in self.plan(
                    model.CommandPage.ALIMENTATIONS
                ).unresolved_boundaries
            )
        )

    def test_domain_has_no_io_sleep_or_dispatch_import_or_executor(self):
        tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(
            imports,
            {"__future__", "collections.abc", "dataclasses", "enum", "fw102x_errors"},
        )
        self.assertFalse(any(isinstance(n, ast.Import) for n in ast.walk(tree)))
        self.assertFalse(
            any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in {"sleep", "open", "eval", "exec", "__import__"}
                for n in ast.walk(tree)
            )
        )


if __name__ == "__main__":
    unittest.main()
