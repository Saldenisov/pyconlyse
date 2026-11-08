"""Offline XML/IL regression checks and supplied-state shutdown witnesses."""

import copy
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_native_timeouts as trace


@pytest.fixture(scope="module")
def sources():
    return trace.original()


@pytest.fixture(scope="module")
def supporting():
    return trace.evidence()


@pytest.fixture(scope="module")
def report(sources, supporting):
    return trace.verify(sources, supporting)


def test_report_reproduces_with_network_forbidden(sources, supporting, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network in local native timeout audit")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = trace.verify(sources, supporting)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert all(
        result[key] is False
        for key in (
            "screen_used",
            "VI_run_or_save",
            "DLL_loaded_or_executed",
            "network_io",
            "hardware_io",
            "production_changes",
            "guaranteed_resource_release",
        )
    )
    assert result["guaranteed_shutdown_deadline_seconds"] is None


def test_discovery_delay_is_not_a_command_watchdog(report):
    rows = report["observations"]["discovery"]
    assert len(rows) == 2
    assert {r["value_ms"] for r in rows} == {5000}
    assert all("not a command deadline" in r["role"] for r in rows)
    wrappers = report["observations"]["NewFocus_wrappers"]
    assert len(wrappers) == 9
    assert not any(r["explicit_timeout_or_cancel_input"] for r in wrappers)


def test_imaq_frame_timeout_value_is_unknown_not_invented(report):
    acq = report["observations"]["acquire"]
    assert acq["Immediate"] is False and acq["own_total_deadline"] is None
    attrs = report["observations"]["NI_frame_timeout"]
    assert attrs["ring_ordinal"] == 42
    assert attrs["setup_selected_ordinal"] == 37
    assert attrs["setup_selected_label"] == "Current buffer list ID"
    assert attrs["actual_session_value_ms"] is None
    assert attrs["configuration_or_driver_default_not_recovered"] is False
    assert attrs["saved_configuration"]["saved_frame_timeout_ms"] == 1000
    assert (
        attrs["saved_configuration"]["currently_loaded_file_identity_proven"] is False
    )
    assert len(report["observations"]["Main_IMAQ_properties"]) == 3


def test_all_five_ni_core_boundaries_have_no_supplied_abort_callback(report):
    rows = report["observations"]["NI_candidate_boundaries"]
    assert len(rows) == 5
    assert rows["IMAQ_Grab_Acquire"]["symbol"] == "imgGrabAcquire_LV"
    assert rows["imgGrabArea"]["symbol"] == "imgGrabArea"
    assert all(row["abort_callback"] is None for row in rows.values())
    assert not any(row["driver_internal_deadline_known"] for row in rows.values())


def test_candidate_ethernet_waits_are_not_total_deadlines(report):
    eth = report["observations"]["candidate_ethernet"]
    assert eth["availability_wait"] == {"Sleep_ms": 10, "iteration_limit": 30}
    assert eth["Poll_arguments"] == [500000, 500000, 500000]
    assert eth["whole_operation_deadline_proven"] is False
    assert eth["socket_ReceiveTimeout_or_SendTimeout_setters_found"] == []
    path = report["observations"]["candidate_GetMotionDone_to_Ethernet_Query"]
    assert path[0]["name"] == "GetMotionDone"
    assert path[-1]["owner"] == "Newport.Ethernet.Ethernet"
    assert path[-1]["name"] == "Query"


def test_cleanup_native_call_order_is_not_a_finally_guarantee(report):
    cleanup = report["observations"]["cleanup"]
    assert cleanup["frame"] == "14127"
    assert cleanup["motion_order"] == ["177515 AbortMotion.vi", "192398 Shutdown.vi"]
    assert cleanup["native_deadlines_proven"] is False
    assert cleanup["independent_PSP_image_motion_chains"] is True


@pytest.mark.parametrize(
    "pending", ["init_returned", "runtime_returned", "wait_clear", "motion_finished"]
)
def test_requested_stop_cannot_jump_over_a_pending_dependency(pending):
    states = dict(
        init_returned=True,
        runtime_returned=True,
        wait_clear=True,
        motion_finished=True,
        cleanup_returned=True,
    )
    states[pending] = False
    assert trace.shutdown_witness(True, **states) == {
        "cleanup_entered": False,
        "cleanup_frame_finished": False,
        "all_resources_released": None,
    }


def test_cleanup_itself_can_remain_pending():
    result = trace.shutdown_witness(
        True,
        init_returned=True,
        runtime_returned=True,
        wait_clear=True,
        motion_finished=True,
        cleanup_returned=False,
    )
    assert result["cleanup_entered"] is True
    assert result["cleanup_frame_finished"] is False
    assert result["all_resources_released"] is None


