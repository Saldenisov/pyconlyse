"""Every original controlled-stop diagram has a manually observed image link."""

import json

import pytest
from tools.validate_acq_native_nested_stop import RECORD, validate


def test_all_45_stop_diagrams_have_source_checked_manual_native_views():
    result = validate()
    assert result["source_stop_diagrams"] == 45
    assert result["source_stop_nets"] == 152
    assert result["manually_viewed_stop_diagrams"] == 45
    assert result["nested_sequence_frames"] == 33
    assert result["retained_nested_images"] == 33
    assert result["retained_prior_images_used"] == 3
    assert not result["native_original_lv2012_runtime_equivalence"]
    assert not result["whole_acquisition_closed"]


@pytest.mark.parametrize(
    "field", ["whole_acquisition_closed", "original_lv2012_runtime_equivalence"]
)
def test_selected_sequence_does_not_become_whole_controller_equivalence(field):
    record = json.loads(RECORD.read_text("utf-8"))
    record[field] = True
    with pytest.raises(AssertionError, match="observation scope"):
        validate(record)


def test_missing_modulator_frame_cannot_be_hidden_by_total_image_count():
    record = json.loads(RECORD.read_text("utf-8"))
    record["nested_sequences"][3]["visited_frames"].pop()
    with pytest.raises(AssertionError, match="visited frame population"):
        validate(record)


def test_second_counter_poll_body_cannot_reuse_first_body_identity():
    record = json.loads(RECORD.read_text("utf-8"))
    record["poll_body_views"][1]["diagram"] = "47770"
    with pytest.raises(AssertionError, match="poll body view mapping"):
        validate(record)
