"""Committed source projection cases, without external VI/native dependencies."""

import json
from pathlib import Path

from legacy.xp_acq_agent.elyse_agent.acquisition_counter_timing import (
    SOURCE_HELPER_SHA256,
    SOURCE_VI_SHA256,
    decode_counter_bank,
    project_counter_selector,
)

EVIDENCE = (
    Path(__file__).resolve().parents[3]
    / "legacy/xp_acq_agent/data/counter_selector_error_evidence.json"
)


def test_source_projection_cases_match_transfer_without_qualifying_negative_task():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    pins = evidence["source_pins"]
    assert pins["acquisition_vi"]["sha256"] == SOURCE_VI_SHA256
    assert pins["helper_vi"]["sha256"] == SOURCE_HELPER_SHA256
    arithmetic = evidence["selector_arithmetic"]
    assert len(arithmetic["type_resolution"]["terminal_types"]) == 15
    assert len(arithmetic["wires"]) == 11
    for case in arithmetic["representative_cases"]:
        projection = project_counter_selector(case["selector"])
        assert {key: projection[key] for key in case} == case
        assert projection["native_default_task_qualified"] is False
        if case["task_in_bounds"]:
            request = decode_counter_bank(
                tuple(float(i) for i in range(32)) + (case["selector"],)
            )
            assert request["counter"] == case["counter"]
            assert request["delay_index"] == case["delay_index"]
            assert request["width_index"] == case["width_index"]


def test_documented_clear_and_local_dialog_do_not_attest_deployed_xp_driver():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    clear = evidence["native_helper_error_flow"]["clear_errors"]
    assert clear["connected_connector_slots"] == [0, 4]
    assert clear["documented_unwired_default"] == 0
    assert clear["documented_profile_result"] == dict(status=False, code=0, source="")
    assert clear["deployed_xp_binary_identity_qualified"] is False
    caller = evidence["caller_error_handler_and_continuation"]
    assert caller["handler_dialog_mode_input_wired"] is False
    assert caller["handler_outputs_consumed"] is False
    assert caller["local_labview_2020_profile"]["default_response_buttons"] == [
        "Continue"
    ]
    assert (
        caller["deployed_xp_labview_2012_profile"]["binary_identity_qualified"] is False
    )