def test_even_returning_cleanup_does_not_prove_all_resources_closed():
    result = trace.shutdown_witness(
        True,
        init_returned=True,
        runtime_returned=True,
        wait_clear=True,
        motion_finished=True,
        cleanup_returned=True,
    )
    assert result["cleanup_frame_finished"] is True
    assert result["all_resources_released"] is None


@pytest.mark.parametrize("bad", [None, 0, 1, "pending"])
def test_unknown_native_completion_is_not_silently_coerced(bad):
    with pytest.raises(ValueError):
        trace.shutdown_witness(
            True,
            init_returned=bad,
            runtime_returned=True,
            wait_clear=True,
            motion_finished=True,
            cleanup_returned=True,
        )


def test_rejects_changed_discovery_literal(sources, supporting):
    roots = copy.deepcopy(sources[1])
    literal = next(
        n for n in roots["bd"].iter() if n.get("uid") == "61835" and n.get("class")
    )
    literal.find("dco/ConstValue").text = "00001770"
    with pytest.raises(AssertionError, match="discovery delay literal changed"):
        trace.verify((sources[0], roots), supporting)


def test_rejects_changed_immediate_boolean(sources, supporting):
    roots = copy.deepcopy(sources[1])
    literal = next(
        n for n in roots["bd"].iter() if n.get("uid") == "13352" and n.get("class")
    )
    literal.find("dco/ConstValue").text = "0001"
    with pytest.raises(AssertionError, match="Boolean literal changed"):
        trace.verify((sources[0], roots), supporting)


@pytest.mark.parametrize("name", list(trace.CORE_NATIVE))
def test_rejects_a_changed_ni_native_abort_callback(supporting, name):
    from export_sup_beam_indicator_routes import SourceGraph, components

    receipt, roots = supporting[1][name]
    roots = copy.deepcopy(roots)
    uid, symbol = trace.CORE_NATIVE[name]
    n = next(
        n
        for n in roots["bd"].iter()
        if n.get("uid") == uid and n.get("class") == "extFunc"
    )
    n.find("abortCB").text = "different_callback"
    T, _ = components()
    graph = SourceGraph(receipt, roots, T(roots["meta"]))
    with pytest.raises(AssertionError, match="native abort callback changed"):
        trace.boundary(graph, uid, symbol)


def test_rejects_corrupted_disassembled_instruction_bytes(supporting):
    eth = copy.deepcopy(supporting[2]["NpEthernet"])
    method = next(m for m in eth["methods"] if m["IL"])
    method["IL"][0]["bytes"] = "FF"
    with pytest.raises(AssertionError, match="IL instruction bytes differ"):
        trace.validate_il(eth)


@pytest.mark.parametrize("offset,value", [(71, 20), (83, 31), (100, 600000)])
def test_rejects_changed_local_wait_constants(supporting, offset, value):
    eth = copy.deepcopy(supporting[2]["NpEthernet"])
    method = next(m for m in eth["methods"] if m["token"] == "0x0600002D")
    ins = next(i for i in method["IL"] if i["offset"] == offset)
    ins["arg"] = value
    with pytest.raises(AssertionError):
        trace.ethernet_contract(eth)


def test_rejects_claimed_native_execution(supporting):
    eth = copy.deepcopy(supporting[2]["NpEthernet"])
    eth["assembly_loaded"] = True
    with pytest.raises(AssertionError, match="generated by managed execution"):
        trace.validate_il(eth)


def test_saved_camera_configuration_is_not_a_live_session_read():
    root = trace.REPO / "Supervision/source/PILOTAGE_ELYSE_SUP"
    result = trace.config_contract(
        (root / "img0.iid").read_text("utf-8"),
        (root / "CCIR(1409).icd").read_text("utf-8"),
    )
    assert result["saved_frame_timeout_ms"] == 1000
    assert result["currently_loaded_file_identity_proven"] is False


@pytest.mark.parametrize("change", ["timeout", "channel", "interface"])
def test_rejects_changed_saved_camera_configuration(change):
    root = trace.REPO / "Supervision/source/PILOTAGE_ELYSE_SUP"
    iid = (root / "img0.iid").read_text("utf-8")
    icd = (root / "CCIR(1409).icd").read_text("utf-8")
    if change == "timeout":
        icd = icd.replace("FrameTimeout (1000)", "FrameTimeout (2000)")
    elif change == "channel":
        iid = iid.replace('Channel1 = "CCIR(1409).icd"', 'Channel1 = "other.icd"')
    else:
        iid = iid.replace('InterfaceName = "img0.iid"', 'InterfaceName = "img1.iid"')
    with pytest.raises(AssertionError):
        trace.config_contract(iid, icd)
