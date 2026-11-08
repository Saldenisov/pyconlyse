"""Validate saved original-source parser receipts without running lvkit or VIs."""

import hashlib
import json
import unittest
from pathlib import Path


class ParserReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.directory = cls.supervision / "analysis/lvkit_eval/parser_release_20261003"
        cls.receipt = json.loads(
            (cls.directory / "receipt.json").read_text(encoding="utf-8")
        )

    def test_all_38_original_members_and_receipts_are_hash_matched(self):
        receipt = self.receipt
        self.assertEqual(receipt["recovered_members"], 38)
        self.assertEqual(receipt["parse_counts"], {"OK": 38})
        self.assertEqual(len(receipt["rows"]), 38)
        for row in receipt["rows"]:
            path = Path(row["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest().upper(), row["sha256"]
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            source = Path(data["source"])
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest().upper(), data["sha256"]
            )
            self.assertEqual(data["fingerprint"], receipt["converter_fingerprint"])

    def test_main_vi_locals_and_defaults_match_native_anchors(self):
        self.assertEqual(self.receipt["identity_qualification"], "PASS")
        self.assertTrue(all(self.receipt["local_checks"].values()))
        self.assertTrue(all(self.receipt["default_checks"].values()))
        main = json.loads((self.directory / "00.json").read_text(encoding="utf-8"))
        self.assertEqual(
            main["sha256"],
            "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B",
        )
        names = {n["uid"]: n["name"] for n in main["graph_locals"]}
        self.assertEqual(
            [names[n] for n in ("53628", "57843", "13401")],
            ["Cmd pos T1", "Cmd pos T2", "Cmd pos T3"],
        )
        self.assertEqual(names["19732"], "Init moy CxCy")
        self.assertEqual(names["57296"], "C9NI6703")

    def test_no_full_vi_replacement_or_generated_execution_is_claimed(self):
        self.assertEqual(self.receipt["full_vi_replacements_verified"], 0)
        self.assertFalse(self.receipt["native_execution"])
        self.assertFalse(self.receipt["hardware_access"])
        self.assertEqual(
            self.receipt["generation_counts"],
            {"REFUSED": 27, "QUARANTINED_TEXT": 10, "BLOCKED_OPAQUE": 1},
        )
        for row in self.receipt["rows"]:
            data = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
            self.assertFalse(data["generated_execution"])
            self.assertFalse(data["behavioral_qualification"])
            self.assertFalse(data["deployable"])

    def test_original_motor_is_parsed_separately_from_changed_working_copy(self):
        data = json.loads(
            (
                self.supervision
                / "analysis/lvkit_eval/parser_motor_release_20261003/receipt.json"
            ).read_text()
        )
        self.assertEqual(
            data["sha256"],
            "4F33F363F0E21F76074CDE926E8439D9BC93947610B55BC42304FAFC2B1EFF3F",
        )
        self.assertEqual(
            hashlib.sha256(Path(data["source"]).read_bytes()).hexdigest().upper(),
            data["sha256"],
        )
        self.assertEqual(data["fingerprint"], self.receipt["converter_fingerprint"])
        self.assertEqual(data["parse"], "OK")
        self.assertEqual(data["generation"], "REFUSED")
        self.assertFalse(data["generated_execution"])
