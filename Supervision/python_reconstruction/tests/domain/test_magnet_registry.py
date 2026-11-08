"""Offline contracts with synthetic commissioned fixtures, never real bindings."""

import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.magnet_registry import (
    CROSSWALK_SHA256, CROSSWALK_SOURCE, LOCAL_ITEST_SHA256, LOCAL_ITEST_SOURCE,
    CurrentLimits, DeviceServerBinding, LegacyCurrentBinding, MagnetEntry,
    MagnetOwner, MagnetRegistry, RouteVerification, candidate_registry,
    legacy_selection_blockers, plan_current_intent, plan_group_currents,
    registry_snapshot,
)
from tools.export_magnet_registry import render_snapshot


class MagnetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = candidate_registry()
        self.ds = MagnetEntry(
            "synthetic-ds", "Synthetic iTest", ("DS alias",), "test",
            MagnetOwner.DEVICE_SERVER, DeviceServerBinding("test/psu/offline", 9),
            RouteVerification.VERIFIED, ("synthetic test verification; not deployed",),
            CurrentLimits(-2, 2),
            LegacyCurrentBinding("TEST_BANK", "retired-current"),
            (LegacyCurrentBinding("TEST_BANK", "retired-current"),),
        )
        self.legacy = MagnetEntry(
            "synthetic-legacy", "Synthetic legacy", (), "test",
            MagnetOwner.LEGACY_ACQ, LegacyCurrentBinding("TEST_BANK", "active-current"),
            RouteVerification.VERIFIED, ("synthetic test verification; not deployed",),
            CurrentLimits(-3, 3),
        )
        self.registry = MagnetRegistry("synthetic.v1", (self.ds, self.legacy))

    def plan(self, name="synthetic-ds", value=1, **kwargs):
        return plan_current_intent(
            self.registry, name, value,
            expected_revision=kwargs.pop("expected_revision", self.registry.revision),
            transport_available=kwargs.pop("transport_available", True), **kwargs,
        )

    def test_inventory_is_21_candidates_not_deployed_registry(self):
        entries = self.candidates.entries
        self.assertEqual(len(entries), 21)
        self.assertEqual(sum(e.owner is MagnetOwner.DEVICE_SERVER for e in entries), 8)
        self.assertEqual(sum(e.owner is MagnetOwner.UNKNOWN for e in entries), 13)
        self.assertFalse(any(e.owner is MagnetOwner.LEGACY_ACQ for e in entries))
        self.assertTrue(all(e.verification is RouteVerification.CANDIDATE for e in entries))
        self.assertTrue(all(e.limits is None for e in entries))
        self.assertFalse(any(e.label == "Phase HF / Laser" for e in entries))

    def test_sparse_itest_ids_match_local_static_config_without_importing_it(self):
        repository = Path(__file__).resolve().parents[4]
        source = repository / LOCAL_ITEST_SOURCE
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest().upper(), LOCAL_ITEST_SHA256)
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "set_itest_config")
        assignment = next(n for n in function.body if isinstance(n, ast.Assign) and n.targets[0].id == "config_data")
        configured = ast.literal_eval(assignment.value)
        expected = {value[0]: int(key.split()[1]) for key, value in configured.items()}
        actual = {e.aliases[0]: e.binding.slot_id for e in self.candidates.entries
                  if isinstance(e.binding, DeviceServerBinding)}
        self.assertEqual(actual, expected)
        self.assertEqual(sorted(actual.values()), [1, 3, 5, 6, 7, 9, 11, 12])

    def test_crosswalk_source_identity_is_pinned(self):
        repository = Path(__file__).resolve().parents[4]
        self.assertEqual(hashlib.sha256((repository / CROSSWALK_SOURCE).read_bytes()).hexdigest().upper(), CROSSWALK_SHA256)

    def test_six_former_assignments_are_retired_and_bcd_is_not_fabricated(self):
        self.assertEqual(sum(len(e.retired_legacy) for e in self.candidates.entries), 6)
        for name in ("T1-1", "T1-2", "H1", "V1", "Dip1", "Dip2"):
            entry = self.candidates.find(name)
            self.assertEqual(entry.retired_legacy, (entry.legacy_candidate,))
        for name in ("Bcd1", "Bcd2"):
            entry = self.candidates.find(name)
            self.assertIsNone(entry.legacy_candidate)
            self.assertEqual(entry.retired_legacy, ())
            self.assertEqual(entry.beam_line, "unresolved")

    def test_legacy_label_mismatches_remain_explicit(self):
        self.assertEqual(self.candidates.find("Focale").crosswalk_status, "LABEL_MISMATCH_VERIFY_MEANING")
        self.assertEqual(self.candidates.find("Correcteur H5").crosswalk_status, "SCHEMA_RESERVE_UNVERIFIED_ACTUATOR")

    def test_aliases_are_case_insensitive_but_not_fuzzy(self):
        self.assertEqual(self.candidates.find(" h1 ").equipment_id, "corrector-h1")
        self.assertEqual(self.candidates.find("Triplet 1-1"), self.candidates.find("T1-1"))
        self.assertIsNone(self.candidates.find("H11"))

    def test_all_default_routes_block_even_with_transport_available(self):
        for entry in self.candidates.entries:
            with self.subTest(entry=entry.equipment_id):
                plan = plan_current_intent(self.candidates, entry.equipment_id, 0,
                    expected_revision=self.candidates.revision, transport_available=True)
                self.assertFalse(plan.resolved)
                self.assertIsNone(plan.target)
                self.assertIn("ROUTE_UNVERIFIED", plan.blocked_reasons)
                self.assertIn("CURRENT_LIMITS_UNVERIFIED", plan.blocked_reasons)
                self.assertFalse(plan.execution_allowed)

    def test_verified_fixture_selects_explicit_slot_not_array_index(self):
        plan = self.plan("DS alias")
        self.assertTrue(plan.resolved)
        self.assertEqual(plan.target, DeviceServerBinding("test/psu/offline", 9))
        self.assertFalse(plan.execution_allowed)
        self.assertTrue(plan.external_effects_blocked)

    def test_verified_legacy_fixture_selects_only_its_named_current_field(self):
        plan = self.plan("synthetic-legacy", -2)
        self.assertTrue(plan.resolved)
        self.assertEqual(plan.target, self.legacy.binding)

    def test_disconnected_ds_never_falls_back_to_former_daqmx_field(self):
        plan = self.plan(transport_available=False)
        self.assertEqual(plan.blocked_reasons, ("TRANSPORT_UNAVAILABLE",))
        self.assertIsNone(plan.target)
        self.assertFalse(plan.resolved)

    def test_missing_availability_fails_closed(self):
        plan = plan_current_intent(self.registry, "synthetic-ds", 0,
                                  expected_revision=self.registry.revision)
        self.assertIn("TRANSPORT_UNAVAILABLE", plan.blocked_reasons)

    def test_revision_mismatch_blocks_every_backend(self):
        for entry in self.registry.entries:
            plan = self.plan(entry.equipment_id, expected_revision="synthetic.v0")
            self.assertIn("REGISTRY_REVISION_MISMATCH", plan.blocked_reasons)
            self.assertIsNone(plan.target)

    def test_unmapped_equipment_has_no_default_legacy_route(self):
        plan = self.plan("missing-equipment")
        self.assertIn("UNKNOWN_EQUIPMENT", plan.blocked_reasons)
        self.assertIsNone(plan.target)

    def test_zero_current_also_requires_verified_limits(self):
        registry = replace(self.registry, entries=(replace(self.ds, limits=None), self.legacy))
        plan = plan_current_intent(registry, "synthetic-ds", 0,
                                  expected_revision=registry.revision, transport_available=True)
        self.assertEqual(plan.blocked_reasons, ("CURRENT_LIMITS_UNVERIFIED",))

    def test_current_boundaries_are_inclusive_and_not_clamped(self):
        for value in (-2, 2):
            self.assertTrue(self.plan(value=value).resolved)
        plan = self.plan(value=2.01)
        self.assertEqual(plan.current_a, 2.01)
        self.assertEqual(plan.blocked_reasons, ("CURRENT_OUT_OF_RANGE",))

    def test_invalid_current_limits_or_availability_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, "1", 10**500):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.plan(value=value)
        for limits in ((2, 1), (float("nan"), 1), (False, 1)):
            with self.assertRaises(ValueError):
                CurrentLimits(*limits)
        with self.assertRaises(ValueError):
            self.plan(transport_available=1)

    def test_duplicate_equipment_alias_or_endpoint_is_rejected(self):
        cases = (
            replace(self.legacy, equipment_id=self.ds.equipment_id),
            replace(self.legacy, aliases=(" DS ALIAS ",)),
            replace(self.ds, equipment_id="other", label="Other", aliases=()),
        )
        for other in cases:
            with self.subTest(other=other), self.assertRaises(ValueError):
                MagnetRegistry("duplicate-test", (self.ds, other))
        with self.assertRaises(ValueError):
            MagnetRegistry("duplicate-test", (self.ds, replace(self.ds, equipment_id="other", label="Other", aliases=(),
                binding=DeviceServerBinding(" TEST/PSU/OFFLINE ", 9))))

    def test_owner_binding_and_verification_cannot_be_ambiguous(self):
        for changes in (
            {"owner": MagnetOwner.LEGACY_ACQ}, {"owner": "DEVICE_SERVER"},
            {"verification": "VERIFIED"}, {"provenance": ()}, {"retired_legacy": ()},
            {"aliases": ["mutable"]}, {"limits": (-2, 2)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.ds, **changes)
        with self.assertRaises(ValueError):
            DeviceServerBinding("test/psu/offline", True)
        with self.assertRaises(ValueError):
            DeviceServerBinding("test/psu/offline", 0)

    def test_retired_route_cannot_be_reassigned_even_to_other_equipment(self):
        replacement = replace(self.legacy, binding=self.ds.retired_legacy[0])
        with self.assertRaisesRegex(ValueError, "retired DAQmx"):
            MagnetRegistry("bad-reassignment", (self.ds, replacement))

    def test_group_preserves_per_equipment_resolution_and_partial_blocks(self):
        plans = plan_group_currents(self.registry, (("DS alias", 1), ("synthetic-legacy", -1)),
            expected_revision=self.registry.revision,
            available_equipment=frozenset(("synthetic-ds",)))
        self.assertTrue(plans[0].resolved)
        self.assertFalse(plans[1].resolved)
        self.assertEqual(plans[1].blocked_reasons, ("TRANSPORT_UNAVAILABLE",))
        self.assertTrue(all(not p.execution_allowed for p in plans))
        plans = plan_group_currents(self.registry, (("DS alias", 0), ("synthetic-legacy", 0)),
            expected_revision=self.registry.revision,
            available_equipment=frozenset(e.equipment_id for e in self.registry.entries))
        self.assertEqual([p.target for p in plans], [self.ds.binding, self.legacy.binding])

    def test_group_rejects_duplicate_magnet_aliases_and_unknown_availability(self):
        with self.assertRaisesRegex(ValueError, "duplicate magnet"):
            plan_group_currents(self.registry, (("DS alias", 0), ("synthetic-ds", 1)),
                                expected_revision=self.registry.revision)
        with self.assertRaises(ValueError):
            plan_group_currents(self.registry, (), expected_revision=self.registry.revision)
        with self.assertRaises(ValueError):
            plan_group_currents(self.registry, (("DS alias", 0),), expected_revision=self.registry.revision,
                                available_equipment=frozenset(("DS alias",)))

    def test_named_legacy_selection_rejects_retired_and_unknown_fields(self):
        blockers = legacy_selection_blockers(self.registry, "TEST_BANK",
            ("active-current", "retired-current", "unmapped"), expected_revision=self.registry.revision)
        self.assertEqual(blockers, ("RETIRED_LEGACY_FIELD: TEST_BANK/retired-current", "NO_LEGACY_OWNER: TEST_BANK/unmapped"))
        self.assertEqual(legacy_selection_blockers(self.registry, "TEST_BANK", ("active-current",),
                         expected_revision=self.registry.revision), ())

    def test_legacy_selection_blocks_unverified_routes_stale_revision_and_duplicates(self):
        registry = replace(self.registry, entries=(self.ds, replace(self.legacy, verification=RouteVerification.CANDIDATE)))
        blockers = legacy_selection_blockers(registry, "TEST_BANK", ("active-current",), expected_revision="stale")
        self.assertEqual(blockers, ("REGISTRY_REVISION_MISMATCH", "ROUTE_UNVERIFIED: TEST_BANK/active-current"))
        with self.assertRaises(ValueError):
            legacy_selection_blockers(self.registry, "TEST_BANK", (), expected_revision=self.registry.revision)
        with self.assertRaises(ValueError):
            legacy_selection_blockers(self.registry, "TEST_BANK", ("active-current", " ACTIVE-CURRENT "),
                                      expected_revision=self.registry.revision)

    def test_original_magnet_bank_republication_is_not_owned(self):
        for bank in ("C6NI6703", "C7NI6703"):
            fields = tuple(e.legacy_candidate.field for e in self.candidates.entries
                           if e.legacy_candidate and e.legacy_candidate.variable == bank)
            blockers = legacy_selection_blockers(self.candidates, bank, fields, expected_revision=self.candidates.revision)
            self.assertEqual(len(blockers), len(fields))
            self.assertTrue(any(reason.startswith("RETIRED_LEGACY_FIELD") for reason in blockers))

    def test_registry_and_plans_are_immutable_and_execution_flag_is_not_a_constructor_option(self):
        plan = self.plan()
        with self.assertRaises(FrozenInstanceError):
            self.registry.revision = "changed"
        with self.assertRaises(FrozenInstanceError):
            plan.target = self.legacy.binding
        with self.assertRaises(TypeError):
            replace(plan, execution_allowed=True)

    def test_snapshot_never_invents_telemetry_or_execution_authority(self):
        snapshot = registry_snapshot(self.candidates)
        self.assertTrue(snapshot["display_only"])
        self.assertTrue(snapshot["external_effects_blocked"])
        for row in snapshot["entries"]:
            self.assertFalse(row["execution_allowed"])
            self.assertEqual(row["telemetry"], {"setpoint_a": None, "measured_a": None,
                "timestamp": None, "quality": "UNAVAILABLE", "source": None})
        exported = json.loads(render_snapshot())
        readbacks = exported.pop("readback_candidates")
        self.assertEqual(exported, snapshot)
        self.assertEqual(len(readbacks), 21)
        self.assertEqual(sum(row["source"] is not None for row in readbacks.values()), 8)

    def test_web_snapshot_is_exact_export_of_python_candidates(self):
        supervision = Path(__file__).resolve().parents[3]
        exported = (supervision / "web_prototype" / "magnet-registry.js").read_text(encoding="utf-8")
        self.assertEqual(exported, render_snapshot(javascript=True))


if __name__ == "__main__":
    unittest.main()
