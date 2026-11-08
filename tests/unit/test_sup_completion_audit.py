"""Local source/identity checks and supplied-state witnesses, never motor IO."""

import copy
import ctypes
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_completion_audit as trace


@pytest.fixture(scope="module")
def inputs():
    return trace.original(), trace.load_inputs()


@pytest.fixture(scope="module")
def main_graph(inputs):
    receipt, roots = inputs[0]
    T, _ = trace.components()
    return trace.SourceGraph(receipt, roots, T(roots["meta"]))


@pytest.fixture(scope="module")
def report(inputs):
    return trace.verify(*inputs)


def test_report_reproduces_without_network_or_native_library(inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No native or network execution in saved-source audit")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    assert trace.verify(*inputs) == json.loads(trace.OUTPUT.read_text("utf-8"))


def test_39_original_identities_are_not_claimed_as_behavioral_completion(report):
    assert report["member_count"] == 39
    members = report["original_application_VIs"]
    assert len({r["name"] for r in members}) == 39
    assert all(r["original_bytes_and_XML_verified"] for r in members)
    assert not any(r["inventory_is_full_behavior_proof"] for r in members)
    assert not report["completion_criteria"][
        "all_original_source_control_behavior_proven"
    ]
    assert not report["completion_criteria"][
        "complete_Python_business_logic_replacement"
    ]
    assert not report["completion_criteria"]["full_Supervision_coverage"]


def test_startup_and_manual_use_same_stored_banks(report):
    routes = report["new_initialization_findings"]["state_banks"]
    assert {r["bank"] for r in routes} == {244, 246, 248}
    assert all(r["same_state_bank"] for r in routes)
    assert {r["FP_control"] for r in routes} == {"61437", "61750", "77644"}


def test_bank_identity_mutation_rejected(main_graph, inputs):
    receipt = copy.deepcopy(inputs[0][0])
    next(r for r in receipt["locals"] if r["uid"] == "286518")["control_uid"] = "999"
    with pytest.raises(AssertionError, match="target identity"):
        trace.initialize(main_graph, receipt)


@pytest.mark.parametrize("loop", ["62157", "274199"])
def test_error_shift_register_mutation_rejected(main_graph, inputs, monkeypatch, loop):
    slot = main_graph.nodes[loop].find("srDCOList")
    assert slot is not None and len(slot) == 0
    injected = ET.SubElement(slot, "SL__arrayElement", uid="fake_sr")
    try:
        with pytest.raises(AssertionError, match="feedback"):
            trace.initialize(main_graph, inputs[0][0])
    finally:
        slot.remove(injected)


def test_key_length_selector_mutation_rejected(main_graph, inputs):
    flag = main_graph.nodes["274119"].find("SelectDefaultCase")
    before = flag.text
    flag.text = "00"
    try:
        with pytest.raises(AssertionError, match="default"):
            trace.initialize(main_graph, inputs[0][0])
    finally:
        flag.text = before


@pytest.mark.parametrize("error", [False, True])
def test_empty_key_keeps_old_key_and_address_with_new_reference(error):
    result = trace.init_witness(
        "OLD-DEVICE", 7, "NEW-REFERENCE", "", 0, [False] * 4, discovery_error=error
    )
    assert result["CmdLib"] == "NEW-REFERENCE"
    assert result["DeviceKey"] == "OLD-DEVICE"
    assert result["DeviceAddress"] == 7
    assert result["out_error_status"] == error
    assert result["button_visibility_request_after_return"]
    assert not result["native_or_hardware_executed"]


@pytest.mark.parametrize("failing_motor", [0, 1, 2, 3])
def test_scalar_last_iteration_can_hide_early_zeroing_error(failing_motor):
    statuses = [False] * 4
    statuses[failing_motor] = True
    result = trace.init_witness("OLD", 7, "NEW-REFERENCE", "FOUND", 2, statuses)
    assert result["DeviceKey"] == "FOUND"
    assert result["DeviceAddress"] == 2
    assert result["out_error_status"] == (failing_motor == 3)
    assert result["button_visibility_request_after_return"]


def test_snapshot_returns_are_required_not_invented():
    with pytest.raises(AssertionError, match="four supplied"):
        trace.init_witness("OLD", 7, "NEW", "FOUND", 2, [])
    with pytest.raises(AssertionError, match="string"):
        trace.init_witness("OLD", 7, "NEW", None, 2, [False] * 4)


def test_button_visibility_is_not_success_acknowledgement(report):
    facts = report["new_initialization_findings"]
    assert facts["manual_event"] == 27
    assert facts["manual_post_phase"]["movement_buttons_Visible_requested"]
    assert facts["manual_post_phase"]["property_writes_outside_error_case"]
    assert facts["no_source_Shutdown_before_manual_reinitialization"]
    assert all(
        not row["empty_key_sets_failure_error"] for row in facts["key_length_branches"]
    )
    assert all(
        not row["per_motor_error_feedback_or_early_stop"]
        for row in facts["zero_position_loops"]
    )


def test_copied_2012_wrappers_not_confused_with_installed_2020(report):
    facts = report["copied_remote_NI2012_cleanup"]
    assert len(facts["members"]) == 5
    assert all("remote_labview2012" in r["archive"] for r in facts["members"])
    assert facts["same_selected_wire_predicates_as_NI2020"]
    assert not facts["native_library_equivalence"]
    assert not facts["observations"]["incoming_error_used_as_close_selector"]
    assert facts["observations"]["prior_error_can_hide_close_error"]


def test_source_and_deployment_obligations_are_distinct(report):
    gaps = report["remaining_source_work_not_replaced_by_inventory"]
    assert len(gaps["concrete_source_obligations"]) == 4
    assert len(gaps["separate_deployment_obligations"]) == 3
    assert any("DCO780" in r["obligation"] for r in gaps["concrete_source_obligations"])
    assert report["previous_frozen_reports_changed"] is False
    assert all(
        report[k] is False
        for k in (
            "screen_used",
            "VI_run_or_save",
            "native_library_loaded",
            "network_io",
            "hardware_io",
            "production_changes",
        )
    )
