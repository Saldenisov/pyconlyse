import unittest

from supervision_reconstruction.domain.magnet_registry import (
    CurrentLimits, DeviceServerBinding, LegacyCurrentBinding, MagnetEntry,
    MagnetOwner, MagnetRegistry, RouteVerification, candidate_registry,
)
from supervision_reconstruction.service.shadow import InvalidPreview, parse_preview, preview_currents


class ShadowPreviewTests(unittest.TestCase):
    def setUp(self):
        self.registry = candidate_registry()

    def body(self, requests=None, **changes):
        body = {"idempotency_key": "test:1", "expected_revision": self.registry.revision,
                "requests": requests if requests is not None else [{"equipment_id": "H1", "current_a": 1}]}
        body.update(changes)
        return body

    def test_aliases_canonicalize_to_the_same_request(self):
        a = parse_preview(self.registry, self.body())
        b = parse_preview(self.registry, self.body([{"equipment_id": "corrector-h1", "current_a": 1.0}]))
        self.assertEqual(a.canonical_request(), b.canonical_request())

    def test_negative_zero_canonicalizes(self):
        a = parse_preview(self.registry, self.body([{"equipment_id": "H1", "current_a": -0.0}]))
        self.assertEqual(a.currents, (("corrector-h1", 0.0),))

    def test_all_21_candidates_block_with_no_hardware_success(self):
        requests = [{"equipment_id": e.equipment_id, "current_a": 0} for e in self.registry.entries]
        result = preview_currents(self.registry, parse_preview(self.registry, self.body(requests)))
        self.assertEqual((result["state"], result["blocked_count"], result["resolved_count"]),
                         ("PREVIEW_BLOCKED", 21, 0))
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["establishes_command_success"])
        self.assertEqual(result["physical_status"], "NOT_EXECUTED")
        self.assertTrue(all(p["route"] is None for p in result["plans"]))

    def test_invalid_schemas_are_not_journalable(self):
        bad = [None, [], {}, self.body(device="test/psu"), self.body(requests=[]),
               self.body(requests=[{"equipment_id": "H1", "current_a": 1, "slot_id": 5}]),
               self.body(requests=[{"equipment_id": "unknown", "current_a": 1}]),
               self.body(idempotency_key=" "), self.body(idempotency_key="x" * 129),
               self.body(expected_revision=""), self.body(requests="H1")]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(InvalidPreview):
                parse_preview(self.registry, body)

    def test_duplicate_aliases_cannot_address_one_physical_magnet_twice(self):
        with self.assertRaises(InvalidPreview):
            parse_preview(self.registry, self.body([
                {"equipment_id": "H1", "current_a": 1},
                {"equipment_id": "corrector-h1", "current_a": 2}]))

    def test_nonfinite_boolean_string_and_huge_currents_are_rejected(self):
        for value in [True, "1", None, float("nan"), float("inf"), 10 ** 1000]:
            with self.subTest(value=str(value)[:20]), self.assertRaises(InvalidPreview):
                parse_preview(self.registry, self.body([{"equipment_id": "H1", "current_a": value}]))

    def test_stale_registry_revision_blocks_each_plan(self):
        result = preview_currents(self.registry, parse_preview(self.registry, self.body(expected_revision="stale")))
        self.assertIn("REGISTRY_REVISION_MISMATCH", result["plans"][0]["blocked_reasons"])

    def test_synthetic_mixed_owners_resolve_separately_but_never_execute(self):
        ds = MagnetEntry("fixture-ds", "Fixture DS", (), "test", MagnetOwner.DEVICE_SERVER,
            DeviceServerBinding("fixture/psu/offline", 9), RouteVerification.VERIFIED,
            ("Synthetic proof only",), CurrentLimits(-2, 2))
        legacy = MagnetEntry("fixture-legacy", "Fixture legacy", (), "test", MagnetOwner.LEGACY_ACQ,
            LegacyCurrentBinding("FIXTURE_BANK", "current"), RouteVerification.VERIFIED,
            ("Synthetic proof only",), CurrentLimits(-3, 3))
        registry = MagnetRegistry("fixture.v1", (ds, legacy))
        body = self.body([{"equipment_id": ds.equipment_id, "current_a": 1},
                          {"equipment_id": legacy.equipment_id, "current_a": -1}],
                         expected_revision=registry.revision)
        intent = parse_preview(registry, body)
        result = preview_currents(registry, intent, available_equipment=frozenset([ds.equipment_id, legacy.equipment_id]))
        self.assertEqual(result["state"], "PREVIEW_RESOLVED")
        self.assertEqual([p["route"]["owner"] for p in result["plans"]], ["DEVICE_SERVER", "LEGACY_ACQ"])
        self.assertEqual(result["plans"][0]["route"]["slot_id"], 9)
        self.assertFalse(result["execution_allowed"])
        mixed = preview_currents(registry, intent, available_equipment=frozenset([ds.equipment_id]))
        self.assertEqual(mixed["state"], "PREVIEW_MIXED")
        self.assertIsNone(mixed["plans"][1]["route"])
