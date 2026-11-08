"""Synthetic, hardware-free provenance and post-dispatch current tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import unittest

from supervision_reconstruction.domain.magnet_registry import (
    CurrentLimits, DeviceServerBinding, LegacyCurrentBinding,
    MagnetEntry, MagnetOwner, MagnetRegistry, RouteVerification, candidate_registry,
)
from supervision_reconstruction.domain.magnet_readback import (
    CurrentReadbackAssociation, CurrentReadbackPolicy, DispatchObservation,
    ITestMeasuredCurrentPoint, LegacyMeasuredCurrentPoint, MeasuredCurrentSample,
    ReadbackQuality, RecordedCurrentRequest, candidate_readback_associations,
    compare_recorded_current_request, project_current_readback,
    readback_candidate_snapshot, sample_from_itest_arrays,
)


class MagnetReadbackTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 12, 0, 10, tzinfo=timezone.utc)
        self.ds = MagnetEntry(
            "synthetic-ds", "Synthetic iTest", (), "test", MagnetOwner.DEVICE_SERVER,
            DeviceServerBinding("test/psu/offline", 9), RouteVerification.VERIFIED,
            ("synthetic command route only; not deployed",), CurrentLimits(-2, 2),
            LegacyCurrentBinding("TEST_COMMAND", "old-ds-current"),
            (LegacyCurrentBinding("TEST_COMMAND", "old-ds-current"),),
        )
        self.legacy = MagnetEntry(
            "synthetic-legacy", "Synthetic legacy", (), "test", MagnetOwner.LEGACY_ACQ,
            LegacyCurrentBinding("TEST_COMMAND", "legacy-current"), RouteVerification.VERIFIED,
            ("synthetic command route only; not deployed",), CurrentLimits(-3, 3),
        )
        self.registry = MagnetRegistry("synthetic-readback.v1", (self.ds, self.legacy))
        self.point = ITestMeasuredCurrentPoint(self.ds.binding)
        self.association = CurrentReadbackAssociation(
            self.ds.equipment_id, self.registry.revision, self.ds.binding, self.point,
            RouteVerification.VERIFIED, ("independent synthetic readback proof; not deployed",),
        )
        self.policy = CurrentReadbackPolicy(1000, 0.5)  # Explicit test values, not commissioned limits.
        self.sample = MeasuredCurrentSample(
            self.ds.equipment_id, self.registry.revision, self.point, 1.0,
            self.now - timedelta(milliseconds=100), self.now - timedelta(milliseconds=50),
            ReadbackQuality.VALID, True,
        )
        self.request = RecordedCurrentRequest(
            "synthetic-command", self.ds.equipment_id, self.registry.revision,
            self.ds.binding, 1.0, DispatchObservation.DISPATCHED,
            self.now - timedelta(milliseconds=500),
        )

    def project(self, sample=None, association=None, registry=None, **kwargs):
        return project_current_readback(
            registry or self.registry, association or self.association,
            self.sample if sample is None else sample, now=kwargs.pop("now", self.now),
            policy=kwargs.pop("policy", self.policy),
            transport_available=kwargs.pop("transport_available", True), **kwargs,
        )

    def compare(self, view=None, request=None, **kwargs):
        view = view or self.project()
        return compare_recorded_current_request(
            self.registry, request or self.request, view,
            now=kwargs.pop("now", view.evaluated_at),
            policy=kwargs.pop("policy", self.policy), **kwargs,
        )

    def test_default_inventory_has_only_eight_unverified_measurement_candidates(self):
        registry = candidate_registry()
        associations = candidate_readback_associations(registry)
        self.assertEqual(len(associations), 21)
        self.assertEqual(sum(a.source is not None for a in associations), 8)
        self.assertTrue(all(a.verification is RouteVerification.CANDIDATE for a in associations))
        self.assertTrue(all(not a.cross_owner_approved for a in associations))
        self.assertTrue(all(a.source is None or a.source.attribute == "currents_meas" for a in associations))
        for association in associations:
            view = project_current_readback(registry, association, None, now=self.now,
                policy=self.policy, transport_available=True)
            self.assertEqual(view.quality, ReadbackQuality.UNKNOWN)
            self.assertIsNone(view.measured_a)
            self.assertIn("READBACK_ASSOCIATION_UNVERIFIED", view.reasons)

    def test_slot_array_selection_uses_discovered_id_not_slot_minus_one(self):
        for ids, currents in (((1, 3, 9, 12), (11, 33, 99, 1212)), ((12, 9, 3, 1), (1212, 99, 33, 11))):
            sample = sample_from_itest_arrays(
                equipment_id=self.ds.equipment_id, registry_revision=self.registry.revision,
                source=self.point, slot_ids=ids, measured_currents=currents,
                source_time=self.sample.source_time, received_at=self.sample.received_at,
                quality=ReadbackQuality.VALID, acquisition_confirmed=True,
            )
            self.assertEqual(sample.value_a, 99)
            self.assertEqual(sample.source.attribute, "currents_meas")

    def test_malformed_duplicate_or_missing_slot_arrays_fail_closed(self):
        for ids, values in (((1, 9), (1,)), ((9, 9), (1, 2)), ((1, 3), (1, 2)), ((True, 9), (1, 2)), ((), ())):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                sample_from_itest_arrays(equipment_id=self.ds.equipment_id,
                    registry_revision=self.registry.revision, source=self.point,
                    slot_ids=ids, measured_currents=values, source_time=self.sample.source_time,
                    received_at=self.sample.received_at, quality=ReadbackQuality.VALID)

    def test_fresh_verified_sample_has_acquisition_age_not_receive_age(self):
        view = self.project()
        self.assertEqual(view.quality, ReadbackQuality.VALID)
        self.assertEqual(view.measured_a, 1.0)
        self.assertEqual(view.age_ms, 100)
        self.assertEqual(view.reasons, ())

    def test_newly_received_old_acquisition_remains_stale(self):
        sample = replace(self.sample, source_time=self.now - timedelta(seconds=5), received_at=self.now)
        view = self.project(sample)
        self.assertEqual(view.quality, ReadbackQuality.STALE)
        self.assertEqual(view.measured_a, 1.0)
        self.assertEqual(view.age_ms, 5000)
        self.assertIsNone(self.compare(view).current_matches_request)

    def test_freshness_boundary_is_inclusive_and_ages_without_new_data(self):
        sample = replace(self.sample, source_time=self.now - timedelta(milliseconds=1000), received_at=self.now)
        self.assertEqual(self.project(sample).quality, ReadbackQuality.VALID)
        view = self.project(sample, now=self.now + timedelta(microseconds=1))
        self.assertEqual(view.quality, ReadbackQuality.STALE)

    def test_upstream_stale_quality_is_never_upgraded_by_recent_receive_time(self):
        view = self.project(replace(self.sample, quality=ReadbackQuality.STALE))
        self.assertEqual(view.quality, ReadbackQuality.STALE)
        self.assertIsNone(self.compare(view).orange_flag)

    def test_cache_initialization_zero_does_not_prove_zero_current(self):
        view = self.project(replace(self.sample, value_a=0, acquisition_confirmed=False))
        request = replace(self.request, requested_a=0)
        self.assertEqual(view.quality, ReadbackQuality.UNKNOWN)
        self.assertIsNone(view.measured_a)
        self.assertIn("PHYSICAL_ACQUISITION_UNPROVEN", view.reasons)
        self.assertIsNone(self.compare(view, request).current_matches_request)

    def test_missing_producer_timestamp_cannot_be_replaced_with_receive_time(self):
        view = self.project(replace(self.sample, source_time=None, received_at=self.now))
        self.assertEqual(view.quality, ReadbackQuality.UNKNOWN)
        self.assertIn("ACQUISITION_TIME_UNKNOWN", view.reasons)
        self.assertIsNone(view.age_ms)
        self.assertIsNone(view.measured_a)

    def test_naive_timestamps_and_invalid_policies_are_rejected(self):
        with self.assertRaises(ValueError):
            self.project(now=datetime(2026, 10, 3))
        with self.assertRaises(ValueError):
            replace(self.sample, received_at=datetime(2026, 10, 3))
        for age, tolerance in ((0, 1), (-1, 1), (1000, -1), (True, 1), (1000, float("nan"))):
            with self.assertRaises(ValueError):
                CurrentReadbackPolicy(age, tolerance)

    def test_future_producer_or_receive_time_is_invalid_not_fresh(self):
        for sample in (
            replace(self.sample, source_time=self.now),
            replace(self.sample, received_at=self.now + timedelta(seconds=1)),
        ):
            view = self.project(sample)
            self.assertEqual(view.quality, ReadbackQuality.INVALID)
            self.assertIsNone(view.measured_a)

    def test_aware_non_utc_times_normalize_to_same_instant(self):
        plus_two = timezone(timedelta(hours=2))
        sample = replace(self.sample, source_time=self.sample.source_time.astimezone(plus_two),
                         received_at=self.sample.received_at.astimezone(plus_two))
        self.assertEqual(self.project(sample).age_ms, 100)
        self.assertEqual(self.project(sample).source_time.tzinfo, timezone.utc)

    def test_invalid_scpi_nan_and_malformed_values_are_not_zeroed(self):
        for payload in (float("nan"), float("inf"), float("-inf"), True, "1", None, 10**500):
            with self.subTest(payload=payload):
                view = self.project(replace(self.sample, value_a=payload))
                self.assertEqual(view.quality, ReadbackQuality.INVALID)
                self.assertIsNone(view.measured_a)
                self.assertIsNone(self.compare(view).current_matches_request)

    def test_disconnected_transport_hides_cached_measurement(self):
        view = self.project(transport_available=False)
        self.assertEqual(view.quality, ReadbackQuality.DISCONNECTED)
        self.assertIsNone(view.measured_a)
        self.assertIsNone(self.compare(view).orange_flag)
        self.assertEqual(view.source, self.point)  # No fallback to legacy source.

    def test_missing_sample_and_unspecified_availability_fail_closed(self):
        view = project_current_readback(self.registry, self.association, None,
                                        now=self.now, policy=self.policy, transport_available=True)
        self.assertIn("NO_SAMPLE", view.reasons)
        self.assertEqual(view.quality, ReadbackQuality.UNKNOWN)
        view = project_current_readback(self.registry, self.association, self.sample,
                                        now=self.now, policy=self.policy)
        self.assertEqual(view.quality, ReadbackQuality.DISCONNECTED)

    def test_upstream_invalid_disconnected_or_unknown_is_not_upgraded(self):
        for quality in (ReadbackQuality.INVALID, ReadbackQuality.DISCONNECTED, ReadbackQuality.UNKNOWN):
            view = self.project(replace(self.sample, quality=quality))
            self.assertEqual(view.quality, quality)
            self.assertIsNone(view.measured_a)
            self.assertIsNone(self.compare(view).current_matches_request)

    def test_simulated_matching_current_cannot_confirm_real_request(self):
        view = self.project(replace(self.sample, quality=ReadbackQuality.SIMULATED))
        self.assertEqual(view.quality, ReadbackQuality.SIMULATED)
        self.assertEqual(view.measured_a, 1.0)
        self.assertIsNone(self.compare(view).current_matches_request)
        view = self.project(replace(self.sample, quality=ReadbackQuality.SIMULATED,
                                    source_time=self.now - timedelta(seconds=5)))
        self.assertEqual(view.quality, ReadbackQuality.SIMULATED)
        self.assertIn("ACQUISITION_STALE", view.reasons)

    def test_unverified_association_never_inherits_command_route_verification(self):
        association = replace(self.association, verification=RouteVerification.CANDIDATE)
        view = self.project(association=association)
        self.assertEqual(view.quality, ReadbackQuality.UNKNOWN)
        self.assertIn("READBACK_ASSOCIATION_UNVERIFIED", view.reasons)
        with self.assertRaises(ValueError):
            replace(self.association, provenance=())

    def test_wrong_equipment_slot_device_or_revision_cannot_confirm(self):
        for sample in (
            replace(self.sample, equipment_id=self.legacy.equipment_id),
            replace(self.sample, registry_revision="stale"),
            replace(self.sample, source=ITestMeasuredCurrentPoint(DeviceServerBinding("test/psu/offline", 3))),
            replace(self.sample, source=ITestMeasuredCurrentPoint(DeviceServerBinding("other/psu/offline", 9))),
        ):
            view = self.project(sample)
            self.assertEqual(view.quality, ReadbackQuality.UNKNOWN)
            self.assertIsNone(view.measured_a)
        association = replace(self.association, source=ITestMeasuredCurrentPoint(DeviceServerBinding("test/psu/offline", 3)))
        sample = replace(self.sample, source=association.source)
        self.assertIn("ITEST_READBACK_SLOT_MISMATCH", self.project(sample, association).reasons)

    def test_stale_association_or_changed_command_route_invalidates_readback(self):
        for association in (
            replace(self.association, registry_revision="stale"),
            replace(self.association, command_binding=DeviceServerBinding("test/psu/offline", 3)),
            replace(self.association, equipment_id="missing"),
        ):
            self.assertIsNone(self.project(association=association).measured_a)

    def test_legacy_readback_needs_separate_verified_ai_field(self):
        point = LegacyMeasuredCurrentPoint("TEST_AI", "physical-legacy-current")
        association = replace(self.association, equipment_id=self.legacy.equipment_id,
                              command_binding=self.legacy.binding, source=point)
        sample = replace(self.sample, equipment_id=self.legacy.equipment_id, source=point)
        view = self.project(sample, association)
        self.assertEqual(view.quality, ReadbackQuality.VALID)
        request = replace(self.request, equipment_id=self.legacy.equipment_id, target=self.legacy.binding)
        self.assertTrue(self.compare(view, request).current_matches_request)

    def test_old_legacy_sensor_cannot_confirm_itest_without_independent_approval(self):
        point = LegacyMeasuredCurrentPoint("TEST_AI", "physical-ds-current")
        association = replace(self.association, source=point)
        sample = replace(self.sample, source=point)
        view = self.project(sample, association)
        self.assertIn("CROSS_OWNER_READBACK_UNAPPROVED", view.reasons)
        association = replace(association, cross_owner_approved=True,
                              provenance=("independent synthetic sensor association",))
        view = self.project(sample, association)
        self.assertEqual(view.quality, ReadbackQuality.VALID)
        self.assertTrue(self.compare(view).current_matches_request)
        with self.assertRaises(ValueError):
            replace(association, verification=RouteVerification.CANDIDATE)

    def test_active_or_retired_command_fields_cannot_be_accepted_as_measurements(self):
        for field in ("old-ds-current", "legacy-current"):
            point = LegacyMeasuredCurrentPoint("TEST_COMMAND", field)
            association = replace(self.association, source=point, cross_owner_approved=True)
            sample = replace(self.sample, source=point)
            view = self.project(sample, association)
            self.assertIn("COMMAND_FIELD_IS_NOT_MEASURED_CURRENT", view.reasons)
            self.assertIsNone(view.measured_a)

    def test_http_acceptance_or_failed_dispatch_never_proves_current_response(self):
        for state in (DispatchObservation.ACCEPTED, DispatchObservation.FAILED,
                      DispatchObservation.TIMED_OUT, DispatchObservation.CANCELLED):
            request = replace(self.request, dispatch_observation=state)
            comparison = self.compare(request=request)
            self.assertIsNone(comparison.current_matches_request)
            self.assertIn(f"DISPATCH_{state.value}", comparison.reasons)

    def test_pre_dispatch_or_equal_timestamp_sample_is_not_response_to_command(self):
        for stamp in (self.request.dispatched_at, self.request.dispatched_at - timedelta(milliseconds=1)):
            view = self.project(replace(self.sample, source_time=stamp))
            self.assertEqual(view.quality, ReadbackQuality.VALID)
            self.assertIn("NO_POST_DISPATCH_MEASUREMENT", self.compare(view).reasons)

    def test_current_match_uses_strict_greater_than_without_claiming_command_success(self):
        for measured, matched in ((1.0, True), (1.5, True), (0.5, True), (1.50001, False), (0.49999, False)):
            comparison = self.compare(self.project(replace(self.sample, value_a=measured)))
            self.assertEqual(comparison.current_matches_request, matched)
            self.assertEqual(comparison.orange_flag, not matched)
            self.assertEqual(comparison.absolute_difference_a, abs(1.0 - measured))
            self.assertFalse(comparison.establishes_command_success)

    def test_recorded_request_must_match_equipment_route_revision_and_limits(self):
        for changes in (
            {"equipment_id": self.legacy.equipment_id}, {"registry_revision": "stale"},
            {"target": self.ds.retired_legacy[0]}, {"requested_a": 3},
            {"dispatched_at": self.now + timedelta(seconds=1)},
        ):
            self.assertIsNone(self.compare(request=replace(self.request, **changes)).current_matches_request)
        with self.assertRaises(ValueError):
            replace(self.request, dispatched_at=None)

    def test_mutated_projection_cannot_forge_valid_current_or_freshness(self):
        view = self.project()
        for changed in (replace(view, measured_a=1.25), replace(view, age_ms=0),
                        replace(view, quality=ReadbackQuality.STALE)):
            self.assertIn("READBACK_PROJECTION_MISMATCH", self.compare(changed).reasons)
            self.assertIsNone(self.compare(changed).current_matches_request)
        narrower = CurrentReadbackPolicy(10, 0.5)
        self.assertIsNone(self.compare(view, policy=narrower).current_matches_request)

    def test_associations_samples_and_projection_are_immutable(self):
        view = self.project()
        with self.assertRaises(FrozenInstanceError):
            view.quality = ReadbackQuality.VALID
        with self.assertRaises(FrozenInstanceError):
            self.sample.value_a = 0
        with self.assertRaises(FrozenInstanceError):
            self.association.source = None
        with self.assertRaises(ValueError):
            replace(self.sample, value_a=[1.0])

    def test_display_candidate_requires_physical_acquisition_and_source_timestamp(self):
        rows = candidate_readback_associations(candidate_registry())
        snapshot = readback_candidate_snapshot(rows[0])
        self.assertEqual(snapshot["source"]["attribute"], "currents_meas")
        self.assertEqual(snapshot["source"]["slot_id"], 7)
        self.assertEqual(snapshot["source"]["ids_attribute"], "ids")
        self.assertTrue(snapshot["physical_acquisition_required"])
        self.assertTrue(snapshot["source_time_required"])
        self.assertEqual(snapshot["verification"], "CANDIDATE")

    def test_replay_acceptance_dispatch_current_match_staleness_disconnect_and_recovery(self):
        fresh = self.project()
        accepted = replace(self.request, dispatch_observation=DispatchObservation.ACCEPTED)
        before_dispatch = self.project(replace(self.sample,
            source_time=self.request.dispatched_at - timedelta(milliseconds=1)))
        later = self.now + timedelta(seconds=2)
        disconnected = self.project(now=later, transport_available=False)
        recovered_sample = replace(self.sample, source_time=later - timedelta(milliseconds=20),
                                   received_at=later - timedelta(milliseconds=10))
        recovered = self.project(recovered_sample, now=later)
        results = (
            self.compare(fresh, accepted), self.compare(before_dispatch), self.compare(fresh),
            self.compare(fresh, now=later), self.compare(disconnected), self.compare(recovered),
            self.compare(recovered, replace(self.request, dispatch_observation=DispatchObservation.TIMED_OUT)),
        )
        self.assertEqual([result.current_matches_request for result in results],
                         [None, None, True, None, None, True, None])
        self.assertIn("ACQUISITION_STALE", results[3].reasons)
        self.assertEqual(results[3].evaluated_at, later)
        self.assertTrue(all(not result.establishes_command_success for result in results))

    def test_comparison_clock_regression_or_naive_time_cannot_reuse_valid_projection(self):
        result = self.compare(now=self.now - timedelta(milliseconds=1))
        self.assertIn("EVALUATION_CLOCK_REGRESSION", result.reasons)
        self.assertIsNone(result.current_matches_request)
        with self.assertRaises(ValueError):
            self.compare(now=datetime(2026, 10, 3))


if __name__ == "__main__":
    unittest.main()
