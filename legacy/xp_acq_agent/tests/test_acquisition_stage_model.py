"""All stage tests are offline; snapshots below are synthetic Booleans."""
import copy
import itertools
import io
import unittest
from unittest.mock import patch

from legacy.xp_acq_agent.elyse_agent.acquisition_stage_model import (
    BANK_SHAPES, EVENTS, StageModel, cooling_flow_trip, load_model,
)


class StageModelTests(unittest.TestCase):
    def setUp(self):
        self.model = load_model()
        self.snapshots = {bank: [bool(i % 2) for i in range(size)]
                          for bank, size in BANK_SHAPES.items()}

    def test_all_sixteen_requests_have_exact_event_and_dps(self):
        self.assertEqual(len(EVENTS), 16)
        self.assertEqual(EVENTS["focales.start"], (15, 10))
        self.assertEqual(EVENTS["relays_ht.start"], (14, 8))
        self.assertEqual(EVENTS["alimentation_ht.start"], (20, 15))
        for name in EVENTS:
            self.assertTrue(self.model.plan(name, True))
            self.assertEqual(self.model.plan(name, False), [])
            permit = self.model.admission(name)
            self.assertFalse(permit["live_control_enabled"])
            self.assertFalse(permit["hardware_shutdown_qualified"])
            self.assertEqual(permit["physical_cooling_permit"], "UNQUALIFIED")

    def test_all_120_frames_preserve_untouched_fields_and_snapshots(self):
        before = copy.deepcopy(self.snapshots)
        self.assertEqual(len(self.model._frames), 120)
        for uid, effects in self.model._frames.items():
            result = self.model.project_frame(uid, self.snapshots)
            self.assertFalse(result["hardware_enabled"])
            self.assertFalse(result["hardware_acknowledged"])
            self.assertFalse(result["frame_effects_ordered"])
            expected = {bank: changes for kind, bank, changes in
                        (e for e in effects if e[0] == "write")}
            for bank, values in result["local_writes"]:
                if bank == 35:
                    self.assertIs(values, True)
                    continue
                changes = dict(expected[bank])
                self.assertEqual(len(values), BANK_SHAPES[bank])
                for i, value in enumerate(values):
                    self.assertIs(value, changes.get(i, before[bank][i]))
        self.assertEqual(self.snapshots, before)

    def test_chauffage_exact_start_stop_and_reset_indices(self):
        start = self.model.plan("chauffage.start")
        self.assertEqual([f[0] for f in start],
                         ["38074", "38157", "38205", "38235", "38295", "38483", "38592"])
        writes = [e for _, effects in start for e in effects if e[0] == "write" and e[1] == 15]
        self.assertEqual(writes, [["write", 15, [[3, True]]], ["write", 15, [[3, False]]],
                                  ["write", 15, [[2, True]]], ["write", 15, [[2, False]]]])
        self.assertEqual(self.model.project_frame("38205", {})["wait_requests_ms"], [3000])
        stop = self.model.plan("chauffage.stop")
        self.assertIn(["write", 15, [[4, False]]], stop[0][1])
        self.assertIn(["write", 15, [[4, True]]], stop[1][1])

    def test_focal_nested_wait_and_helper_are_not_skipped_or_assumed_successful(self):
        nested = self.model.project_frame("40293", {})["nested_frame_uids"]
        self.assertEqual(nested, [["46840", "48404", "49054"]])
        self.assertEqual(self.model.project_frame("46840", {})["wait_requests_ms"], [29000])
        self.assertEqual(self.model.project_frame("49054", {})["wait_requests_ms"], [1500])
        call = self.model.project_frame("48404", {})["helper_boundaries"]
        self.assertEqual(call, [dict(helper="1_Focales ON.vi", error_policy="call_handle_error",
                                     completion="UNSUPPLIED")])
        self.assertEqual(self.model.project_frame("53835", {})["helper_boundaries"][0]["error_policy"],
                         "call_clear_error")
        self.assertEqual(self.model.project_frame("57312", {})["helper_boundaries"][0]["error_policy"],
                         "call_handle_error")

    def test_ht_command_is_not_relay_command_and_publication_order_is_preserved(self):
        self.assertIn(["write", 15, [[18, True]]], self.model.plan("alimentation_ht.start")[0][1])
        self.assertIn(["write", 15, [[16, True]]], self.model.plan("relays_ht.start")[0][1])
        result = self.model.project_frame("54238", self.snapshots)
        self.assertEqual([name for name, bank, values in result["publication_intents"][0]],
                         ["DPS", "EPS", "C4_OUT_DIO96"])

    def test_general_stop_is_not_a_direct_ht_supply_stop(self):
        def c4_changes(frames):
            changes = []
            for _, effects in frames:
                for effect in effects:
                    if effect[0] == "write" and effect[1] == 15:
                        changes.extend(effect[2])
            return changes
        general = c4_changes(self.model.plan("general.stop"))
        self.assertEqual([i for i, v in general], [8, 8, 17, 17, 6, 6, 4, 4, 1, 1])
        self.assertNotIn(19, [i for i, v in general])
        self.assertEqual(c4_changes(self.model.plan("alimentation_ht.stop")), [[19, False], [19, True]])
        # A relay opening might independently cut power; this test proves
        # command indices only, not persistence of actual high voltage.

    def test_publication_is_supplied_read_not_an_assumed_current_write(self):
        result = self.model.project_frame("54238", self.snapshots)
        for name, bank, values in result["publication_intents"][0]:
            self.assertEqual(values, self.snapshots[bank])
            values[0] = not values[0]
        self.assertIs(self.snapshots[15][0], False)
        self.assertIs(self.snapshots[36][0], False)

    def test_eps_ok_is_literal_not_feedback_or_permission(self):
        result = self.model.project_frame("38483", self.snapshots)
        eps = dict(result["local_writes"])[44]
        self.assertIs(eps[14], True)
        self.assertIs(eps[12], False)
        self.assertIs(eps[17], False)
        self.assertFalse(result["hardware_acknowledged"])
        self.assertFalse(self.model.admission("chauffage.start")["live_control_enabled"])

    def test_model_and_plan_are_not_mutable_aliases(self):
        plan = self.model.plan("chauffage.start")
        plan[0][1].clear()
        self.assertTrue(self.model.plan("chauffage.start")[0][1])
        original = copy.deepcopy(self.model._catalog)
        clone = StageModel(original)
        original["procedures"]["chauffage.start"]["frames"].clear()
        self.assertTrue(clone.plan("chauffage.start"))

    def test_rejects_guessed_values_shapes_and_unknown_operations(self):
        for value in (None, 0, 1, "False"):
            with self.assertRaises(ValueError):
                self.model.plan("chauffage.start", value)
            snapshots = copy.deepcopy(self.snapshots)
            snapshots[15][3] = value
            with self.assertRaises(ValueError):
                self.model.project_frame("38074", snapshots)
        with self.assertRaises(ValueError):
            self.model.plan("ht_voltage_12.7kv")
        with self.assertRaises(ValueError):
            self.model.project_frame("NOT_A_FRAME", {})
        with self.assertRaises(KeyError):
            self.model.project_frame("38074", {})

    def test_rejects_unsupported_effects_and_wrong_bank_indices(self):
        for effect in (["hardware_write", 18], ["write", 15, [[32, True]]],
                       ["write", 15, [[3, 1]]], ["call_handle_error", "GUESS.vi"]):
            catalog = copy.deepcopy(self.model._catalog)
            catalog["procedures"]["chauffage.start"]["frames"][0][1].append(effect)
            with self.assertRaises(ValueError):
                StageModel(catalog)

    def test_file_identity_is_checked_before_catalog_use(self):
        with patch("legacy.xp_acq_agent.elyse_agent.acquisition_stage_model.io.open",
                   return_value=io.BytesIO(b'{"hardware_enabled": true}')):
            with self.assertRaisesRegex(ValueError, "catalog identity changed"):
                load_model()

    def test_cooling_guard_all_16_combinations_and_klystron_input_independence(self):
        for a, b, c, d in itertools.product((False, True), repeat=4):
            c4, c3 = [False]*64, [False]*56
            c4[19], c4[38], c3[0], c3[6] = a, b, c, d
            expected = (a or b) and ((not c) or (not d))
            for klystron_value in (False, True):
                for field in (0, 1, 2, 20):
                    c4[field] = klystron_value
                self.assertIs(cooling_flow_trip(c4, c3), expected)

    def test_cooling_guard_rejects_missing_or_coerced_states(self):
        with self.assertRaises(ValueError):
            cooling_flow_trip([], [])
        for value in (None, 0, 1, "False"):
            c4, c3 = [False]*64, [False]*56
            c4[0] = value
            with self.assertRaises(ValueError):
                cooling_flow_trip(c4, c3)


if __name__ == "__main__":
    unittest.main()
