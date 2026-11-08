from __future__ import annotations

import ast
import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from supervision_reconstruction.domain import synchronisation_events as model
from supervision_reconstruction.domain.fw102x_errors import ErrorCluster


class SynchronisationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.proof_path = cls.supervision / model.EVIDENCE_PATH
        cls.proof = json.loads(cls.proof_path.read_text(encoding="utf-8"))

    @staticmethod
    def dps():
        return dict.fromkeys(model.DPS_FIELDS, False)

    def plan(self, changes=(0,), stored=None, dps=None):
        old = [0.0] * 33
        new = [float(i + 1) if i in changes else 0.0 for i in range(33)]
        return model.plan_synchronisation_change(
            self.dps() if dps is None else dps,
            old,
            new,
            stored,
        )

    def test_original_vctp_has_33_dbls_including_selection_and_duplicates(self):
        schema = self.proof["original_cluster_schemas"]["Page Synchronisation"]
        self.assertEqual(len(schema), model.SYNCHRONISATION_FIELD_COUNT)
        self.assertEqual({f["Type"] for f in schema}, {"NumFloat64"})
        self.assertEqual(schema[2]["Label"], schema[3]["Label"])
        self.assertEqual(schema[14]["Label"], schema[15]["Label"])
        self.assertEqual(schema[32]["Label"], model.SELECTION_NUMBER_FIELD)

    def test_each_of_33_single_changes_selects_index_plus_one(self):
        for index in range(33):
            plan = self.plan((index,))
            self.assertEqual(plan.changed_indices, (index,))
            self.assertEqual(plan.final_flash_index, index)
            self.assertEqual(plan.iterations[0].selection_number, index + 1)

    def test_selection_field_itself_can_produce_unclamped_selection_33(self):
        plan = self.plan((32,))
        self.assertEqual(plan.iterations[0].selection_number, 33)
        self.assertFalse(plan.execution_allowed)

    def test_all_changes_are_retained_not_first_only(self):
        plan = self.plan(tuple(range(33)))
        self.assertEqual(plan.changed_indices, tuple(range(33)))
        self.assertEqual(
            tuple(p.selection_number for p in plan.iterations), tuple(range(1, 34))
        )
        self.assertEqual(plan.final_flash_index, 32)

    def test_multi_changes_iterate_in_index_order_and_final_highlight_is_last(self):
        plan = self.plan((30, 4, 9), stored=1)
        self.assertEqual(plan.changed_indices, (4, 9, 30))
        self.assertEqual(plan.final_flash_index, 30)

    def test_zero_change_still_waits_then_uses_explicit_stored_flash_index(self):
        plan = self.plan((), stored=12)
        self.assertEqual(plan.iterations, ())
        self.assertEqual(plan.final_flash_index, 12)
        self.assertEqual(plan.wait_ms, 300)
        self.assertTrue(plan.final_property_intent)
        with self.assertRaises(TypeError):
            self.plan(())

    def test_signed_zero_not_changed_and_tiny_nonzero_is_changed(self):
        old, new = [0.0] * 33, [-0.0] * 33
        plan = model.plan_synchronisation_change(self.dps(), old, new, 1)
        self.assertEqual(plan.changed_indices, ())
        new[3] = 5e-324
        self.assertEqual(
            model.plan_synchronisation_change(self.dps(), old, new).changed_indices,
            (3,),
        )

    def test_every_dps_flag_discards_event_without_wait_or_queue(self):
        for name in model.DPS_FIELDS:
            dps = self.dps()
            dps[name] = True
            plan = self.plan((0, 32), dps=dps)
            self.assertEqual(plan.active_dps_fields, (name,))
            self.assertTrue(plan.discarded_due_to_busy_dps)
            self.assertEqual(plan.iterations, ())
            self.assertEqual(plan.wait_ms, 0)
            self.assertFalse(plan.final_property_intent)
            self.assertFalse(plan.queued)

    def test_busy_branch_does_not_inspect_unread_old_new_or_flash(self):
        dps = self.dps()
        dps[model.DPS_FIELDS[0]] = True
        plan = model.plan_synchronisation_change(dps, None, None)
        self.assertTrue(plan.discarded_due_to_busy_dps)

    def test_iterations_patch_only_selection_from_fresh_local_not_newval(self):
        plan = self.plan((2, 3))
        for iteration in plan.iterations:
            self.assertEqual(iteration.local_base, "Page Synchronisation")
            self.assertEqual(iteration.patched_field, model.SELECTION_NUMBER_FIELD)
            self.assertFalse(iteration.event_numeric_copied_into_payload)
            self.assertEqual(
                iteration.local_sinks, ("Page Synchronisation", "C10-11 NI6602")
            )
            self.assertEqual(iteration.psp_url, model.C1011_PSP_URL)
            self.assertTrue(iteration.psp_error_input_from_highlight_property)
            self.assertFalse(iteration.local_sinks_conditioned_on_psp_success)

    def test_frozen_scope_three_sequence_frames_and_original_local_uids(self):
        scope = self.proof["scopes"]["35757"]
        self.assertEqual(tuple(f["label"] for f in scope["frames"]), ("0", "1", "2"))
        self.assertIn({"uid": "35801", "class": "prim"}, scope["frames"][1]["nodes"])
        nodes = self.proof["nodes"]
        for uid, name, write in (
            (19774, "Page Synchronisation", False),
            (35923, "Page Synchronisation", True),
            (37769, "C10-11 NI6602", True),
            (21948, "N° CO Flash", True),
            (8733, "N° CO Flash", False),
        ):
            self.assertEqual(nodes[str(uid)]["stored_local_name"], name)
            self.assertEqual(nodes[str(uid)]["stored_local_write"], write)
        self.assertEqual(nodes["23628"]["term_field_indices"], [None, None, "32"])

    def test_original_event_inputs_are_old_minus_new_not_reversed(self):
        inputs = self.proof["nodes"]["35269"]["inputs"]
        self.assertEqual(
            {n["terminal"]: n["net"]["terminal"] for n in inputs}, {"x": "4", "y": "5"}
        )

    def test_native_property_names_not_misparsed_short_names(self):
        nodes = self.proof["nodes"]
        self.assertEqual(
            nodes["41566"]["original_properties"], ['"NumText"', '"BGColor"']
        )
        self.assertEqual(
            nodes["40371"]["original_properties"],
            ['"NumText"', '"BGColor"', '"Label"', '"Text"', '"Value"'],
        )
        plan = self.plan()
        self.assertEqual(plan.final_label_property, "Label.Text")
        self.assertEqual(plan.final_value_property, "Value")
        for uid, color in (
            ("41566", plan.iterations[0].highlight_color),
            ("40371", plan.final_background_color),
        ):
            self.assertIn(
                str(color),
                [i["net"]["terminal"] for i in nodes[uid]["inputs"]],
            )
        self.assertFalse(plan.formatter_qualified)
        self.assertFalse(plan.error_aggregation_qualified)

    def test_no_error_requires_actual_supplied_formatted_text_keeps_ter(self):
        plan = self.plan()
        result = model.project_synchronisation_result(
            plan, "old TME", "old TER", ErrorCluster(False, 0, ""), "runtime text"
        )
        self.assertEqual(result.tme, "runtime text")
        self.assertEqual(result.ter, "old TER")
        with self.assertRaises(TypeError):
            model.project_synchronisation_result(
                plan, "old", "old", ErrorCluster(False, 0, "")
            )

    def test_error_retains_tme_appends_source_to_ter_without_psp_inference(self):
        result = model.project_synchronisation_result(
            self.plan(),
            "old TME",
            "old TER",
            ErrorCluster(True, -1, " property source "),
        )
        self.assertEqual(result.tme, "old TME")
        self.assertEqual(
            result.ter, model.SYNCHRONISATION_ERROR_PREFIX + " property source "
        )

    def test_busy_retains_text_and_rejects_nonexistent_runtime_result(self):
        dps = self.dps()
        dps[model.DPS_FIELDS[0]] = True
        plan = self.plan(dps=dps)
        result = model.project_synchronisation_result(plan, "TME", "TER", None)
        self.assertEqual((result.tme, result.ter), ("TME", "TER"))
        with self.assertRaises(ValueError):
            model.project_synchronisation_result(
                plan, "TME", "TER", ErrorCluster(False, 0, "")
            )

    def test_wrong_vector_shape_type_and_nonfinite_values_rejected(self):
        for vector in (
            [],
            [0] * 32,
            [0] * 34,
            {},
            [True] * 33,
            ["0"] * 33,
            [float("nan")] * 33,
            [float("inf")] * 33,
            [10**1000] * 33,
        ):
            with self.assertRaises((TypeError, ValueError)):
                model.plan_synchronisation_change(self.dps(), [0] * 33, vector, 0)

    def test_subtraction_overflow_not_silently_qualified(self):
        with self.assertRaises(ValueError):
            model.plan_synchronisation_change(self.dps(), [1e308] * 33, [-1e308] * 33)

    def test_complete_exact_dps_and_valid_stored_flash_required(self):
        for dps in ({}, {**self.dps(), "Libre X": 1}):
            with self.assertRaises((TypeError, ValueError)):
                self.plan(dps=dps)
        for index in (True, -1, 33, "1"):
            with self.assertRaises((TypeError, ValueError)):
                self.plan((), stored=index)

    def test_inputs_unchanged_and_intents_frozen_without_external_effects(self):
        dps, old, new = self.dps(), [0.0] * 33, [1.0] * 33
        model.plan_synchronisation_change(dps, old, new)
        self.assertEqual(dps, self.dps())
        self.assertEqual(old, [0.0] * 33)
        self.assertEqual(new, [1.0] * 33)
        plan = self.plan()
        with self.assertRaises(FrozenInstanceError):
            plan.wait_ms = 0
        self.assertFalse(plan.execution_allowed)
        self.assertFalse(plan.acknowledgement_observed)
        self.assertTrue(plan.external_effects_blocked)

    def test_frozen_evidence_identity_and_synchronisation_print_range(self):
        from supervision_reconstruction import domain

        self.assertIs(
            domain.plan_synchronisation_change, model.plan_synchronisation_change
        )
        self.assertIn("plan_synchronisation_change", domain.__all__)
        self.assertIn("synchronisation_events", domain.EVENT_CASES[6].boundary)
        self.assertEqual(
            hashlib.sha256(self.proof_path.read_bytes()).hexdigest().upper(),
            model.EVIDENCE_SHA256,
        )
        anchors = {a["path"] for a in self.proof["artifacts"]}
        self.assertTrue(
            all(
                f"analysis/labview_print_hidden_frames/0__SUP__ELYSEd{i}.png" in anchors
                for i in range(211, 221)
            )
        )

    def test_no_io_network_or_runtime_executor_import(self):
        tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
        self.assertEqual(
            {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)},
            {
                "__future__",
                "collections.abc",
                "dataclasses",
                "fw102x_errors",
                "machine_frequency",
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
