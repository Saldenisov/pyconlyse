"""Non-actuating Page HT display projection checks."""

import unittest

from DeviceServers.control.elyse_acq.supervision_status import (
    project_fluides_raw_display_flags,
    project_modulator_stage_ok_from_eps,
    project_ht_display_flags,
    project_radioprotection_display_flags,
    radioprotection_graph_summary,
)


class SupervisionHtStatusTests(unittest.TestCase):
    def test_each_page_ht_flag_copies_its_c4_input_without_inversion(self):
        expected = {
            "V HT": 35,
            "I HT": 36,
            "Radioprotection": 46,
            "Relais 1 HT": 37,
            "Relais 2 HT": 32,
            "HT en marche": 48,
            "HT en défaut": 49,
        }
        self.assertEqual(
            project_ht_display_flags([False] * 64),
            {name: False for name in expected},
        )
        for name, index in expected.items():
            bank = [False] * 64
            bank[index] = True
            with self.subTest(name=name, index=index):
                self.assertEqual(
                    project_ht_display_flags(bank),
                    {field: field == name for field in expected},
                )

    def test_snapshot_size_and_boolean_type_are_required(self):
        for bank in ([False] * 63, [False] * 65, [False] * 63 + [1]):
            with self.subTest(size=len(bank)):
                with self.assertRaises(ValueError):
                    project_ht_display_flags(bank)

    def test_each_radioprotection_field_copies_one_raw_c4_bit(self):
        expected = {
            "Porte lourde": 53,
            "Porte légére": 52,
            "Porte de Secours": 54,
            "Porte Laser": 55,
            "Rondiers": 60,
            "Occulteur LASER": 63,
            "BACO-TIR EN/HORS": 62,
            "BACO PA/MOD": 61,
            "RONDIER 1": 57,
            "RONDIER 2": 58,
            "RONDIER 3": 59,
            "ARRETS D'URGENCE": 56,
        }
        self.assertEqual(
            project_radioprotection_display_flags([False] * 64),
            {name: False for name in expected},
        )
        for name, index in expected.items():
            bank = [False] * 64
            bank[index] = True
            with self.subTest(name=name, index=index):
                self.assertEqual(
                    project_radioprotection_display_flags(bank),
                    {field: field == name for field in expected},
                )

    def test_radioprotection_projection_rejects_malformed_snapshots(self):
        for bank in ([False] * 63, [False] * 65, [False] * 63 + [1]):
            with self.subTest(size=len(bank)):
                with self.assertRaises(ValueError):
                    project_radioprotection_display_flags(bank)

    def test_graph_summary_matches_all_4096_page_boolean_snapshots(self):
        fields = (
            "Porte lourde", "Porte légére", "Porte de Secours", "Porte Laser",
            "Rondiers", "Occulteur LASER", "BACO-TIR EN/HORS", "BACO PA/MOD",
            "RONDIER 1", "RONDIER 2", "RONDIER 3", "ARRETS D'URGENCE",
        )
        positive_mask = sum(1 << index for index in (0, 1, 2, 3, 7, 11))
        inverted_mask = sum(1 << index for index in (4, 6))
        for mask in range(1 << len(fields)):
            page = {name: bool(mask & (1 << index)) for index, name in enumerate(fields)}
            expected = (mask & positive_mask) == positive_mask and not (mask & inverted_mask)
            with self.subTest(mask=mask):
                self.assertIs(radioprotection_graph_summary(page), expected)

    def test_graph_summary_rejects_missing_or_non_boolean_fields(self):
        page = project_radioprotection_display_flags([False] * 64)
        missing = dict(page)
        missing.pop("RONDIER 1")
        wrong_type = dict(page)
        wrong_type["RONDIER 1"] = 1
        extra = dict(page)
        extra["unexpected"] = False
        for invalid in (missing, wrong_type, extra):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    radioprotection_graph_summary(invalid)


class SupervisionFluidesStatusTests(unittest.TestCase):
    def test_each_page_fluides_flag_copies_one_raw_input(self):
        c3_fields = {
            "Canon 220V": 0,
            "Canon Défauts": 1,
            "Canon Pressostat": 4,
            "Section 220V": 6,
            "Section Défauts": 7,
            "Section Pressostat": 10,
        }
        c4_fields = {
            "Canon débimètre": 19,
            "Section débimètre": 38,
            "Résistivité": 39,
        }
        expected_names = set(c3_fields) | set(c4_fields)
        self.assertEqual(
            project_fluides_raw_display_flags([False] * 56, [False] * 64),
            {name: False for name in expected_names},
        )
        for name, index in c3_fields.items():
            c3 = [False] * 56
            c3[index] = True
            with self.subTest(bank="C3", name=name):
                self.assertEqual(
                    project_fluides_raw_display_flags(c3, [False] * 64),
                    {field: field == name for field in expected_names},
                )
        for name, index in c4_fields.items():
            c4 = [False] * 64
            c4[index] = True
            with self.subTest(bank="C4", name=name):
                self.assertEqual(
                    project_fluides_raw_display_flags([False] * 56, c4),
                    {field: field == name for field in expected_names},
                )

    def test_fluides_rejects_malformed_raw_banks(self):
        for c3, c4 in (
            ([False] * 55, [False] * 64),
            ([False] * 55 + [1], [False] * 64),
            ([False] * 56, [False] * 63),
            ([False] * 56, [False] * 63 + [1]),
        ):
            with self.subTest(c3=len(c3), c4=len(c4)):
                with self.assertRaises(ValueError):
                    project_fluides_raw_display_flags(c3, c4)


class SupervisionModulatorStageOkTests(unittest.TestCase):
    def test_each_indicator_copies_only_its_eps_software_flag(self):
        expected = {
            "GENERAL MOD OK": 8,
            "CHAUFFAGE OK": 14,
            "PREMA OK": 20,
            "RELAIS HT OK": 26,
            "FOCALES OK": 32,
        }
        self.assertEqual(
            project_modulator_stage_ok_from_eps([False] * 77),
            {name: False for name in expected},
        )
        for name, index in expected.items():
            eps = [False] * 77
            eps[index] = True
            with self.subTest(name=name):
                self.assertEqual(
                    project_modulator_stage_ok_from_eps(eps),
                    {field: field == name for field in expected},
                )

    def test_indicator_projection_rejects_malformed_eps(self):
        for eps in ([False] * 76, [False] * 78, [False] * 76 + [1]):
            with self.subTest(length=len(eps)):
                with self.assertRaises(ValueError):
                    project_modulator_stage_ok_from_eps(eps)


if __name__ == "__main__":
    unittest.main()
