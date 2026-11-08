"""Pinned source mutations and supplied-state cooperative-stop witnesses."""

import copy
import json
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_normal_stop as trace


@pytest.fixture(scope="module")
def sources():
    return trace.original()


@pytest.fixture(scope="module")
def report(sources):
    return trace.verify(*sources)


def changed(sources):
    return sources[0], copy.deepcopy(sources[1])


def node(sources, uid):
    return next(
        n for n in sources[1]["bd"].iter() if n.get("uid") == uid and n.get("class")
    )


def test_reproduces_with_network_forbidden(sources, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network allowed in stop proof")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = trace.verify(*sources)
    assert result == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert result["all_runtime_Main_loops_enumerated"]
    assert not any(
        result[k]
        for k in (
            "screen_used",
            "VI_run_or_save",
            "network_io",
            "hardware_io",
            "production_changes",
            "all_stop_paths_finish_cleanup_guaranteed",
            "hardware_safe_state_proven",
            "full_Supervision_coverage",
        )
    )


def test_request_is_ui_control_not_program_true_writer(report):
    obs = report["observations"]
    stop = obs["stop_control"]
    assert stop["caption"] == "STOP" and stop["Main_local_bank"] == 49
    assert stop["program_True_writers"] == []
    assert stop["sole_program_writer"] == {
        "uid": "12664",
        "value": False,
        "frame": "14127",
    }
    assert obs["STOP_event_registered"] is False
    assert len(obs["event_registrations"]) == 38
    assert obs["event_timeout_ms"] == 80


def test_all_twenty_main_runtime_loops_are_accounted_for(report):
    obs = report["observations"]
    assert len(obs["runtime_loop_census"]) == 20
    assert obs["loop_class_counts"] == {"timeLoop": 1, "whileLoop": 13, "forLoop": 6}
    assert len(obs["outer_loops"]) == 4
    assert all(
        r["stop_if_true"] and r["iteration_must_finish"] for r in obs["outer_loops"]
    )
    assert {r["loop"] for r in obs["motor_stop_routes"]} == set(trace.MOTOR)


def test_seven_motor_dependencies_are_actual_or_routes_not_alias_bfs(report):
    for row in report["observations"]["motor_stop_routes"]:
        assert row["route"][0]["from"] == row["port"]
        assert row["route"][-1]["to"] == row["test"]
        assert any(step["kind"] == "OR" for step in row["route"])
        assert {step["kind"] for step in row["route"]} == {"wire", "OR"}


def test_wait_is_independent_of_global_stop(report):
    obs = report["observations"]
    assert obs["camera_wait"] == {
        "loop": "6584",
        "continue_when": "Wait",
        "sleep_ms": 50,
        "checks_global_stop": False,
    }
    writes = obs["Wait_writers"]
    assert len(writes) == 9
    assert sum(row["value"] for row in writes) == 4
    assert {row["event"] for row in writes} == {None, 24, 25, 30}


def test_counter_bound_is_iteration_bound_not_wall_clock_deadline(report):
    obs = report["observations"]["other_nested_loop"]
    assert obs["iteration_cap_predicate"] == "i >1200"
    assert obs["wait_ms_per_iteration"] == 100
    assert obs["max_completed_iterations_without_earlier_exit"] == 1202
    assert next(i for i in range(1203) if i > 1200) == 1201
    assert not obs["checks_global_stop"]


@pytest.mark.parametrize(
    "wait_held,motion_pending",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_all_true_outer_samples_are_insufficient_if_a_child_is_still_busy(
    wait_held, motion_pending
):
    result = trace.cooperative_witness(
        (True,) * 4, wait_held=wait_held, motion_pending=motion_pending
    )
    assert result["cleanup_frame_eligible"] == (not wait_held and not motion_pending)
    assert result["effects_executed"] is False
    assert result["cleanup_success_proven"] is False


@pytest.mark.parametrize("late_loop", range(4))
def test_every_outer_loop_must_notice_request_and_complete(late_loop):
    samples = tuple(i != late_loop for i in range(4))
    result = trace.cooperative_witness(samples)
    assert not result["cleanup_frame_eligible"]
    assert result["outer_bodies_finished_and_stop_seen"] == samples


@pytest.mark.parametrize(
    "samples", [None, (), (True,), (1, True, True, True), [True] * 4]
)
def test_unsupplied_or_coerced_states_are_rejected(samples):
    with pytest.raises(ValueError):
        trace.cooperative_witness(samples)


def test_cleanup_is_an_attempt_and_false_stop_is_not_a_completion_ack(report):
    cleanup = report["observations"]["cleanup"]
    assert cleanup["requires_runtime_frame_completion"]
    assert cleanup["PSP_URL_count"] == 13 and cleanup["image_count"] == 9
    assert cleanup["PSP_initial_error_shift_register_not_wired"]
    assert cleanup["image_disposal_all"] and cleanup["initial_image_error_cluster_zero"]
    assert cleanup["addressed_AbortMotion_then_Shutdown"] == ["177515", "192398"]
    assert cleanup["Main_PSP_zeroing_or_shutdown_writes"] == []
    assert not cleanup["stop_False_reset_ordered_after_resource_closes"]


def test_psp_cleanup_array_does_not_cover_all_runtime_urls(report):
    cleanup = report["observations"]["cleanup"]
    assert len(cleanup["runtime_PSP_URL_sites"]) == 24
    assert len(cleanup["PSP_close_target_URLs"]) == 13
    assert len(cleanup["runtime_PSP_URLs_not_in_explicit_close_array"]) == 12
    assert {
        url.rsplit("/", 1)[1]
        for url in cleanup["runtime_PSP_URLs_not_in_explicit_close_array"]
    } == {
        "VAD",
        "VDD",
        "DPS",
        "DPC",
        "C1011NI6602",
        "VTS",
        "VTA",
        "VTL",
        "VAM-A",
        "EPC",
        "EPS",
        "VDM-A",
    }
    assert cleanup["Main_PSP_close_primitive_sites"] == ["14463"]


def test_wrong_close_target_is_detected(sources):
    altered = changed(sources)
    value = b"ni.var.psp://localhost/SUPERVISION/EPS"
    raw = len(value).to_bytes(4, "big") + value
    node(altered, "31821").find("dco/ConstValue").text = raw.hex().upper()
    with pytest.raises(AssertionError, match="explicit close target list changed"):
        trace.verify(*altered)


@pytest.mark.parametrize("loop,flags", [("6017", "1"), ("6584", "65537")])
def test_changed_stop_polarity_is_rejected(sources, loop, flags):
    altered = changed(sources)
    node(altered, loop).find("loopTestDCO/objFlags").text = flags
    with pytest.raises(AssertionError):
        trace.verify(*altered)


@pytest.mark.parametrize(
    "net,index,replacement",
    [
        ("11791", 0, "26305"),
        ("6569", 0, "21242"),
        ("96147", 0, "14053"),
        ("177516", 0, "12839"),
        ("26734", 0, "12839"),
    ],
)
def test_changed_stop_or_release_wire_is_rejected(sources, net, index, replacement):
    altered = changed(sources)
    node(altered, net).findall("termList/*")[index].set("uid", replacement)
    with pytest.raises(AssertionError):
        trace.verify(*altered)


def test_stop_true_program_assignment_is_rejected(sources):
    altered = changed(sources)
    node(altered, "12839").find("dco/ConstValue").text = "01"
    with pytest.raises(AssertionError, match="Boolean literal changed"):
        trace.verify(*altered)


def test_new_stop_event_registration_is_rejected(sources):
    altered = changed(sources)
    node(altered, "5909").find("EventNodeEvents/*/ddoUID").text = "6015"
    with pytest.raises(AssertionError, match="STOP gained an event"):
        trace.verify(*altered)


def test_wait_false_clear_cannot_be_assumed_if_its_literal_changes(sources):
    altered = changed(sources)
    node(altered, "14803").find("dco/ConstValue").text = "01"
    with pytest.raises(AssertionError, match="Boolean literal changed"):
        trace.verify(*altered)


def test_motion_or_cannot_be_replaced_by_and(sources):
    altered = changed(sources)
    node(altered, "95900").find("primResID").text = "1061"
    with pytest.raises(AssertionError, match="lost its OR influence"):
        trace.verify(*altered)


def test_psp_shift_register_initializer_change_is_detected(sources):
    altered = changed(sources)
    net = ET.SubElement(
        altered[1]["bd"].find("root/nodeList"),
        "SL__arrayElement",
        {"class": "signal", "uid": "test-only-initializer"},
    )
    ports = ET.SubElement(net, "termList")
    for uid in ("26728", "12555"):
        ET.SubElement(ports, "SL__arrayElement", {"uid": uid})
    with pytest.raises(AssertionError, match="register gained an initializer"):
        trace.verify(*altered)


def test_mislabelled_camera_screenshot_limit_is_preserved(report):
    assert any(
        "0[0..9]" in line and "frame9" in line
        for line in report["unknown_or_requires_further_evidence"]
    )
    assert report["hardware_safe_state_proven"] is False
