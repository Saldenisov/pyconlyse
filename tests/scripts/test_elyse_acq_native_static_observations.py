"""Version-bound source/image record and inert controller projections."""

import itertools
import json
from copy import deepcopy

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.timeout_cooling import (
    cooling_guard,
    trip_frame,
)
from tools.validate_acq_native_static_observations import (
    INIT_RECORD,
    RECORD,
    validate,
    validate_initializer_observations,
    validate_stop_observations,
)


def test_initializer_images_keep_configuration_distinct_from_output_and_recovery():
    result = validate_initializer_observations()
    assert result["frozen_initializer_images"] == 17
    assert result["caller_error_cases_both_arms_reviewed"] == 4
    assert result["pilot_error_cases_both_arms_reviewed"] == 2
    assert result["ao_frames_reviewed"] == 4
    assert result["final_startup_frames_reviewed"] == 5
    assert result["dio_loaded_path_readback_pending"]
    assert not result["whole_initialization_closed"]
    assert not result["whole_acquisition_closed"]


@pytest.mark.parametrize(
    "field", ["whole_initialization_closed", "whole_acquisition_closed"]
)
def test_initializer_record_cannot_promote_selected_views_to_completion(field):
    record = json.loads(INIT_RECORD.read_text("utf-8"))
    record[field] = True
    with pytest.raises(AssertionError, match="initializer observation scope"):
        validate_initializer_observations(record)


def test_initializer_record_does_not_turn_annotation_into_error_code_guard():
    record = json.loads(INIT_RECORD.read_text("utf-8"))
    record["pilot_fallback"]["error_code_equality_guard"] = True
    with pytest.raises(AssertionError, match="caller/fallback observation"):
        validate_initializer_observations(record)


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text("utf-8"))


def test_all_three_original_disable_structures_and_eighteen_images_are_bound(record):
    result = validate(record)
    assert result["byte_identical_original_members"] == 17
    assert result["disable_arms_visually_reviewed"] == 6
    assert result["cooling_trip_frames_visually_reviewed"] == 7
    assert result["frozen_images"] == 18
    assert not result["original_lv2012_runtime_equivalence"]
    assert not result["whole_acquisition_closed"]


def test_seven_outer_stop_views_do_not_claim_all_nested_visits():
    result = validate_stop_observations()
    assert result["static_native_outer_phase_views"] == 7
    assert result["frozen_stop_images"] == 12
    assert result["source_stop_graphs"] == 45
    assert result["source_stop_nets"] == 152
    assert result["source_envelope_graphs"] == 12
    assert not result["all_nested_stop_diagrams_visually_reviewed"]
    assert not result["whole_acquisition_closed"]


def test_observed_import_arm_drives_only_explicit_inert_cooling_projection(record):
    flow_row = next(row for row in record["comment_nodes"] if row["uid"] == "14478")
    assert record["native_executable_file_version"] == "20.0f1"
    enabled = flow_row["observed_active_index"] == 0
    assert enabled
    for a, b, c, d in itertools.product((False, True), repeat=4):
        c4, c3 = [False] * 64, [False] * 56
        c4[19], c4[38], c3[0], c3[6] = a, b, c, d
        assert cooling_guard(
            enabled_arm=enabled, c4_snapshot=tuple(c4), c3_snapshot=tuple(c3)
        ) == ((a or b) and (not c or not d))


def test_seven_observed_wait_arguments_match_the_existing_non_actuating_model(record):
    snapshots = (
        {"10431": (True,) * 40},
        {"13466": (False,) * 40},
        {},
        {"22661": (True,) * 40},
        {"30986": (False,) * 40},
        {"39289": (True,) * 77, "39313": (True,) * 29},
        {"39444": (False,) * 29},
    )
    effects = [trip_frame(i, snapshots=reads) for i, reads in enumerate(snapshots)]
    assert [row.requested_wait_ms for row in effects] == record["cooling_guard"][
        "requested_wait_ms_by_frame"
    ]
    assert [row.diagram_uid for row in effects] == [
        "10221",
        "13119",
        "14187",
        "20056",
        "30644",
        "31857",
        "39347",
    ]
    assert effects[5].writes[0].data[8] is True  # No implicit General-OK reset.
    assert effects[6].publication.data == snapshots[6]["39444"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("whole_acquisition_closed", True),
        ("native_original_lv2012_runtime_equivalence", True),
        ("native_executable_file_version", "12.0f3"),
    ],
)
def test_scope_promotion_or_version_substitution_is_rejected_early(
    record, field, value
):
    changed = deepcopy(record)
    changed[field] = value
    with pytest.raises(AssertionError, match="scope or qualification"):
        validate(changed)
