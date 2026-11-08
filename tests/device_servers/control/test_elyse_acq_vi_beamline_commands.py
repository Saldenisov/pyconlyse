"""Explicit snapshots and no actuating effects in beam-line tail projections."""

import ast
import unittest
from pathlib import Path

from DeviceServers.control.elyse_acq.vi_simulation import beamline_commands as model


def cells(count):
    return tuple(
        (
            True,
            False,
            True,
            False,
            True,
            1000.0 + i,
            -2000.0 - i,
            False,
            True,
            False,
            True,
        )
        for i in range(count)
    )


def banks(indices):
    return {bank: tuple(100.0 * bank + i for i in range(10)) for bank in indices}


class BeamlineCommandTests(unittest.TestCase):
    def test_direct_assigns_eleven_fields_and_preserves_every_other_field(self):
        original = banks((9, 10, 11))
        result = model.project_setpoint_frame(
            1, apply_setpoints=True, cells=cells(11), read_snapshots=original
        )
        self.assertEqual(
            tuple((r.local_index, r.value) for r in result),
            (
                (
                    9,
                    (
                        1003.0,
                        1004.0,
                        1005.0,
                        1006.0,
                        1009.0,
                        1010.0,
                        906.0,
                        907.0,
                        908.0,
                        909.0,
                    ),
                ),
                (
                    10,
                    (
                        1007.0,
                        1008.0,
                        1002.0,
                        1003.0,
                        1004.0,
                        1001.0,
                        1006.0,
                        1007.0,
                        1000.0,
                        1009.0,
                    ),
                ),
                (
                    11,
                    (
                        1100.0,
                        1101.0,
                        1102.0,
                        1103.0,
                        1104.0,
                        1002.0,
                        1106.0,
                        1107.0,
                        1108.0,
                        1109.0,
                    ),
                ),
            ),
        )
        self.assertEqual(original, banks((9, 10, 11)))

    def test_deviated_assigns_nine_fields_including_saved_reserve_channel(self):
        original = banks((9, 10))
        result = model.project_setpoint_frame(
            2, apply_setpoints=True, cells=cells(9), read_snapshots=original
        )
        self.assertEqual(
            tuple((r.local_index, r.value) for r in result),
            (
                (
                    9,
                    (
                        900.0,
                        901.0,
                        902.0,
                        903.0,
                        904.0,
                        905.0,
                        1004.0,
                        1005.0,
                        1007.0,
                        1008.0,
                    ),
                ),
                (
                    10,
                    (
                        1000.0,
                        1001.0,
                        1002.0,
                        1002.0,
                        1003.0,
                        1005.0,
                        1000.0,
                        1001.0,
                        1008.0,
                        1006.0,
                    ),
                ),
            ),
        )
        self.assertEqual(original, banks((9, 10)))

    def test_false_arm_does_not_read_missing_or_invalid_snapshots(self):
        for event in (1, 2):
            self.assertEqual(
                model.project_setpoint_frame(event, apply_setpoints=False), ()
            )
            self.assertEqual(
                model.project_setpoint_frame(
                    event,
                    apply_setpoints=False,
                    cells=object(),
                    read_snapshots=object(),
                ),
                (),
            )

    def test_publication_is_independent_of_false_update_and_uses_fresh_snapshots(self):
        old = banks((9, 10, 11))
        updated = model.project_setpoint_frame(
            1, apply_setpoints=True, cells=cells(11), read_snapshots=old
        )
        fresh = banks((9, 10, 11, 12))
        fresh[9] = (-42.0,) * 10
        for event in (1, 2):
            requests = model.project_publication_frame(event, read_snapshots=fresh)
            self.assertEqual(len(requests), 4)
            for r in requests:
                self.assertEqual(r.payload, fresh[r.local_index])
                self.assertEqual(
                    r.uri,
                    f"ni.var.psp://10.20.30.2/SUPERVISION/C{r.local_index - 3}NI6703",
                )
                self.assertEqual(
                    r.error_handling, "independent Simple Error Handler.vi"
                )
            self.assertNotEqual(requests[0].payload, updated[0].value)

    def test_bank12_is_published_without_being_updated_by_either_true_arm(self):
        for event, count, indices in ((1, 11, (9, 10, 11)), (2, 9, (9, 10))):
            writes = model.project_setpoint_frame(
                event,
                apply_setpoints=True,
                cells=cells(count),
                read_snapshots=banks(indices),
            )
            self.assertNotIn(12, [w.local_index for w in writes])
            self.assertIn(
                12,
                [
                    p.local_index
                    for p in model.project_publication_frame(
                        event, read_snapshots=banks((9, 10, 11, 12))
                    )
                ],
            )

    def test_wait_is_a_request_not_a_delay_or_voltage_settling_claim(self):
        self.assertEqual(model.terminal_wait_ms(1), 100)
        self.assertEqual(model.terminal_wait_ms(2), 100)

    def test_strict_event_and_boolean_fixture_types(self):
        for event in (True, 1.0, "1", 0, 3):
            with self.subTest(event=event), self.assertRaises(ValueError):
                model.project_setpoint_frame(event, apply_setpoints=False)
        for value in (0, 1, "True", None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                model.project_setpoint_frame(1, apply_setpoints=value)

    def test_incomplete_wrong_type_and_cross_phase_snapshots_are_rejected(self):
        bad_cells = (
            cells(10),
            list(cells(11)),
            ((0,) + cells(11)[0][1:],) + cells(11)[1:],
        )
        for snapshot in bad_cells:
            with self.subTest(cells=snapshot), self.assertRaises(TypeError):
                model.project_setpoint_frame(
                    1,
                    apply_setpoints=True,
                    cells=snapshot,
                    read_snapshots=banks((9, 10, 11)),
                )
        for snapshot in (
            None,
            banks((9, 10)),
            banks((9, 10, 11, 12)),
            {9: (0.0,) * 9, 10: (0.0,) * 10, 11: (0.0,) * 10},
            {9: (0,) * 10, 10: (0.0,) * 10, 11: (0.0,) * 10},
        ):
            with self.subTest(banks=snapshot), self.assertRaises(TypeError):
                model.project_setpoint_frame(
                    1, apply_setpoints=True, cells=cells(11), read_snapshots=snapshot
                )
        with self.assertRaises(TypeError):
            model.project_publication_frame(2, read_snapshots=banks((9, 10, 11)))

    def test_model_has_only_in_memory_imports_and_no_effectful_boundary(self):
        tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
        self.assertEqual(
            {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)},
            {"dataclasses", "types"},
        )
        self.assertFalse(any(isinstance(n, ast.Import) for n in ast.walk(tree)))
        self.assertFalse(
            any(
                isinstance(n, ast.Name)
                and n.id
                in {"exec", "eval", "open", "sleep", "socket", "nidaqmx", "pyvisa"}
                for n in ast.walk(tree)
            )
        )


if __name__ == "__main__":
    unittest.main()
