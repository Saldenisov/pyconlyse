"""Every overlay diagram matches original identity; no automatic closure."""

import csv
import json
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]


class SourceFacetRegisterTests(unittest.TestCase):
    def test_all_29_initializer_descendants_have_facets_without_native_closure(self):
        register = json.loads(
            (REPOSITORY / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
                encoding="utf-8"
            )
        )
        with (REPOSITORY / register["census"]).open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        expected = {
            "188",
            "20362",
            "17607",
            "17949",
            "227",
            "1256",
            "1250",
            "1517",
            "1526",
            "1227",
            "1410",
            "1609",
            "1837",
            "133",
            "2119",
            "2128",
            "2253",
            "2262",
            "1356",
            "76558",
            "76564",
            "21518",
            "74296",
            "7580",
            "14803",
            "24611",
            "25990",
            "33052",
            "17881",
        }
        selected = {
            row["diagram_uid"]
            for row in rows
            if row["vi"] == "0_ACQ_ELYSE.vi"
            and row["scope_path"].startswith("0_ACQ_ELYSE.vi/root/sequence:359[1]")
        }
        self.assertEqual(selected, expected)
        registered = {
            uid
            for group in register["groups"]
            if group["vi"] == "0_ACQ_ELYSE.vi"
            for uid in group["diagram_uids"]
        }
        self.assertTrue(expected <= registered)
        self.assertFalse(register["whole_acquisition_closed"])
        self.assertFalse(register["native_evidence_complete"])

    def test_vendor_facets_remain_separate_and_not_universally_closed(self):
        register = json.loads(
            (
                REPOSITORY / "docs/ELYSE_ACQ_VENDOR_SOURCE_FACETS_2026-10-02.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(register["included_in_original_533_diagram_census"])
        self.assertFalse(register["whole_vendor_protocol_closed"])
        self.assertFalse(register["native_evidence_complete"])
        seen = set()
        for group in register["groups"]:
            self.assertTrue((REPOSITORY / group["validator"]).is_file())
            self.assertEqual(group["native_status"], "not_closed")
            for uid in group["diagram_uids"]:
                identity = (group["vi"], uid)
                self.assertNotIn(identity, seen)
                seen.add(identity)
        self.assertEqual(len(seen), 50)

    def test_each_of_533_named_diagrams_matches_census_without_closure(self):
        register = json.loads(
            (REPOSITORY / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
                encoding="utf-8"
            )
        )
        with (REPOSITORY / register["census"]).open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 533)
        self.assertFalse(register["whole_acquisition_closed"])
        self.assertFalse(register["native_evidence_complete"])
        seen = set()
        for group in register["groups"]:
            self.assertTrue((REPOSITORY / group["validator"]).is_file())
            self.assertEqual(group["native_status"], "not_closed")
            self.assertTrue(group["facets"])
            for uid in group["diagram_uids"]:
                identity = (group["vi"], uid)
                self.assertNotIn(identity, seen)
                seen.add(identity)
                matches = [
                    row for row in rows if (row["vi"], row["diagram_uid"]) == identity
                ]
                self.assertEqual(len(matches), 1, identity)
                self.assertEqual(
                    matches[0]["source_vi_sha256"], group["source_vi_sha256"]
                )
                self.assertEqual(matches[0]["behavioral_coverage"], "UNREVIEWED")
        self.assertEqual(len(seen), 533)

    def test_all533_are_accounted_for_without_promoting_six_dormant_graphs(self):
        register = json.loads(
            (REPOSITORY / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
                encoding="utf-8"
            )
        )
        with (REPOSITORY / register["census"]).open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        faceted = {
            (g["vi"], uid) for g in register["groups"] for uid in g["diagram_uids"]
        }
        excluded = {
            (g["vi"], uid)
            for g in register["static_call_graph_exclusions"]
            for uid in g["diagram_uids"]
        }
        # Dormancy and wire review are independent: both dormant VIs now
        # have bounded facets without becoming reachable root callees.
        self.assertTrue(excluded <= faceted)
        self.assertEqual(len(excluded), 6)
        self.assertEqual(
            faceted | excluded, {(r["vi"], r["diagram_uid"]) for r in rows}
        )
        self.assertEqual(sum(vi == "0_ACQ_ELYSE.vi" for vi, _ in faceted), 475)
        self.assertFalse(register["whole_acquisition_closed"])

    def test_six_dormant_graph_facets_do_not_close_native_or_root_behavior(self):
        register = json.loads(
            (REPOSITORY / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
                encoding="utf-8"
            )
        )
        groups = [
            g
            for g in register["groups"]
            if g["validator"] == "tools/validate_acq_ni6259_dormant.py"
        ]
        self.assertEqual(
            {g["vi"] for g in groups}, {"1_ACQ_INIT_NI6259.vi", "1_ACQ_READ_NI6259.vi"}
        )
        self.assertEqual(sum(len(g["diagram_uids"]) for g in groups), 6)
        self.assertTrue(all(g["native_status"] == "not_closed" for g in groups))
        self.assertFalse(register["whole_acquisition_closed"])
        self.assertFalse(register["native_evidence_complete"])

    def test_cross_indexed_helper_proofs_and_dormant_call_graph_are_reproducible(self):
        import sys

        sys.path.insert(0, str(REPOSITORY / "tools"))
        from validate_acq_helper_source_facets import validate_helpers

        proof = validate_helpers()
        self.assertEqual(proof["cross_indexed_helper_diagrams"], 37)
        self.assertEqual(proof["dormant"]["members_checked"], 17)
        self.assertEqual(proof["dormant"]["static_inbound_calls"], ())
        self.assertFalse(proof["dormant"]["business_logic_translated"])

    def test_frame0_facets_name_all52_checked_graphs_without_native_closure(self):
        register = json.loads(
            (REPOSITORY / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
                encoding="utf-8"
            )
        )
        groups = [
            group
            for group in register["groups"]
            if group["validator"] == "tools/validate_acq_beamline_adjustment.py"
        ]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["diagram_uids"]), 52)
        self.assertTrue({"11087", "19057"} <= set(groups[0]["diagram_uids"]))
        self.assertEqual(groups[0]["native_status"], "not_closed")
        self.assertFalse(register["whole_acquisition_closed"])

    def test_beamline_tail_facets_do_not_close_unreviewed_frame0(self):
        register = json.loads(
            (REPOSITORY / "docs/ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json").read_text(
                encoding="utf-8"
            )
        )
        groups = [
            group
            for group in register["groups"]
            if group["validator"] == "tools/validate_acq_beamline_commands.py"
        ]
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            set(groups[0]["diagram_uids"]),
            {
                "14333",
                "14348",
                "14354",
                "14553",
                "15917",
                "64765",
                "64780",
                "64786",
                "64942",
                "14963",
            },
        )
        self.assertNotIn("11087", groups[0]["diagram_uids"])
        self.assertNotIn("19057", groups[0]["diagram_uids"])
        self.assertFalse(register["whole_acquisition_closed"])


if __name__ == "__main__":
    unittest.main()
