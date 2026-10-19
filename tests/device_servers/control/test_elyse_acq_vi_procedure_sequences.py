"""Pure procedure plans preserve frame boundaries, field retention and ramps."""

import ast
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

from DeviceServers.control.elyse_acq.vi_simulation import procedure_sequences as model


def snapshots():
    return {
        bank: tuple(
            float(i + 100) if kind is float else bool(i % 2) for i in range(count)
        )
        for bank, (count, kind) in model.BANK_SHAPES.items()
    }


class ProcedureProjectionTests(unittest.TestCase):
    def test_all_23_newval_gates_and_frame_counts(self):
        self.assertEqual(len(model.PROCEDURES), 23)
        self.assertEqual(sum(map(len, model.PROCEDURES.values())), 159)
        self.assertEqual(len(model.all_phases()), 166)
        for event, phases in model.PROCEDURES.items():
            with self.subTest(event=event):
                self.assertEqual(model.plan_procedure(event, True), phases)
                self.assertEqual(model.plan_procedure(event, False), ())

    def test_every_frame_only_changes_named_fields_and_leaves_inputs_untouched(self):
        state = snapshots()
        before = dict(state)
        for uid, effects in model.all_phases():
            with self.subTest(diagram=uid):
                result = model.project_frame(uid, state)
                for bank, values in result.local_writes:
                    changes = dict(
                        next(e[2] for e in effects if e[:2] == ("write", bank))
                    )
                    if bank == 35:
                        self.assertIs(values, True)
                        continue
                    for index, value in enumerate(values):
                        self.assertEqual(value, changes.get(index, state[bank][index]))
                self.assertEqual(state, before)
                self.assertEqual(
                    result.wait_requests_ms,
                    tuple(e[1] for e in effects if e[0] == "wait"),
                )
                self.assertEqual(
                    result.subsequence_requests,
                    tuple(e[1] for e in effects if e[0] == "subsequence"),
                )

    def test_focal_29000_and_1500_waits_and_different_error_routes(self):
        focal = model.project_frame("40293", {})
        cells = focal.subsequence_requests[0]
        self.assertEqual([uid for uid, _ in cells], ["46840", "48404", "49054"])
        self.assertEqual(model.project_frame("46840", {}).wait_requests_ms, (29000,))
        self.assertEqual(model.project_frame("49054", {}).wait_requests_ms, (1500,))
        self.assertEqual(
            model.project_frame("53835", {}).call_requests,
            (("call_clear_error", "1_Focales OFF.vi"),),
        )
        self.assertEqual(
            model.project_frame("57312", {}).call_requests,
            (("call_handle_error", "1_Focales OFF.vi"),),
        )

    def test_same_frame_wait_and_write_have_no_invented_order(self):
        result = model.project_frame("53995", snapshots())
        self.assertEqual(result.wait_requests_ms, (150,))
        self.assertTrue(dict(result.local_writes)[15][18])
        self.assertFalse(hasattr(result, "elapsed_ms"))

    def test_ht_reset_republishes_eps_without_a_status_write(self):
        phases = model.plan_procedure(22, True)
        self.assertFalse(
            any(e[:2] == ("write", 44) for _, effects in phases for e in effects)
        )
        result = model.project_frame("33438", snapshots())
        self.assertEqual(
            tuple(p[0] for p in result.publication_payloads[0]),
            ("DPS", "EPS", "C4_OUT_DIO96"),
        )
        self.assertEqual(result.publication_payloads[0][1][2], snapshots()[44])

    def test_zero_and_stop_have_different_retained_c7_field_five(self):
        zero = dict(model.project_frame("38812", snapshots()).local_writes)[10]
        stop = dict(model.project_frame("42539", snapshots()).local_writes)[10]
        self.assertEqual(zero[5], 105.0)
        self.assertEqual(stop[5], 0.0)
        self.assertEqual(zero[2], stop[2])
        self.assertEqual(zero[2], 102.0)

    def test_whole_cluster_write_can_overwrite_concurrent_unmodified_field(self):
        old = snapshots()
        result = dict(model.project_frame("54078", old).local_writes)[15]
        current = list(old[15])
        current[31] = not current[31]
        self.assertNotEqual(result[31], current[31])

    def test_all_960_conditioning_iterations_with_independent_decimal_rounding(self):
        for _, effects in model.PROCEDURES[16]:
            for effect in effects:
                if effect[0] != "conditioning_ramp":
                    continue
                _, uid, _, fields, count, seed, step, wait = effect
                oracle = seed
                for iteration in range(count):
                    with localcontext() as context:
                        context.prec = 1200
                        oracle = float(
                            Decimal.from_float(oracle) + Decimal.from_float(step)
                        )
                    values = model.project_conditioning_iteration(
                        uid, iteration, snapshots()[10]
                    )
                    with self.subTest(body=uid, iteration=iteration):
                        for field in fields:
                            self.assertEqual(values[field], oracle)
                        self.assertEqual(values[2], 102.0)
                        self.assertEqual(values[5], 105.0)
                self.assertEqual(wait, 100)

    def test_conditioning_seed_restarts_and_roundoff_not_removed(self):
        self.assertEqual(
            model.project_conditioning_iteration("41875", 0, snapshots()[10])[0], 15.9
        )
        final = model.project_conditioning_iteration("48496", 159, snapshots()[10])[0]
        self.assertNotEqual(final, 160 * 0.1)
        self.assertAlmostEqual(final, 16.0)

    def test_invalid_unreviewed_events_uids_shapes_and_iterations_fail(self):
        for event in (0, 1, 2, True, 99):
            with self.assertRaises(ValueError):
                model.plan_procedure(event, True)
        with self.assertRaises(TypeError):
            model.plan_procedure(20, 1)
        with self.assertRaises(ValueError):
            model.project_frame("unreviewed", {})
        with self.assertRaises(ValueError):
            model.project_frame("54078", {15: (False,)})
        with self.assertRaises(ValueError):
            model.project_frame("54078", {15: (0,) * 32})
        for iteration in (-1, 160, True):
            with self.assertRaises(ValueError):
                model.project_conditioning_iteration(
                    "48496", iteration, snapshots()[10]
                )

    def test_module_has_no_io_imports(self):
        tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(imports, {"__future__", "dataclasses", "types", "typing"})
        self.assertFalse(any(isinstance(n, ast.Import) for n in ast.walk(tree)))

    def test_counter_start_chain_and_42_poll_bound_are_requests_not_execution(self):
        self.assertEqual(
            model.project_frame("45203", {}).counter_requests,
            (("counter_start_clear_chain", 21, (3, 4)),),
        )
        for uid in ("2745", "49233"):
            for iteration in range(42):
                with self.subTest(body=uid, iteration=iteration):
                    self.assertIs(
                        model.counter_poll_should_stop(uid, iteration, False),
                        iteration == 41,
                    )
                    self.assertTrue(
                        model.counter_poll_should_stop(uid, iteration, True)
                    )
        for done in (1, None):
            with self.assertRaises(TypeError):
                model.counter_poll_should_stop("2745", 0, done)

    def test_counter_stop_retains_saved_cross_subsystem_eps_42_assignment(self):
        writes = dict(model.project_frame("41162", snapshots()).local_writes)
        self.assertTrue(writes[44][42])
        self.assertFalse(writes[44][52])
        self.assertEqual(writes[44][55], snapshots()[44][55])
        self.assertEqual(
            model.project_frame("40802", {}).counter_requests,
            (("counter_poll_stop_clear", 21, 3, "2745", 40, 1),),
        )


if __name__ == "__main__":
    unittest.main()
