from __future__ import annotations

import ast
import hashlib
import json
import runpy
import sys
import unittest
from dataclasses import FrozenInstanceError
from itertools import product
from pathlib import Path

from supervision_reconstruction.domain import parameter_page_events as model
from supervision_reconstruction.domain.fw102x_errors import ErrorCluster


class ParameterPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.proof_path = cls.supervision / model.EVIDENCE_PATH
        cls.proof = json.loads(cls.proof_path.read_text(encoding="utf-8"))

    @staticmethod
    def dps():
        return dict.fromkeys(model.DPS_FIELDS, False)

    @staticmethod
    def rules(page):
        return tuple(r for r in model.PARAMETER_RULES if r.page is page)

    def plan(self, page, mask=0, busy=None, selected=(), numeric=None):
        arrows = {r.arrow: bool(r.mask & mask) for r in self.rules(page)}
        procedures = {s: s in selected for s, _ in model.PROCEDURE_FIELD_MAPS[page]}
        numbers = (
            {
                r.numeric_field: 10.0 if r.limits is None else sum(r.limits) / 2
                for r in self.rules(page)
            }
            if numeric is None
            else numeric
        )
        return model.plan_parameter_page_change(
            page,
            self.dps() if busy is None else busy,
            arrows,
            procedures,
            numbers,
        )

    def test_twenty_rules_have_unique_page_mask_and_native_uids(self):
        from supervision_reconstruction import domain

        self.assertIs(
            domain.plan_parameter_page_change, model.plan_parameter_page_change
        )
        self.assertIn("plan_parameter_page_change", domain.__all__)
        for index in (14, 15, 16):
            self.assertIn("parameter_page_events", domain.EVENT_CASES[index].boundary)
        self.assertEqual(len(model.PARAMETER_RULES), 20)
        self.assertEqual(len({(r.page, r.mask) for r in model.PARAMETER_RULES}), 20)
        for rule in model.PARAMETER_RULES:
            for uid in rule.node_uids:
                if uid is not None:
                    self.assertIn(str(uid), self.proof["nodes"])
            arithmetic, clamp, bundle, psp, read, write, ui, uiwrite, sequence, wait = (
                str(uid) for uid in rule.node_uids
            )
            nodes = self.proof["nodes"]
            self.assertEqual(
                nodes[arithmetic]["old_description_name"],
                "Subtract" if rule.delta < 0 else "Add",
            )
            inputs = nodes[arithmetic]["inputs"]
            self.assertIn(
                abs(rule.delta),
                [
                    float(i["net"]["terminal"])
                    for i in inputs
                    if i["net"]["node"] is None
                ],
            )
            if clamp != "None":
                self.assertEqual(
                    nodes[clamp]["old_description_name"], "In Range and Coerce"
                )
                limits = {
                    i["terminal"]: float(i["net"]["terminal"])
                    for i in nodes[clamp]["inputs"]
                    if i["net"]["node"] is None
                }
                self.assertEqual(
                    (limits["lower limit"], limits["upper limit"]), rule.limits
                )
            self.assertEqual(nodes[psp]["class"], "sharedVariableDynamicWrite")
            self.assertEqual(nodes[read]["stored_local_name"], rule.controller)
            self.assertFalse(nodes[read]["stored_local_write"])
            self.assertEqual(nodes[write]["stored_local_name"], rule.controller)
            self.assertTrue(nodes[write]["stored_local_write"])
            self.assertEqual(nodes[uiwrite]["stored_local_name"], rule.page.value)
            self.assertEqual(nodes[wait]["old_description_name"], "Wait (ms)")
            self.assertIn(sequence, self.proof["scopes"])
            self.assertEqual(nodes[bundle]["class"], "nMux")
            self.assertIn(
                rule.controller_field,
                [item["terminal"] for item in nodes[bundle]["inputs"]],
            )
            self.assertEqual(nodes[ui]["class"], "nMux")

    def test_exact_parameter_names_and_error_prefixes_match_frozen_sources(self):
        for page, outer, masks in (
            (model.ParameterPage.FLUIDES, 38117, 19503),
            (model.ParameterPage.HT, 38758, 39371),
            (model.ParameterPage.HF, 53782, 55903),
        ):
            fields = self.proof["original_cluster_schemas"][page.value]
            names = {f["Label"] for f in fields}
            for rule in self.rules(page):
                self.assertIn(rule.arrow, names)
                self.assertIn(rule.numeric_field, names)
                scope = self.proof["scopes"][str(masks)]
                prefix_output = next(
                    o for o in scope["outputs"] if o["net"].endswith("out1")
                )
                source = next(
                    c["source"]
                    for c in prefix_output["cases"]
                    if c["frame"] == str(rule.mask)
                )
                self.assertEqual(
                    ast.literal_eval(source["terminal"]), rule.error_prefix
                )
            output = self.proof["scopes"][str(outer)]["outputs"][0]
            self.assertEqual(
                ast.literal_eval(output["cases"][0]["source"]["terminal"]),
                model.PROCEDURE_ERROR_PREFIXES[page],
            )

    def test_each_rule_arithmetic_and_named_controller_patch(self):
        for rule in model.PARAMETER_RULES:
            with self.subTest(page=rule.page, mask=rule.mask):
                plan = self.plan(rule.page, rule.mask)
                self.assertEqual(plan.branch, model.ParameterBranch.ADJUSTMENT)
                self.assertAlmostEqual(
                    plan.projected_numeric, plan.incoming_numeric + rule.delta
                )
                self.assertEqual(
                    plan.controller_patch,
                    (rule.controller_field, plan.projected_numeric),
                )
                self.assertEqual(
                    plan.psp_url,
                    f"ni.var.psp://localhost/SUPERVISION/{rule.controller}",
                )
                self.assertEqual(plan.error_prefix, rule.error_prefix)
                self.assertEqual(plan.dps_patches, ())
                self.assertIsNone(plan.projected_dps)

    def test_all_masks_follow_procedure_single_bit_or_default(self):
        for page in model.ParameterPage:
            rules = self.rules(page)
            for mask in range(2 ** len(rules)):
                plan = self.plan(page, mask)
                branch = (
                    model.ParameterBranch.PROCEDURE
                    if mask == 0
                    else model.ParameterBranch.ADJUSTMENT
                    if mask & (mask - 1) == 0
                    else model.ParameterBranch.DEFAULT_NO_OP
                )
                self.assertEqual(plan.mask, mask)
                self.assertEqual(plan.branch, branch)
                if branch is model.ParameterBranch.DEFAULT_NO_OP:
                    self.assertFalse(plan.write_intent_observed)
                    self.assertEqual(plan.ui_patches, ())
                    self.assertEqual(plan.wait_ms, 0)
                    self.assertIsNone(plan.error_prefix)

    def test_each_busy_dps_flag_blocks_procedures_not_any_single_arrow(self):
        for page, field in product(model.ParameterPage, model.DPS_FIELDS):
            dps = self.dps()
            dps[field] = True
            self.assertEqual(
                self.plan(page, busy=dps).branch,
                model.ParameterBranch.BUSY_PROCEDURE_DISCARDED,
            )
            for rule in self.rules(page):
                plan = self.plan(page, rule.mask, busy=dps)
                self.assertEqual(plan.branch, model.ParameterBranch.ADJUSTMENT)
                self.assertTrue(plan.write_intent_observed)
                self.assertEqual(plan.active_dps_fields, (field,))
                self.assertEqual(plan.dps_patches, ())

    def test_original_wires_prove_inner_selector_is_arrow_or_not_dps_or(self):
        for index, arrow, outer, inner in (
            (14, 27087, 38117, 39025),
            (15, 40970, 38758, 39044),
            (16, 58189, 53782, 55624),
        ):
            event = next(e for e in self.proof["events"] if e["index"] == index)
            nodes = self.proof["nodes"]
            arrow_out = nodes[str(arrow)]["term_uids"][0]
            root_wire = next(w for w in event["wires"] if arrow_out in w)
            outer_terms = nodes[str(outer)]
            bridge = next(
                t for t in outer_terms["tunnel_term_uids"] if t[-1] in root_wire
            )
            inner_selector = nodes[str(inner)]["term_uids"][0]
            outer_true = self.proof["scopes"][str(outer)]["frames"][1]
            self.assertIn([bridge[1], inner_selector], outer_true["wires"])

    def test_all_procedure_flag_combinations_forward_selected_payload(self):
        for page in model.ParameterPage:
            fields = model.PROCEDURE_FIELD_MAPS[page]
            for states in product((False, True), repeat=len(fields)):
                selected = tuple(s for (s, _), value in zip(fields, states) if value)
                plan = self.plan(page, selected=selected)
                self.assertEqual(
                    plan.dps_patches,
                    tuple(
                        (target, state) for (_, target), state in zip(fields, states)
                    ),
                )
                self.assertEqual(plan.psp_url, model.DPS_URL)
                self.assertEqual(
                    plan.wait_ms, 200 if page is model.ParameterPage.FLUIDES else 0
                )

    def test_all_false_procedure_payload_still_has_write_intent(self):
        for page in model.ParameterPage:
            plan = self.plan(page)
            self.assertTrue(plan.write_intent_observed)
            self.assertTrue(all(not v for _, v in plan.projected_dps))

    def test_procedures_ignored_when_arrow_present(self):
        for page in model.ParameterPage:
            selected = tuple(s for s, _ in model.PROCEDURE_FIELD_MAPS[page])
            plan = self.plan(page, 1, selected=selected)
            self.assertEqual(plan.dps_patches, ())
            self.assertEqual(plan.timing_control_intents, ())

    def test_limits_clamp_after_addition_and_phase_does_not_wrap(self):
        for rule in model.PARAMETER_RULES:
            if rule.limits is None:
                continue
            low, high = rule.limits
            for supplied, expected in ((low - 1000, low), (high + 1000, high)):
                plan = self.plan(
                    rule.page, rule.mask, numeric={rule.numeric_field: supplied}
                )
                self.assertEqual(plan.projected_numeric, expected)

    def test_fluides_has_no_evidenced_temperature_clamp(self):
        for rule in self.rules(model.ParameterPage.FLUIDES):
            plan = self.plan(rule.page, rule.mask, numeric={rule.numeric_field: -1000})
            self.assertAlmostEqual(plan.projected_numeric, -1000 + rule.delta)
            self.assertIsNone(rule.limits)

    def test_hf_coarse_positive_attenuator_preserves_native_plus_one(self):
        a = self.plan(model.ParameterPage.HF, 4)
        b = self.plan(model.ParameterPage.HF, 8)
        self.assertEqual(a.projected_numeric, b.projected_numeric)
        self.assertEqual(b.rule.delta, 1)

    def test_fluides_section_decrement_keeps_duplicate_and_missing_reset(self):
        plan = self.plan(model.ParameterPage.FLUIDES, 4)
        self.assertEqual(
            tuple(n for n, _ in plan.ui_patches[1:]),
            ("> Canon", "> Canon", "> Section", "< Section"),
        )
        nodes = self.proof["nodes"]["45095"]["inputs"]
        self.assertEqual(sum(n["terminal"] == "> Canon" for n in nodes), 2)
        base = {
            "T° SECTION:": 50.0,
            "> Canon": True,
            "< Canon": True,
            "> Section": True,
            "< Section": True,
            "untouched": "readback",
        }
        projected = model.project_parameter_ui(
            plan, model.ParameterUiBase.LOCAL_PAGE, base
        )
        self.assertTrue(projected["< Canon"])
        self.assertFalse(projected["> Canon"])
        self.assertEqual(projected["untouched"], "readback")
        self.assertEqual(base["T° SECTION:"], 50.0)
        self.assertAlmostEqual(projected["T° SECTION:"], 9.9)

    def test_ui_base_is_fresh_local_for_fluides_newval_for_ht_hf(self):
        for page in model.ParameterPage:
            plan = self.plan(page, 1)
            expected = (
                model.ParameterUiBase.LOCAL_PAGE
                if page is model.ParameterPage.FLUIDES
                else model.ParameterUiBase.EVENT_NEWVAL
            )
            self.assertIs(plan.ui_base, expected)
            base = {n: True if type(v) is bool else 99.0 for n, v in plan.ui_patches}
            base["other"] = 7
            self.assertEqual(
                model.project_parameter_ui(plan, expected, base)["other"], 7
            )
            wrong = next(v for v in model.ParameterUiBase if v is not expected)
            with self.assertRaises(ValueError):
                model.project_parameter_ui(plan, wrong, base)

    def test_ui_base_missing_or_wrong_arrow_fails_closed(self):
        plan = self.plan(model.ParameterPage.HF, 1)
        with self.assertRaises(ValueError):
            model.project_parameter_ui(plan, plan.ui_base, {})
        base = {n: 0 if type(v) is bool else 10 for n, v in plan.ui_patches}
        with self.assertRaises(TypeError):
            model.project_parameter_ui(plan, plan.ui_base, base)

    def test_start_pulse_enables_stop_disables_not_reversed(self):
        for trigger, value, uids in (
            ("Marche pulse MOD", 0, (7002, 67505, 68962, 70250)),
            ("Arrêt pulse MOD", 1, (67577, 67619, 67657, 67698)),
        ):
            plan = self.plan(model.ParameterPage.HT, selected=(trigger,))
            self.assertEqual(
                tuple(p.control for p in plan.timing_control_intents),
                model.TIMING_CONTROLS,
            )
            self.assertEqual(
                tuple(p.property_uid for p in plan.timing_control_intents), uids
            )
            for p in plan.timing_control_intents:
                self.assertEqual(p.disabled_enum, value)
                node = self.proof["nodes"][str(p.property_uid)]
                self.assertEqual(node["properties"][0]["net"]["terminal"], str(value))

    def test_opposing_pulse_flags_are_unordered_conflicting_intents(self):
        plan = self.plan(
            model.ParameterPage.HT, selected=("Marche pulse MOD", "Arrêt pulse MOD")
        )
        self.assertTrue(plan.conflicting_timing_intents)
        self.assertEqual(len(plan.timing_control_intents), 8)
        self.assertTrue(dict(plan.dps_patches)["X Marche impulsion mod"])
        self.assertTrue(dict(plan.dps_patches)["X Arret impulsion mod"])

    def test_wait_gates_ui_reset_not_psp_success_or_controller_sinks(self):
        for rule in model.PARAMETER_RULES:
            plan = self.plan(rule.page, rule.mask)
            self.assertEqual(plan.wait_ms, 200)
            self.assertTrue(plan.ui_reset_after_wait)
            self.assertFalse(plan.wait_orders_controller_writes)
            self.assertFalse(plan.local_write_conditioned_on_psp_success)
            self.assertFalse(plan.acknowledgement_observed)

    def test_busy_procedure_has_no_wait_ui_error_or_queue(self):
        dps = self.dps()
        dps[model.DPS_FIELDS[0]] = True
        for page in model.ParameterPage:
            plan = self.plan(page, busy=dps)
            self.assertEqual(plan.wait_ms, 0)
            self.assertFalse(plan.write_intent_observed)
            self.assertEqual(plan.timing_control_intents, ())
            self.assertFalse(plan.queued)
            self.assertEqual(model.project_parameter_error(plan, "old", None), "old")
            with self.assertRaises(ValueError):
                model.project_parameter_error(plan, "old", ErrorCluster(False, 0, ""))

    def test_error_source_appends_without_rollback_and_no_error_retains_ter(self):
        for page, mask in product(model.ParameterPage, (0, 1)):
            plan = self.plan(page, mask)
            self.assertEqual(
                model.project_parameter_error(
                    plan, "old", ErrorCluster(False, 9, "warn")
                ),
                "old",
            )
            self.assertEqual(
                model.project_parameter_error(
                    plan, "old", ErrorCluster(True, -1, " x ")
                ),
                plan.error_prefix + " x ",
            )
            self.assertTrue(plan.write_intent_observed)
            with self.assertRaises(TypeError):
                model.project_parameter_error(plan, "old", None)

    def test_exact_booleans_complete_banks_and_explicit_page_required(self):
        page = model.ParameterPage.FLUIDES
        arrows = {r.arrow: False for r in self.rules(page)}
        commands = {s: False for s, _ in model.PROCEDURE_FIELD_MAPS[page]}
        for dps in ({}, {**self.dps(), "Libre X": 1}, {**self.dps(), "unknown": False}):
            with self.assertRaises((TypeError, ValueError)):
                model.plan_parameter_page_change(page, dps, arrows, commands, {})
        for invalid in ({}, {**arrows, "< Canon": 1}, {**arrows, "unknown": False}):
            with self.assertRaises((TypeError, ValueError)):
                model.plan_parameter_page_change(
                    page, self.dps(), invalid, commands, {}
                )
        with self.assertRaises(TypeError):
            model.plan_parameter_page_change(
                "Page Fluides", self.dps(), arrows, commands, {}
            )

    def test_selected_missing_nonfinite_or_coerced_numeric_rejected(self):
        for bad in (
            {},
            {"T° CANON:": True},
            {"T° CANON:": "10"},
            {"T° CANON:": float("nan")},
            {"T° CANON:": float("inf")},
            {"T° CANON:": 10**1000},
            {"unknown": 10},
        ):
            with self.assertRaises((TypeError, ValueError)):
                self.plan(model.ParameterPage.FLUIDES, 1, numeric=bad)

    def test_noop_does_not_require_or_validate_unread_numeric(self):
        plan = self.plan(
            model.ParameterPage.HF, 3, numeric={"Cons Atténuateur HF": float("nan")}
        )
        self.assertEqual(plan.branch, model.ParameterBranch.DEFAULT_NO_OP)
        self.assertEqual(
            self.plan(model.ParameterPage.HF, numeric={}).branch,
            model.ParameterBranch.PROCEDURE,
        )

    def test_inputs_not_mutated_and_plan_frozen(self):
        dps = self.dps()
        original = dict(dps)
        plan = self.plan(model.ParameterPage.HT, busy=dps, selected=("Marche HT",))
        self.assertEqual(dps, original)
        with self.assertRaises(FrozenInstanceError):
            plan.mask = 1
        self.assertFalse(plan.execution_allowed)
        self.assertTrue(plan.external_effects_blocked)
        self.assertFalse(plan.establishes_physical_state)

    def test_error_contract_rejects_malformed_clusters(self):
        plan = self.plan(model.ParameterPage.HT)
        for error in (
            ErrorCluster(1, 0, "x"),
            ErrorCluster(False, True, "x"),
            ErrorCluster(False, 0, None),
            ErrorCluster(False, 2**31, "x"),
        ):
            with self.assertRaises((TypeError, ValueError)):
                model.project_parameter_error(plan, "old", error)

    def test_frozen_evidence_and_all_70_artifact_identities(self):
        self.assertEqual(
            tuple(f["Label"] for f in self.proof["original_cluster_schemas"]["DPS"]),
            model.DPS_FIELDS,
        )
        self.assertEqual(
            hashlib.sha256(self.proof_path.read_bytes()).hexdigest().upper(),
            model.EVIDENCE_SHA256,
        )
        self.assertEqual(self.proof["source_vi_sha256"], model.SOURCE_VI_SHA256)
        self.assertEqual(len(self.proof["artifacts"]), 70)
        self.assertEqual(len({a["path"] for a in self.proof["artifacts"]}), 70)
        for item in self.proof["artifacts"]:
            path = self.supervision / item["path"]
            self.assertEqual(path.stat().st_size, item["bytes"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest().upper(), item["sha256"]
            )

    def test_rebuild_matches_frozen_evidence_without_overwriting(self):
        analysis = str(self.supervision / "analysis")
        sys.path.insert(0, analysis)
        try:
            generator = runpy.run_path(
                str(self.supervision / "analysis/build_parameter_event_evidence.py")
            )
            self.assertEqual(generator["build_evidence"](), self.proof)
            with self.assertRaises(FileExistsError):
                generator["main"]()
        finally:
            sys.path.remove(analysis)

    def test_module_has_no_io_network_or_runtime_executor_import(self):
        tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(
            imports,
            {
                "__future__",
                "collections.abc",
                "dataclasses",
                "enum",
                "fw102x_errors",
                "page_command_events",
            },
        )
        self.assertEqual(
            {
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            },
            {"math"},
        )


if __name__ == "__main__":
    unittest.main()
